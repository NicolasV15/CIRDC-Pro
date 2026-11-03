from contextlib import closing

import pytest
from starlette.testclient import TestClient

from cirdc.config import Config
from cirdc.web.app import create_app
from cirdc.web.fulltext import paper_passages, passages, run_fulltext_index, search_body, status
from cirdc.web.index import initialize, put_rows, save_meta
from cirdc.web.resources import ResourceProviders
from cirdc.web.settings import connect

BODY = ('<section id="sec1"><p>SECTION I.</p><h2 id="sec1-h">Introduction</h2>'
        '<p>The proposed converter partitions the conversion into a coarse SAR stage and a fine stage.</p>'
        '<p>Because the amplifier operates open loop, its gain depends on the transconductance '
        '<span class="doc-math">\\(g_m\\)</span> and the integration time.</p></section>'
        '<section id="sec2"><h2 id="sec2-h">II. Architecture</h2>'
        '<p>A successive-approximation ADC resolves the residue.<span class="doc-math">\\[V=1\\]</span>'
        '<span><span>View Source</span><span>\\[V=1\\]</span></span></p>'
        '<ul><li><p>Background calibration corrects inter-stage gain errors.</p></li></ul>'
        '<figure><img src="x.png"><figcaption>Fig. 1. Measured SNDR versus input frequency.</figcaption></figure>'
        '<table><tr><th>Metric</th><th>This work</th></tr><tr><td>SNDR</td><td>62.3 dB</td></tr></table></section>')


class CatalogProvider:
    def __init__(self):
        self.documents = {'201': ('v1', BODY), '202': ('v1', '<h2 id="a">Results</h2><p>The SAR ADC achieves 62 dB SNDR.</p>'
                                                     '<p>Calibration of the SAR ADC is performed in background.</p>'),
                          '203': ('v1', '<p>A bang-bang PLL locks quickly.</p>')}
        self.states = {'201': 'ready', '202': 'ready', '203': 'ready', '204': 'failed'}
        self.reads = []

    def links(self, numbers): return {}
    def routes(self): return []

    def agent_document_catalog(self, cursor=None, limit=100):
        items = [{'number': n, 'version': (self.documents.get(n) or ('',))[0], 'state': s} for n, s in sorted(self.states.items())]
        start = int(cursor or 0)
        page = items[start:start + 2]
        return {'items': page, 'cursor': str(start + len(page)), 'more': start + len(page) < len(items), 'total': len(items)}

    def agent_document(self, number, version=None):
        self.reads.append((number, version))
        current, html = self.documents[number]
        assert version in (None, current)
        return {'version': current, 'html': html, 'source': 'ieee_html', 'state': 'ready', 'toc': []}

    def agent_ensure(self, *args, **kwargs):
        raise AssertionError('Indexing must never request acquisition')


def providers(provider):
    value = object.__new__(ResourceProviders)
    value.providers, value.interface = [provider], 'reader'
    return value


@pytest.fixture
def body_site(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'web'))
    with closing(connect('search.sqlite')) as db:
        initialize(db)
        put_rows(db, [{'number': n, 'data': {'articleTitle': 'Fixture paper ' + n, 'authors': [{'preferredName': 'Lin Zhang'}],
                       'abstract': 'Metadata only.', 'keywords': {}, 'publicationYear': str(year), 'publicationNumber': '4',
                       'doi': '', 'articleContentType': 'Journals'}, 'abstract_state': 'complete', 'keywords_state': 'complete'}
                      for n, year in [('201', 2024), ('202', 2025), ('203', 2023), ('204', 2022), ('205', 2021)]])
        save_meta(db, phase='ready', indexed=5, checked_at='2999-01-01T00:00:00+00:00', authors_phase='ready')
        db.commit()
    provider = CatalogProvider()
    config = Config(tmp_path, tmp_path / 'runtime', {})
    return config, provider


def test_passages_follow_reader_blocks_sections_and_formula_placeholders():
    rows = passages(BODY)
    texts = [row['text'] for row in rows]
    assert 'SECTION I.' not in texts  # merged into the following heading by the reader
    assert texts[0] == 'Introduction' and rows[0]['kind'] == 'heading'
    math = rows[2]
    assert math['text'] == 'Because the amplifier operates open loop, its gain depends on the transconductance ⋯ and the integration time.'
    assert math['section'] == 'I. Introduction' and math['section_id'] == 'sec1-h'
    assert any(row['text'] == 'A successive-approximation ADC resolves the residue. ⋯' for row in rows)
    assert not any('View Source' in text for text in texts)
    assert 'Background calibration corrects inter-stage gain errors.' in texts  # li > p is one passage
    caption = next(row for row in rows if row['kind'] == 'caption')
    assert caption['section'] == 'II. Architecture'
    assert [row['text'] for row in rows if row['kind'] == 'table'] == ['Metric This work', 'SNDR 62.3 dB']
    assert [row['ordinal'] for row in rows] == list(range(len(rows)))


def test_indexer_reads_only_cached_catalog_documents_and_tracks_versions(body_site):
    config, provider = body_site
    assert status()['enabled'] is False
    result = run_fulltext_index(config, once=True, providers=providers(provider))
    assert result['documents'] == 3 and result['phase'] == 'ready' and result['catalog_total'] == 4 and result['pending'] == 0
    assert sorted(provider.reads) == [('201', 'v1'), ('202', 'v1'), ('203', 'v1')]
    run_fulltext_index(config, once=True, providers=providers(provider))
    assert len(provider.reads) == 3  # unchanged versions are not read again
    provider.documents['203'] = ('v2', '<p>A charge-pump PLL with a sampling phase detector.</p>')
    with closing(connect('fulltext.sqlite')) as db:
        db.execute("UPDATE meta SET value='\"0\"' WHERE key='catalog_cursor'")
        db.commit()
    run_fulltext_index(config, once=True, providers=providers(provider))
    assert provider.reads[-1] == ('203', 'v2')
    assert paper_passages('203', {'q': 'bang-bang PLL'})['total'] == 0
    assert paper_passages('203', {'q': 'charge-pump PLL'})['total'] == 1


def test_sentence_search_distinguishes_exact_source_from_approximate_matches(body_site):
    config, provider = body_site
    run_fulltext_index(config, once=True, providers=providers(provider))
    exact = search_body({'q': 'because the AMPLIFIER operates open-loop,\n its gain depends on the transconductance and the integration time'})
    assert exact['query']['match'] == 'exact' and [item['number'] for item in exact['items']] == ['201'] and exact['total'] == 1
    passage = exact['items'][0]['passages'][0]
    assert passage['section'] == 'I. Introduction' and passage['ordinal'] == 2 and passage['match'] == 'exact'
    start, end = passage['excerpt']['highlights'][0]
    assert passage['excerpt']['text'][start:end].startswith('Because the amplifier operates open loop')
    near = search_body({'q': 'the integration time and the transconductance depend on how the amplifier operates in open loop'})
    assert near['query']['match'] == 'approximate' and [item['number'] for item in near['items']] == ['201']
    assert all(p['match'] == 'approximate' for p in near['items'][0]['passages'])
    none = search_body({'q': 'a completely unrelated sentence about antenna arrays and radar imaging'})
    assert none['total'] == 0 and none['items'] == []


def test_term_search_requires_terms_in_one_passage_and_reports_every_hit(body_site):
    config, provider = body_site
    run_fulltext_index(config, once=True, providers=providers(provider))
    sar = search_body({'q': 'SAR ADC'})
    assert sar['query']['match'] == 'terms' and sorted(item['number'] for item in sar['items']) == ['201', '202']
    assert sar['total'] == 2
    exact = search_body({'q': 'SAR ADC', 'terms': 'exact'})
    assert [item['number'] for item in exact['items']] == ['202']
    hits = paper_passages('202', {'q': 'SAR ADC'})
    assert hits['state'] == 'indexed' and hits['total'] == 2 and [h['ordinal'] for h in hits['items']] == [1, 2]
    assert search_body({'q': 'calibration SNDR'})['total'] == 0  # different passages, not one finding
    paged = search_body({'q': 'SAR ADC', 'limit': '1', 'sort': 'year'})
    second = search_body({'q': 'SAR ADC', 'limit': '1', 'sort': 'year', 'cursor': paged['next_cursor']})
    assert [paged['items'][0]['number'], second['items'][0]['number']] == ['202', '201'] and second['next_cursor'] is None
    assert search_body({'q': 'SAR ADC', 'year_to': '2024'})['total'] == 1
    top = search_body({'q': 'SAR ADC', 'view': 'top', 'k': '1'})
    assert len(top['items']) == 1 and top['total'] == 2 and top['items'][0]['position'] == 1


def test_paper_states_separate_no_body_not_indexed_and_disabled(body_site):
    config, provider = body_site
    assert paper_passages('201', {'q': 'SAR'})['state'] == 'disabled'
    run_fulltext_index(config, max_rows=1, providers=providers(provider))
    with closing(connect('fulltext.sqlite')) as db:
        db.execute("INSERT OR REPLACE INTO catalog(number,version,state,seen_at) VALUES('203','v1','ready','now')")
        db.commit()
    assert paper_passages('203', {'q': 'PLL'})['state'] == 'not_indexed'
    assert paper_passages('205', {'q': 'PLL'})['state'] == 'unknown'
    run_fulltext_index(config, once=True, providers=providers(provider))
    assert paper_passages('204', {'q': 'PLL'})['state'] == 'no_body'
    assert paper_passages('205', {'q': 'PLL'})['state'] == 'no_body'  # catalog complete and absent
    assert paper_passages('203', {'q': 'PLL'})['state'] == 'indexed'


def test_body_search_routes_and_coverage_status(body_site):
    config, provider = body_site
    with TestClient(create_app(config, resource_providers=providers(provider), reader_auth='public')) as client:
        assert client.get('/api/fulltext/status').json()['fulltext']['enabled'] is False
        assert client.get('/api/papers', params={'field': 'body', 'q': 'SAR ADC'}).json()['items'] == []
        run_fulltext_index(config, once=True, providers=providers(provider))
        value = client.get('/api/papers', params={'field': 'body', 'q': 'SAR ADC', 'totals': 'defer'}).json()
        assert value['total'] is None and len(value['items']) == 2 and value['fulltext']['documents'] == 3
        assert client.get('/api/papers', params={'field': 'body', 'q': 'SAR ADC', 'totals': 'only'}).json()['total'] == 2
        hits = client.get('/api/papers/202/passages', params={'q': 'SAR ADC'}).json()
        assert hits['total'] == 2 and hits['items'][0]['fingerprint'].startswith('the sar adc achieves')
        assert client.get('/api/papers/abc/passages').status_code == 422
        assert client.get('/api/papers', params={'q': 'SAR', 'view': 'cards'}).status_code == 422
        assert client.get('/api/papers', params={'q': 'x' * 601, 'field': 'body'}).status_code == 422


def test_reader_parity_fixture_matches_server_extraction():
    """The browser regression locates these ordinals in the rendered reader; keep both sides aligned."""
    import json
    from pathlib import Path
    from cirdc.web.fulltext import fingerprint
    fixture = json.loads((Path(__file__).parents[1] / 'web/tests/fixtures/fulltextPassages.json').read_text())
    assert [(row['ordinal'], fingerprint(row['text'])) for row in passages(fixture['html'])] == \
        [(row['ordinal'], row['fingerprint']) for row in fixture['passages']]


class IncrementalCatalog(CatalogProvider):
    """An unchanged document never reappears after the saved cursor."""
    def __init__(self):
        super().__init__()
        self.events = [{'number': '201', 'version': 'v1', 'state': 'ready'}]
        self.fail = True

    def agent_document_catalog(self, cursor=None, limit=100):
        start = int(cursor or 0)
        return {'items': self.events[start:start + limit], 'cursor': str(min(start + limit, len(self.events))),
                'more': start + limit < len(self.events), 'total': 1}

    def agent_document(self, number, version=None):
        if self.fail:
            self.reads.append((number, version))
            raise TimeoutError('Cached body temporarily unavailable')
        return super().agent_document(number, version)


@pytest.fixture
def retry_clock(monkeypatch):
    import time
    from types import SimpleNamespace
    from cirdc.web import fulltext
    clock = [1000.0]
    monkeypatch.setattr(fulltext, 'time', SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic,
                                                       sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
    return clock


def test_failed_body_retries_after_restart_without_new_catalog_events(body_site, retry_clock):
    import json
    config, _ = body_site
    provider = IncrementalCatalog()
    first = run_fulltext_index(config, once=True, providers=providers(provider))
    assert (first['documents'], first['pending'], first['failed'], first['blocked']) == (0, 1, 1, 0)
    assert first['next_retry_at'] == 1030
    provider.fail = False
    run_fulltext_index(config, once=True, providers=providers(provider))
    assert len(provider.reads) == 1  # Restart cannot bypass backoff.
    retry_clock[0] = 1030
    fixed = run_fulltext_index(config, once=True, providers=providers(provider))
    assert (fixed['documents'], fixed['pending'], fixed['failed']) == (1, 0, 0)
    assert fixed['next_retry_at'] is None and fixed['error'] is None
    assert search_body({'q': 'SAR ADC'})['total'] == 1
    run_fulltext_index(config, once=True, providers=providers(provider))
    assert len(provider.reads) == 2
    with closing(connect('fulltext.sqlite')) as db:
        retry = db.execute('SELECT * FROM index_retries').fetchone()
        assert retry['resolved_at'] and json.loads(retry['failures'])[0]['error'] == 'TimeoutError'


def test_resident_indexer_retries_without_reopening_catalog(body_site, retry_clock, monkeypatch):
    from cirdc.web import fulltext
    config, _ = body_site
    provider = IncrementalCatalog()
    def sleep(seconds):
        if len(provider.reads) == 2:
            raise KeyboardInterrupt()
        retry_clock[0] += seconds
        provider.fail = False
    monkeypatch.setattr(fulltext.time, 'sleep', sleep)
    with pytest.raises(KeyboardInterrupt):
        run_fulltext_index(config, providers=providers(provider))
    assert len(provider.reads) == 2
    assert status()['documents'] == 1 and status()['pending'] == 0


def test_retry_budget_persists_and_explicit_retry_keeps_history(body_site, retry_clock):
    import json
    from cirdc.web import fulltext
    config, _ = body_site
    provider = IncrementalCatalog()
    for attempt in range(fulltext.MAX_ATTEMPTS):
        result = run_fulltext_index(config, once=True, providers=providers(provider))
        assert len(provider.reads) == attempt + 1
        retry_clock[0] = result['next_retry_at'] or retry_clock[0] + 3600
    assert result['blocked'] == 1 and result['pending'] == 1 and result['next_retry_at'] is None
    assert search_body({'q': 'SAR'})['partial']
    # Even a repeated catalog notification of this same version cannot reset failures.
    provider.events.append(dict(provider.events[0]))
    run_fulltext_index(config, once=True, providers=providers(provider))
    assert len(provider.reads) == fulltext.MAX_ATTEMPTS
    provider.fail = False
    fixed = run_fulltext_index(config, once=True, retry_failed=True, providers=providers(provider))
    assert fixed['pending'] == 0 and fixed['blocked'] == 0
    with closing(connect('fulltext.sqlite')) as db:
        row = db.execute('SELECT * FROM index_retries').fetchone()
        assert len(json.loads(row['failures'])) == fulltext.MAX_ATTEMPTS and row['resolved_at']


def test_new_version_gets_its_own_retry_budget(body_site, retry_clock):
    from cirdc.web import fulltext
    config, _ = body_site
    provider = IncrementalCatalog()
    for _ in range(fulltext.MAX_ATTEMPTS):
        value = run_fulltext_index(config, once=True, providers=providers(provider))
        retry_clock[0] = value['next_retry_at'] or retry_clock[0] + 3600
    provider.fail = False
    provider.documents['201'] = ('v2', '<p>New comparator architecture.</p>')
    provider.events.append({'number': '201', 'version': 'v2', 'state': 'ready'})
    fixed = run_fulltext_index(config, once=True, providers=providers(provider))
    assert fixed['pending'] == 0 and fixed['blocked'] == 0
    assert paper_passages('201', {'q': 'comparator'})['version'] == 'v2'


def test_failed_replacement_preserves_previous_passages_and_fts(body_site, retry_clock, monkeypatch):
    from cirdc.web import fulltext
    config, _ = body_site
    provider = IncrementalCatalog(); provider.fail = False
    run_fulltext_index(config, once=True, providers=providers(provider))
    provider.documents['201'] = ('v2', '<p>New comparator architecture.</p>')
    provider.events.append({'number': '201', 'version': 'v2', 'state': 'ready'})
    original = fulltext.store_document
    def broken(db, number, version, source, rows):
        original(db, number, version, source, rows)
        raise RuntimeError('Failure after replacement writes')
    monkeypatch.setattr(fulltext, 'store_document', broken)
    result = run_fulltext_index(config, once=True, providers=providers(provider))
    assert result['documents'] == 1 and result['pending'] == 1
    old = search_body({'q': 'SAR ADC'})
    assert old['total'] == 1 and old['partial'] and old['items'][0]['passages'][0]['version'] == 'v1'
    assert search_body({'q': 'comparator'})['total'] == 0
    monkeypatch.setattr(fulltext, 'store_document', original)
    retry_clock[0] = result['next_retry_at']
    run_fulltext_index(config, once=True, providers=providers(provider))
    assert search_body({'q': 'SAR ADC'})['total'] == 0
    assert paper_passages('201', {'q': 'comparator'})['version'] == 'v2'


def test_legacy_pending_failures_migrate_without_resetting_catalog_cursor(body_site):
    import json
    from cirdc.web import fulltext
    config, _ = body_site
    provider = IncrementalCatalog(); provider.fail = False
    with closing(connect('fulltext.sqlite')) as db:
        fulltext.initialize(db)
        db.execute('DROP TABLE index_retries')
        db.execute("INSERT INTO catalog(number,version,state,seen_at,error) VALUES('201','v1','ready','old','TimeoutError')")
        fulltext.save_meta(db, catalog_cursor='1', phase='ready', error='TimeoutError')
        db.commit()
    assert status()['pending'] == 1 and status()['failed'] == 1
    fixed = run_fulltext_index(config, once=True, providers=providers(provider))
    assert fixed['documents'] == 1 and fixed['pending'] == 0 and fixed['error'] is None
    assert len(provider.reads) == 1
    with closing(connect('fulltext.sqlite')) as db:
        retry = db.execute('SELECT * FROM index_retries').fetchone()
        assert retry['resolved_at'] and json.loads(retry['failures'])[0]['legacy']


def test_cli_passes_explicit_retry_only_to_fulltext_index(body_site, monkeypatch, capsys):
    from cirdc.cli import parser
    from cirdc.web.cli import run
    from cirdc.web import fulltext
    args = vars(parser().parse_args(['web', 'fulltext-index', '--once', '--retry-failed']))
    calls = []
    monkeypatch.setattr(fulltext, 'run_fulltext_index', lambda config, **kwargs: calls.append(kwargs) or {})
    assert run(body_site[0], 'fulltext-index', once=args['once'], retry_failed=args['retry_failed']) == 0
    assert calls == [{'max_rows': None, 'once': True, 'retry_failed': True}]
    with pytest.raises(ValueError, match='only supported'):
        run(body_site[0], 'index', retry_failed=True)


def test_budget_counts_failed_reads_and_removed_bodies_are_not_retried(body_site, retry_clock):
    config, _ = body_site
    provider = IncrementalCatalog()
    result = run_fulltext_index(config, max_rows=1, providers=providers(provider))
    assert result['pending'] == 1 and len(provider.reads) == 1
    provider.events.append({'number': '201', 'version': 'v1', 'state': 'unavailable'})
    retry_clock[0] = result['next_retry_at']
    result = run_fulltext_index(config, once=True, providers=providers(provider))
    assert result['pending'] == 0 and result['failed'] == 0 and len(provider.reads) == 1


def test_missing_html_does_not_replace_a_readable_version(body_site, retry_clock, monkeypatch):
    config, _ = body_site
    provider = IncrementalCatalog(); provider.fail = False
    run_fulltext_index(config, once=True, providers=providers(provider))
    provider.events.append({'number': '201', 'version': 'v2', 'state': 'ready'})
    monkeypatch.setattr(provider, 'agent_document', lambda *args: {'version': 'v2', 'state': 'ready'})
    result = run_fulltext_index(config, once=True, providers=providers(provider))
    assert result['pending'] == 1 and result['failed'] == 1
    assert search_body({'q': 'SAR ADC'})['total'] == 1


def test_catalog_crash_after_cursor_commit_leaves_recoverable_work(body_site, monkeypatch):
    from cirdc.web import fulltext
    config, _ = body_site
    provider = IncrementalCatalog(); provider.fail = False
    original = fulltext.index_pending
    def crash(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(fulltext, 'index_pending', crash)
    with pytest.raises(KeyboardInterrupt):
        run_fulltext_index(config, once=True, providers=providers(provider))
    assert not provider.reads and status()['pending'] == 1
    monkeypatch.setattr(fulltext, 'index_pending', original)
    fixed = run_fulltext_index(config, once=True, providers=providers(provider))
    assert fixed['documents'] == 1 and fixed['pending'] == 0 and fixed['error'] is None
