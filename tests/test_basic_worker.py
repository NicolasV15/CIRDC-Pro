from datetime import datetime
import json
import pytest

from cirdc.engine import Service
from cirdc.store import Store, BusyError
from test_engine import setup as setup, run_id
from test_provider import client, response


def metadata_params(ctx, **extra):
    return {'stage': 'metadata', 'skip_import': True, 'skip_catalog': True,
            'publication': ctx['publication'], 'year': 2026, 'workers': 1, **extra}


def test_metadata_can_fetch_while_a_document_collection_is_active_and_only_lock_writes(setup):
    ctx = setup
    ctx['service']._import({'path': ctx['relative']}, {})
    peer = run_id(ctx, {'mode': 'distributed_collection', 'stage': 'enrich'})
    ctx['store'].set_run(peer, status='collecting')
    other = Store(ctx['config'])
    calls = []
    class Source:
        def search_all(self, number, year):
            # HTTP must not monopolize the shared database writer.
            with other.lock():
                calls.append((number, year))
            return [{'articleNumber': ctx['numbers'][0], 'articleTitle': 'Latest basic',
                     'abstract': 'Ignored search preview...'}]
    ctx['service'].provider = Source()
    original = ctx['service']._fetch
    def writing(*args, **kwargs):
        with pytest.raises(BusyError):
            with other.lock():
                pass
        return original(*args, **kwargs)
    ctx['service']._fetch = writing
    try:
        job = ctx['service'].start(metadata_params(ctx), foreground=True)['run_id']
        assert calls == [(ctx['publication'], 2026)]
        assert ctx['store'].run(job)['status'] == 'completed'
        assert ctx['store'].run(peer)['status'] == 'collecting'
        assert ctx['store'].paper(ctx['numbers'][0])['record']['articleTitle'] == 'Latest basic'
        assert not ctx['store'].paper(ctx['numbers'][0])['record']['abstract']
    finally:
        other.close()


def test_verify_all_seeds_history_despite_recent_cursor_and_checks_future_year(setup):
    ctx = setup
    current = datetime.now().year
    index = {'Journals': {ctx['publication']: {'start_year': str(current - 3), 'end_year': 'Present'}},
             'Conferences': {}}
    ctx['service'].indexes = lambda: index
    old_path = f'articleInfo/Journals/{ctx["publication"]}/{current - 3}.json'
    ctx['store'].execute('INSERT INTO sync_cursors(path,source_count) VALUES (%s,%s)', (old_path, 0))
    ctx['store'].db.commit()
    job = run_id(ctx)
    ctx['service']._seed_fetch(job, {'stage': 'metadata', 'verify_all': True}, {})
    rows = ctx['store'].execute('SELECT payload FROM tasks WHERE run_id=%s AND kind=%s', (job, 'fetch'))
    years = {json.loads(r['payload'])['year'] for r in rows}
    assert current - 3 in years and current + 1 in years


def test_saved_early_access_year_stays_in_scope_before_catalog_start(setup):
    ctx = setup
    current = datetime.now().year
    ctx['service'].indexes = lambda: {'Journals': {ctx['publication']: {
        'start_year': str(current), 'end_year': 'Present'}}, 'Conferences': {}}
    early = ctx['config'].destination(f'articleInfo/Journals/{ctx["publication"]}/{current - 1}.json')
    early.write_text(json.dumps(ctx['rows']))
    job = run_id(ctx)
    ctx['service']._seed_fetch(job, {'stage': 'metadata', 'verify_all': True}, {})
    tasks = ctx['store'].execute('SELECT payload FROM tasks WHERE run_id=%s AND kind=%s', (job, 'fetch'))
    years = {json.loads(r['payload'])['year'] for r in tasks}
    assert {current - 1, current, current + 1} <= years


def test_announced_future_journal_checks_recent_years_without_cached_files(setup):
    ctx = setup
    current = datetime.now().year
    publication = ctx['publication'] + '7'
    ctx['service'].indexes = lambda: {'Journals': {publication: {
        'start_year': str(current + 1), 'end_year': 'Present'}}, 'Conferences': {}}
    job = run_id(ctx)
    ctx['service']._seed_fetch(job, {'stage': 'metadata', 'verify_all': True}, {})
    tasks = ctx['store'].execute('SELECT payload FROM tasks WHERE run_id=%s AND kind=%s', (job, 'fetch'))
    years = {json.loads(r['payload'])['year'] for r in tasks}
    assert years == {current - 1, current, current + 1}


def test_catalog_keeps_unchanged_merged_index_and_still_records_year_snapshot(setup):
    ctx = setup
    records = [{'parentPublicationNumber': ctx['publication'], 'parentTitle': 'Synthetic series',
                'titleHistory': [{'publicationNumber': ctx['publication'] + '1',
                                  'startYear': '2026', 'displayTitle': 'Synthetic edition'}]}]
    first = run_id(ctx)
    ctx['service']._catalog(first, {'kind': 'Conferences', 'year': 2026}, records=records)
    ctx['service'].flush_exports(first)
    second = run_id(ctx)
    ctx['service']._catalog(second, {'kind': 'Conferences', 'year': 2026}, records=records)
    paths = {x['path'] for x in ctx['store'].execute('SELECT path FROM exports WHERE run_id=%s', (second,))}
    assert paths == {'publicationInfo/Conferences/2026/cirdc.json'}
    records[0]['parentTitle'] = 'Updated series title'
    ctx['service']._catalog(second, {'kind': 'Conferences', 'year': 2026}, records=records)
    ctx['service'].flush_exports(second)
    saved = json.loads(ctx['config'].destination('publicationInfo/all_conferences.json').read_text())
    assert saved[ctx['publication']]['parentTitle'] == 'Updated series title'


def test_basic_upsert_only_indexes_actual_changes(setup, monkeypatch):
    ctx = setup
    changed = []
    monkeypatch.setattr(ctx['store'], 'index_changed', lambda numbers: changed.extend(numbers))
    record = {'articleNumber': ctx['numbers'][0], 'articleTitle': 'Stable'}
    ctx['store'].upsert_records([record], ctx['relative'], basic_only=True)
    assert ctx['store'].last_upsert_stats == {'new': 1, 'updated': 0, 'unchanged': 0}
    changed.clear()
    ctx['store'].upsert_records([record], ctx['relative'], basic_only=True)
    assert ctx['store'].last_upsert_stats == {'new': 0, 'updated': 0, 'unchanged': 1}
    assert changed == []


def test_committed_document_export_is_rebuilt_before_a_basic_update(setup):
    ctx = setup
    ctx['service']._import({'path': ctx['relative']}, {})
    number = ctx['numbers'][0]
    peer = run_id(ctx, {'stage': 'enrich', 'mode': 'distributed_collection'})
    ctx['store'].add_tasks(peer, 'enrich', [(number, {'number': number, 'refresh_existing': True})])
    task = ctx['store'].next_task(peer)
    ctx['store'].update_document({'articleNumber': number, 'abstract': 'Committed full text'},
                                  {'abstract': 'complete', 'keywords': 'no_data'})
    ctx['store'].execute('INSERT INTO exports(run_id,path,staged_path,digest,status) VALUES (%s,%s,%s,%s,%s)',
                         (peer, ctx['relative'], '/foreign-host/missing-stage.json', '0' * 64, 'pending'))
    ctx['store'].task_state(task['id'], 'done')
    ctx['store'].set_run(peer, status='collecting')
    class Source:
        def search_all(self, *args):
            return [{'articleNumber': number, 'articleTitle': 'New title'}]
    ctx['service'].provider = Source()
    job = ctx['service'].start(metadata_params(ctx), foreground=True)['run_id']
    saved = json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]
    assert saved['articleTitle'] == 'New title'
    assert saved['abstract'] == 'Committed full text'
    assert ctx['store'].counts(peer)['exports_pending'] == 0
    assert ctx['store'].run(job)['status'] == 'completed'


def test_cached_network_result_recovers_after_write_interruption(setup, monkeypatch):
    ctx = setup
    calls = []
    class Source:
        def search_all(self, *args):
            calls.append(True)
            return [{'articleNumber': ctx['numbers'][0], 'articleTitle': 'Fetched once'}]
    ctx['service'].provider = Source()
    real_fetch = ctx['service']._fetch
    monkeypatch.setattr(ctx['service'], '_fetch', lambda *a, **k: (_ for _ in ()).throw(OSError('write offline')))
    with pytest.raises(OSError):
        ctx['service'].start(metadata_params(ctx), foreground=True)
    job = ctx['store'].execute('SELECT id FROM runs ORDER BY created_at DESC,id DESC LIMIT 1')[0]['id']
    monkeypatch.setattr(ctx['service'], '_fetch', real_fetch)
    ctx['service'].resume(job, foreground=True)
    assert len(calls) == 1
    assert ctx['store'].run(job)['status'] == 'completed'


def test_cached_rows_without_identifiers_are_retained_while_valid_articles_import(setup):
    ctx = setup
    invalid = {'articleNumber': None, 'articleTitle': 'Historic unresolved record'}
    ctx['config'].destination(ctx['relative']).write_text(json.dumps([invalid, ctx['rows'][0]]))
    job = run_id(ctx)
    ctx['service']._fetch(job, {'path': ctx['relative']}, {}, rows=[ctx['rows'][0]])
    ctx['service'].flush_exports(job)
    saved = json.loads(ctx['config'].destination(ctx['relative']).read_text())
    assert invalid in saved
    assert ctx['store'].paper(ctx['numbers'][0])


def test_archive_only_cache_does_not_roll_back_newer_canonical_metadata(setup):
    ctx = setup
    number = ctx['numbers'][0]
    ctx['store'].upsert_records([{'articleNumber': number, 'articleTitle': 'New canonical title',
                                  'publicationYear': '2026'}], basic_only=True)
    ctx['store'].db.commit()
    cached = {'articleNumber': number, 'articleTitle': 'Old archived title', 'publicationYear': '2025'}
    ctx['config'].destination(ctx['relative']).write_text(json.dumps([cached]))
    job = run_id(ctx)
    ctx['service']._fetch(job, {'path': ctx['relative']}, {}, rows=[])
    ctx['service'].flush_exports(job)
    saved = ctx['store'].paper(number)['record']
    assert saved['articleTitle'] == 'New canonical title'
    assert saved['publicationYear'] == '2026'
    assert json.loads(ctx['config'].destination(ctx['relative']).read_text()) == [cached]


def test_source_omission_preserves_newer_database_fields_and_refreshes_basic_snapshot(setup):
    ctx = setup
    number = ctx['numbers'][0]
    ctx['store'].upsert_records([{'articleNumber': number, 'doi': '10.synthetic/current',
                                  'articleTitle': 'Previous canonical title'}], basic_only=True)
    ctx['store'].db.commit()
    cached = {'articleNumber': number, 'doi': '10.synthetic/old', 'articleTitle': 'Cached title',
              'abstract': 'Retain cached enrichment', 'keywords': {'Author Keywords': ['cached']}}
    ctx['config'].destination(ctx['relative']).write_text(json.dumps([cached]))
    job = run_id(ctx)
    ctx['service']._fetch(job, {'path': ctx['relative']}, {},
                          rows=[{'articleNumber': number, 'articleTitle': 'Latest source title', 'doi': ''}])
    ctx['service'].flush_exports(job)
    paper = ctx['store'].paper(number)
    saved = json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]
    assert paper['record']['doi'] == saved['doi'] == '10.synthetic/current'
    assert paper['record']['articleTitle'] == saved['articleTitle'] == 'Latest source title'
    assert saved['abstract'] == cached['abstract'] and saved['keywords'] == cached['keywords']
    assert paper['abstract_state'] == paper['keywords_state'] == 'pending'


def test_basic_patch_preserves_enrichment_and_unrelated_null_fields(setup):
    ctx = setup
    number = ctx['numbers'][0]
    original = {'articleNumber': number, 'articleTitle': 'Old title', 'abstract': 'Full cached abstract',
                'keywords': {'Author Keywords': ['preserved']}, 'external_note': None}
    ctx['store'].execute('INSERT INTO papers(number,data,abstract_state,keywords_state) VALUES (%s,%s,%s,%s)',
                         (number, json.dumps(original), 'complete', 'complete'))
    source = {'articleNumber': number, 'articleTitle': 'Latest title', 'abstract': 'Ignored preview...'}
    ctx['store'].upsert_records([source], basic_only=True, source_records={number: source})
    ctx['store'].db.commit()
    saved = ctx['store'].paper(number)
    assert saved['record']['articleTitle'] == 'Latest title'
    assert saved['record']['abstract'] == original['abstract']
    assert saved['record']['keywords'] == original['keywords']
    assert 'external_note' in saved['record'] and saved['record']['external_note'] is None
    assert saved['abstract_state'] == saved['keywords_state'] == 'complete'


@pytest.mark.parametrize('pages', [None, 0, 1])
def test_confirmed_empty_search_can_omit_records(tmp_path, monkeypatch, pages):
    payload = {'totalRecords': 0}
    if pages is not None:
        payload['totalPages'] = pages
    provider, _ = client(tmp_path, monkeypatch, [response(payload)])
    assert provider.search_all('4', 2027) == []


@pytest.mark.parametrize('payload', [{'totalRecords': 0, 'error': 'blocked'},
                                    {'totalRecords': 0, 'totalPages': True},
                                    {'totalRecords': 0, 'records': [{'articleNumber': '1'}]}])
def test_malformed_zero_is_not_source_absence(tmp_path, monkeypatch, payload):
    provider, _ = client(tmp_path, monkeypatch, [response(payload)])
    with pytest.raises(Exception):
        provider.search_all('4', 2027)
