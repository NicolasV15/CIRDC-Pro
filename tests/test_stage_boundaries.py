import json
import pytest

from cirdc.model import field_states, normalize
from cirdc.config import Config
from cirdc.engine import Service
from unittest.mock import Mock
from test_engine import setup as setup, run_id
from test_provider import client, response


@pytest.mark.parametrize('abstract', ['x' * 400 + '...', 'A full-looking search abstract. ' * 40])
def test_search_results_only_supply_legacy_basic_fields(tmp_path, monkeypatch, abstract):
    provider, _ = client(tmp_path, monkeypatch, [response({
        'totalRecords': 1, 'totalPages': 1,
        'records': [{'articleNumber': 12, 'articleTitle': 'Basic title', 'doi': '',
                     'authors': [{'id': '2', 'preferredName': 'Second'},
                                 {'id': '1', 'preferredName': 'First'}],
                     'abstract': abstract, 'keywords': {'Author Keywords': ['search-only']}}],
    })])
    rows = provider.search_all('4', 2026)
    assert rows[0]['articleNumber'] == '12'
    assert rows[0]['doi'] == ''
    assert [a['id'] for a in rows[0]['authors']] == ['2', '1']
    assert 'abstract' not in rows[0] and 'keywords' not in rows[0]
    assert field_states(rows[0]) == ('pending', 'pending')


def test_imported_search_preview_is_pending_but_a_plain_403_char_abstract_is_not():
    assert field_states(normalize({'articleNumber': '1', 'abstract': 'x' * 400 + '...'}))[0] == 'pending'
    assert field_states(normalize({'articleNumber': '2', 'abstract': 'x' * 403}))[0] == 'complete'
    assert field_states(normalize({'articleNumber': '3', 'abstract': 'x' * 399 + '&#39;...'}))[0] == 'pending'


def test_agent_plan_advertises_only_the_selected_stage_fields(tmp_path, monkeypatch):
    service = Service(Config(tmp_path, tmp_path / 'state'), store=Mock())
    monkeypatch.setattr(service, 'indexes', lambda: {'Journals': {}, 'Conferences': {}})
    monkeypatch.setattr(service.storage, 'article_paths', lambda: [])
    monkeypatch.setattr(service, 'summary', lambda: {})
    assert service.plan({'stage': 'metadata'})['fields'] == ['bibliographic']
    assert service.plan({'stage': 'enrich'})['fields'] == ['abstract', 'keywords']


def test_basic_fetch_leaves_enrichment_for_separate_document_stage(setup):
    ctx = setup
    number = ctx['numbers'][0]
    ctx['config'].destination(ctx['relative']).write_text('[]')
    params = {'stage': 'enrich', 'skip_import': True, 'skip_catalog': True, 'workers': 1}
    job = run_id(ctx, params)
    calls = []
    class Source:
        def document(self, value):
            calls.append(value)
            return {'articleNumber': value, 'abstract': 'Document source. ' * 100,
                    'keywords': {'Author Keywords': ['document']}}, {
                'abstract': 'complete', 'keywords': 'complete'}
    ctx['service'].provider = Source()
    # Supplied worker rows are also filtered, even if a producer sends enrichment.
    ctx['service']._fetch(job, {'path': ctx['relative']}, {}, rows=[{
        'articleNumber': number, 'articleTitle': 'Basic source',
        'abstract': 'p' * 400 + '...', 'keywords': {'Author Keywords': ['search']}}])
    basic = ctx['store'].paper(number)
    assert basic['abstract_state'] == basic['keywords_state'] == 'pending'
    assert 'abstract' not in basic['record'] and 'keywords' not in basic['record']
    ctx['service'].flush_exports(job)
    saved = json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]
    assert 'abstract' not in saved and 'keywords' not in saved
    assert calls == []
    ctx['service'].work(job)
    assert calls == [number]
    enriched = ctx['store'].paper(number)
    assert enriched['abstract_state'] == enriched['keywords_state'] == 'complete'
    assert enriched['record']['abstract'] == 'Document source. ' * 100
    assert enriched['record']['keywords'] == {'Author Keywords': ['document']}


def test_basic_fetch_preserves_cached_values_and_does_not_promote_states(setup):
    ctx = setup
    ctx['rows'][0].update(abstract='Cached full abstract. ' * 50,
                          keywords={'Author Keywords': ['cached']})
    ctx['config'].destination(ctx['relative']).write_text(json.dumps(ctx['rows']))
    ctx['service']._import({'path': ctx['relative']}, {})
    number = ctx['numbers'][0]
    # A historical value can exist while still awaiting a document-stage check.
    ctx['store'].execute('UPDATE papers SET abstract_state=%s WHERE number=%s', ('pending', number))
    ctx['store'].db.commit()
    job = run_id(ctx)
    ctx['service']._fetch(job, {'path': ctx['relative']}, {}, rows=[{
        'articleNumber': number, 'articleTitle': 'Updated basic title',
        'abstract': 's' * 400 + '...', 'keywords': {'Author Keywords': ['search']}}])
    paper = ctx['store'].paper(number)
    assert paper['record']['articleTitle'] == 'Updated basic title'
    assert paper['record']['abstract'] == ctx['rows'][0]['abstract']
    assert paper['record']['keywords'] == ctx['rows'][0]['keywords']
    assert paper['abstract_state'] == 'pending'
    assert paper['keywords_state'] == 'complete'
    ctx['service'].flush_exports(job)
    saved = json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]
    assert saved['abstract'] == ctx['rows'][0]['abstract']
    assert saved['keywords'] == ctx['rows'][0]['keywords']


def test_document_stage_can_confirm_a_short_abstract_and_basic_fetch_preserves_its_decision(setup):
    ctx = setup
    ctx['service']._import({'path': ctx['relative']}, {})
    number = ctx['numbers'][0]
    # A boundary signature alone is not definitive when the document source agrees.
    value = 'v' * 400 + '...'
    ctx['store'].update_document({'articleNumber': number, 'abstract': value, 'keywords': {}},
                                 {'abstract': 'complete', 'keywords': 'no_data'})
    ctx['store'].db.commit()
    ctx['store'].upsert_records([{'articleNumber': number, 'articleTitle': 'Basic title'}],
                                ctx['relative'], basic_only=True)
    paper = ctx['store'].paper(number)
    assert paper['record']['abstract'] == value
    assert paper['abstract_state'] == 'complete'
    assert paper['keywords_state'] == 'no_data'
