from contextlib import closing
import pytest
pytest.importorskip('argon2', reason='Install the web extra')
from starlette.testclient import TestClient
from cirdc.web.app import create_app
from cirdc.web.index import save_meta
from cirdc.web.settings import connect
from cirdc.web.resources import ResourceProviders
from test_web import website as website


class Provider:
    identifier='documents'
    def routes(self): return []
    def coverage(self):
        return {'id':'documents','label':'Registered documents','status':'ready','numerator':25,'denominator':50,
                'sampled_at':'2026-10-29T00:00:00Z','configuration_secret':'must-not-be-exposed'}


def test_optional_coverage_extends_only_the_response_not_the_stored_index(website):
    providers=ResourceProviders(website);providers.providers=[Provider()]
    with closing(connect('search.sqlite')) as db:
        save_meta(db,overview={'papers':100,'venues':[],'field_states':[]});db.commit()
    with TestClient(create_app(website,resource_providers=providers,reader_auth='public')) as client:
        r=client.get('/api/overview');assert r.status_code==200
        body=r.json();item=body['overview']['resource_coverage'][0]
        assert item['numerator']==25 and item['denominator']==50 and item['status']=='ready'
        assert 'configuration_secret' not in item
        assert body['index']['overview']==body['overview']
    with closing(connect('search.sqlite')) as db:
        from cirdc.web.index import metadata
        assert 'resource_coverage' not in metadata(db)['overview']


def test_failed_optional_coverage_does_not_replace_a_valid_overview_with_zero(website):
    class Failing(Provider):
        def coverage(self): raise OSError('offline')
    providers=ResourceProviders(website);providers.providers=[Failing()]
    with closing(connect('search.sqlite')) as db:
        save_meta(db,overview={'papers':100,'venues':[],'field_states':[]});db.commit()
    with TestClient(create_app(website,resource_providers=providers,reader_auth='public')) as client:
        body=client.get('/api/overview').json()
        assert body['overview']['papers']==100
        assert body['overview']['resource_coverage'][0]['numerator'] is None
        assert body['overview']['resource_coverage'][0]['status']=='unavailable'
