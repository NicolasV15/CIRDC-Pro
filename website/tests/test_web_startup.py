from contextlib import closing
import json

import pytest
from starlette.testclient import TestClient
from cirdc.web import index
from cirdc.web.app import create_app
from cirdc.web.settings import connect
from test_web import website


@pytest.mark.parametrize('params', [{}, {'q': 'RF'}, {'q': 'UniqueBodyToken', 'field': 'abstract'},
                                 {'field': 'authors', 'q': 'Alice'}, {'venue': '4', 'year_from': '2025'},
                                 {'q': 'missingword'}, {'kind': 'Conferences'}])
def test_deferred_and_count_only_use_the_exact_same_match_set(website, params):
    expected = index.search({**params, 'limit': '3'})
    deferred = index.search({**params, 'limit': '3', 'totals': 'defer'})
    count = index.search({**params, 'totals': 'only'})
    assert deferred['total'] is None
    assert [r['number'] for r in deferred['items']] == [r['number'] for r in expected['items']]
    assert count['total'] == expected['total']
    assert count['items'] == [] and count['next_cursor'] is None
    if expected['next_cursor']:
        second = index.search({**params, 'limit': '3', 'cursor': expected['next_cursor'], 'totals': 'defer'})
        assert len(second['items']) == 3


def test_deferred_page_never_counts_and_count_only_never_reads_a_page(website, monkeypatch):
    queries = []
    original = index.connect
    def traced(name):
        db = original(name)
        db.set_trace_callback(queries.append)
        return db
    monkeypatch.setattr(index, 'connect', traced)
    index.search({'totals': 'defer'})
    assert not any('COUNT(*)' in q.upper() for q in queries)
    queries.clear()
    assert index.search({'totals': 'only'})['total'] == 9
    assert any('COUNT(*)' in q.upper() for q in queries)
    assert not any('WITH HITS AS' in q.upper() for q in queries)


def test_count_cache_ignores_pagination_but_invalidates_on_insert_and_delete(website, monkeypatch):
    calls = []
    original = index._search_uncached
    def counted(params):
        calls.append(params)
        return original(params)
    monkeypatch.setattr(index, '_search_uncached', counted)
    assert index.search({'q': 'RF', 'totals': 'only', 'limit': '25'})['total'] == 9
    assert index.search({'q': 'RF', 'totals': 'only', 'limit': '100', 'cursor': 'ignored', 'sort': 'year'})['total'] == 9
    assert len(calls) == 1
    with closing(connect('search.sqlite')) as db:
        index.put_rows(db, [{'number': '200', 'data': {'articleTitle': 'RF added', 'publicationYear': '2026'},
                             'abstract_state': 'pending', 'keywords_state': 'pending'}])
        db.commit()
    assert index.search({'q': 'RF', 'totals': 'only'})['total'] == 10
    with closing(connect('search.sqlite')) as db:
        db.execute("DELETE FROM docs WHERE number='200'")
        db.commit()
    assert index.search({'q': 'RF', 'totals': 'only'})['total'] == 9
    assert len(calls) == 3


def test_count_only_skips_reading_resources_and_rejects_invalid_queries(website):
    class NoResourceCalls:
        def routes(self): return []
        def attach(self, items): raise AssertionError('Count must not attach resource descriptions')
    with TestClient(create_app(website, reader_auth='public', resource_providers=NoResourceCalls())) as client:
        result = client.get('/api/papers?totals=only').json()
        assert result['total'] == 9 and result['items'] == []
        for query in ['totals=bad', 'totals=only&year_from=2028&year_to=2027',
                      'totals=bad&q=100', 'totals=only&venue_any=bad']:
            assert client.get('/api/papers?' + query).status_code == 422


def test_catalog_cache_compression_revalidation_and_auth_boundary(website, monkeypatch):
    from cirdc.web import app as module
    calls = []
    class Venues:
        def __init__(self, config): pass
        def close(self): pass
        def execute(self, sql):
            assert sql.startswith('SELECT kind,number,data FROM venues')
            calls.append(sql)
            return [{'kind': 'Journals', 'number': str(i), 'data': json.dumps({'title': 'Fixture title ' * 8})} for i in range(100)]
    monkeypatch.setattr(module, 'Store', Venues)
    app = create_app(website, reader_auth='public')
    with TestClient(app) as client:
        raw = client.get('/api/venues', headers={'Accept-Encoding': 'identity'})
        packed = client.get('/api/venues', headers={'Accept-Encoding': 'gzip'})
        assert raw.content == packed.content
        assert packed.headers['content-encoding'] == 'gzip'
        assert int(packed.headers['content-length']) < len(raw.content) / 3
        assert raw.headers['etag'] != packed.headers['etag']
        assert raw.headers['cache-control'] == 'private, max-age=60'
        cached = client.get('/api/venues', headers={'Accept-Encoding': 'gzip', 'If-None-Match': 'W/' + packed.headers['etag']})
        assert cached.status_code == 304 and not cached.content
        assert 'Accept-Encoding' in cached.headers['vary']
        assert len(calls) == 1
    with TestClient(create_app(website, reader_auth='required')) as client:
        denied = client.get('/api/venues', headers={'If-None-Match': raw.headers['etag']})
        assert denied.status_code == 401 and denied.headers['cache-control'] == 'no-store'
        assert len(calls) == 1
