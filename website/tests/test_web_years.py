from contextlib import closing

import pytest

pytest.importorskip('argon2', reason='Install the web extra')
from starlette.testclient import TestClient
from cirdc.web.app import create_app
from cirdc.web.index import metadata, put_rows, search
from cirdc.web.settings import connect
from test_web import website as website


def add_year(db, number, year):
    put_rows(db, [{'number': number, 'data': {'articleTitle': 'Year fixture', 'publicationYear': year},
                   'abstract_state': 'complete', 'keywords_state': 'complete'}])
    db.commit()


def test_overview_tracks_future_publication_years_without_rebuilding_or_rewriting_metadata(website):
    with closing(connect('search.sqlite')) as db:
        original = metadata(db)
    with TestClient(create_app(website, reader_auth='public')) as client:
        assert client.get('/api/overview').json()['index']['year_range'] == {'min': 2025, 'max': 2025}
        for year in (2027, 2028):
            with closing(connect('search.sqlite')) as db:
                add_year(db, str(year), str(year))
            response = client.get('/api/overview')
            assert response.status_code == 200
            assert response.json()['index']['year_range'] == {'min': 2025, 'max': year}
    with closing(connect('search.sqlite')) as db:
        assert metadata(db) == original


def test_overview_ignores_missing_and_out_of_range_years(website):
    with closing(connect('search.sqlite')) as db:
        db.execute('DELETE FROM docs')
        for i, year in enumerate(('', '1799', '2201')):
            add_year(db, str(3000 + i), year)
    with TestClient(create_app(website, reader_auth='public')) as client:
        assert client.get('/api/overview').json()['index']['year_range'] == {'min': None, 'max': None}
        with closing(connect('search.sqlite')) as db:
            add_year(db, '4000', '1800')
            add_year(db, '4001', '2200')
        assert client.get('/api/overview').json()['index']['year_range'] == {'min': 1800, 'max': 2200}


@pytest.mark.parametrize('query', ['', '100'])
def test_inverted_year_range_is_rejected_before_search_or_direct_database_lookup(website, monkeypatch, query):
    def unexpected_lookup(*args, **kwargs):
        raise AssertionError('Invalid year range must be rejected before database lookup')

    monkeypatch.setattr('cirdc.web.app.Store', unexpected_lookup)
    with TestClient(create_app(website, reader_auth='public')) as client:
        result = client.get('/api/papers', params={'q': query, 'year_from': '2027', 'year_to': '2025'})
        assert result.status_code == 422
        assert result.json()['error'] == 'invalid_query'


def test_index_search_rejects_inverted_year_range(website):
    with pytest.raises(ValueError, match='Start year'):
        search({'year_from': '2027', 'year_to': '2025'})


@pytest.mark.parametrize('bounds', [
    {'year_from': '2025', 'year_to': '2025'},
    {'year_from': '2025'},
    {'year_to': '2025'},
    {},
])
def test_same_year_and_unlimited_bounds_remain_valid(website, bounds):
    assert len(search(bounds)['items']) == 9
