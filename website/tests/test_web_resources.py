import pytest
pytest.importorskip('argon2')
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from cirdc.web.app import create_app
from cirdc.web.resources import ResourceProviders
from test_web import website, signin  # noqa: F401


class Provider:
    def routes(self):
        return [Route('/api/resources/fixture/item', lambda request: JSONResponse({'ok': True}))]

    def links(self, numbers):
        return {n: [{'id': 'fixture', 'href': '/api/resources/fixture/item', 'label': '查看本地资料'}] for n in numbers}


def test_related_reading_requires_login_and_password_change(request):
    config = request.getfixturevalue('website')
    providers = ResourceProviders.__new__(ResourceProviders)
    providers.providers = [Provider()]
    app = create_app(config, resource_providers=providers)
    app.state.accounts.create('alice', 'fixture-original-password')
    with TestClient(app) as client:
        assert client.get('/api/resources/fixture/item').status_code == 401
        signin(client, 'alice', 'fixture-original-password')
        assert client.get('/api/resources/fixture/item').status_code == 403
        app.state.accounts.reset('alice', 'fixture-personal-password', False)
        signin(client, 'alice', 'fixture-personal-password')
        assert client.get('/api/resources/fixture/item').status_code == 200
        value = client.get('/api/papers?q=RF').json()
        assert value['items'][0]['resources'][0]['id'] == 'fixture'


def test_resources_are_disabled_by_default_and_failure_preserves_metadata(request, monkeypatch):
    config = request.getfixturevalue('website')
    monkeypatch.delenv('CIRDC_WEB_RESOURCE_PROVIDERS', raising=False)
    disabled = ResourceProviders(config)
    item = {'number': '123'}
    disabled.attach([item])
    assert 'resources' not in item and not disabled.routes()
    class Broken(Provider):
        def links(self, numbers):
            raise OSError('fixture storage unavailable')
    disabled.providers = [Broken()]
    disabled.attach([item])
    assert item['number'] == '123' and item['resources'] == [] and item['resource_notice']


def test_resource_settings_are_admin_only_and_require_csrf(website):
    class Configurable(Provider):
        identifier='fixture'
        root='/mounted/originals'
        def describe_settings(self):return {'id':self.identifier,'root_dir':self.root,'title':'Storage'}
        def configure(self,values):
            if set(values)!={'root_dir'}:raise ValueError('Unsupported field')
            self.root=values['root_dir'];return self.describe_settings()
    registry=ResourceProviders.__new__(ResourceProviders);registry.providers=[Configurable()]
    admin=create_app(website,interface='admin',resource_providers=registry)
    admin.state.accounts.create('owner','fixture-password','admin');admin.state.accounts.reset('owner','fixture-password',False)
    with TestClient(admin,base_url='http://127.0.0.1:18089') as client:
        assert client.get('/api/admin/resources').status_code==401
        _,headers=signin(client,'owner','fixture-password')
        assert client.get('/api/admin/resources').json()['items'][0]['root_dir']=='/mounted/originals'
        assert client.post('/api/admin/resources/fixture',json={'root_dir':'/new/root'},headers={'Origin':str(client.base_url).rstrip('/')}).status_code==403
        assert client.post('/api/admin/resources/fixture',json={'root_dir':'/new/root'},headers=headers).status_code==200
        assert client.get('/api/admin/audit').json()['items'][0]['action']=='resource_configure'
    reader=create_app(website,resource_providers=registry)
    with TestClient(reader) as client:
        assert client.get('/api/admin/resources').status_code==404
        assert client.post('/api/admin/resources/fixture',json={}).status_code==404
