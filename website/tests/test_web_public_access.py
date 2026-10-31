import pytest
pytest.importorskip('argon2', reason='Install the web extra')
from starlette.testclient import TestClient
from starlette.responses import FileResponse
from starlette.routing import Route
from cirdc.web.app import create_app
from cirdc.web.access import SearchRateLimiter, authentication_required
from test_web import signin
from test_web import website as website


def test_public_session_is_anonymous_without_cookie_or_account_lookup(website, monkeypatch):
    app = create_app(website, reader_auth='public')
    def forbidden(*args):
        raise AssertionError('Public readers must not resolve account cookies')
    monkeypatch.setattr(app.state.accounts, 'session', forbidden)
    with TestClient(app) as client:
        client.cookies.set('cirdc_reader', 'old-or-invalid-cookie')
        r = client.get('/api/auth/session')
        assert r.status_code == 200
        assert r.json()['user'] is None
        assert r.json()['authentication_required'] is False
        assert r.json()['access_mode'] == 'public'
        assert 'set-cookie' not in r.headers
        assert client.get('/api/papers?q=RF&field=title').status_code == 200
        assert client.get('/api/overview').status_code == 200
        assert client.get('/api/authors?q=Alice').status_code == 200


def test_public_reader_rejects_every_account_operation_and_administrator_route(website):
    app = create_app(website, reader_auth='public')
    with TestClient(app) as client:
        for path in ['/api/auth/login', '/api/auth/logout', '/api/auth/password']:
            assert client.post(path, json={}).status_code == 404
            assert client.get(path).status_code == 404
        for path in ['/admin/', '/api/admin/users', '/api/admin/actions/update']:
            assert client.get(path).status_code == 404
            assert client.post(path, json={}).status_code == 404
        for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            r = client.request(method, '/api/papers', json={})
            assert r.status_code == 405
            assert r.headers['allow'] == 'GET, HEAD'


def test_public_resource_streams_support_head_and_byte_ranges(website, tmp_path):
    path = tmp_path / 'fixture.bin'
    path.write_bytes(b'read-only-resource-fixture')
    class Provider:
        def routes(self):
            return [Route('/api/resources/fixture/file', lambda request: FileResponse(path), methods=['GET', 'HEAD'])]
        def attach(self, rows): pass
    app = create_app(website, resource_providers=Provider(), reader_auth='public')
    with TestClient(app) as client:
        assert client.head('/api/resources/fixture/file').status_code == 200
        r = client.get('/api/resources/fixture/file', headers={'Range': 'bytes=0-3'})
        assert r.status_code == 206 and r.content == b'read'
        assert client.post('/api/resources/fixture/file').status_code == 405


def test_requiring_login_again_preserves_accounts_passwords_and_session_workflow(website):
    required = create_app(website, reader_auth='required')
    required.state.accounts.create('alice', 'fixture-reader-password')
    required.state.accounts.reset('alice', 'fixture-reader-password', False)
    with required.state.accounts.db() as db:
        before = db.execute('SELECT password_hash FROM users WHERE username=?', ('alice',)).fetchone()[0]
    with TestClient(required) as client:
        assert client.get('/api/papers?q=RF').status_code == 401
        assert signin(client, 'alice', 'fixture-reader-password')[0].status_code == 200
        token = client.cookies.get('cirdc_reader')
    public = create_app(website, reader_auth='public')
    with TestClient(public) as client:
        client.cookies.set('cirdc_reader', token)
        assert client.get('/api/auth/session').json()['user'] is None
        assert client.get('/api/papers?q=RF').status_code == 200
        assert client.post('/api/auth/password', json={}).status_code == 404
    restored = create_app(website, reader_auth='required')
    with restored.state.accounts.db() as db:
        after = db.execute('SELECT password_hash FROM users WHERE username=?', ('alice',)).fetchone()[0]
    assert before == after
    with TestClient(restored) as client:
        assert client.get('/api/auth/session').json()['authentication_required'] is True
        assert signin(client, 'alice', 'fixture-reader-password')[0].status_code == 200
        assert client.get('/api/papers?q=RF').status_code == 200


def test_administrator_still_requires_login_when_reader_mode_is_public(website, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_READER_AUTH', 'public')
    app = create_app(website, 'admin', reader_auth='public')
    app.state.accounts.create('owner', 'fixture-admin-password', 'admin')
    app.state.accounts.reset('owner', 'fixture-admin-password', False)
    with TestClient(app, base_url='http://127.0.0.1:18089') as client:
        assert client.get('/api/auth/session').json()['authentication_required'] is True
        assert client.get('/api/admin/users').status_code == 401
        assert signin(client, 'owner', 'fixture-admin-password')[0].status_code == 200
        assert client.get('/api/admin/users').status_code == 200
        assert client.post('/api/admin/users/active', json={}).status_code == 403


def test_public_search_uses_actual_peer_ip_and_ignores_forwarding_claims(website):
    app = create_app(website, reader_auth='public')
    with TestClient(app, client=('198.51.100.1', 1000)) as client:
        for i in range(10):
            assert client.get('/api/papers?q=RF', headers={'X-Forwarded-For': f'203.0.113.{i}'}).status_code == 200
        assert client.get('/api/papers?q=RF', headers={'X-Forwarded-For': '203.0.113.99'}).status_code == 429
    with TestClient(app, client=('198.51.100.2', 1000)) as client:
        assert client.get('/api/papers?q=RF').status_code == 200


def test_rate_buckets_are_bounded_and_default_mode_fails_closed(monkeypatch):
    monkeypatch.delenv('CIRDC_WEB_READER_AUTH', raising=False)
    assert authentication_required('reader') is True
    assert authentication_required('admin', 'public') is True
    with pytest.raises(ValueError): authentication_required('reader', 'typo')
    limiter = SearchRateLimiter(limit=2, capacity=2)
    assert limiter.allow('a') and limiter.allow('a')
    assert not limiter.allow('a')
    assert limiter.allow('b') and limiter.allow('c')
    assert len(limiter.entries) == 2


def test_direct_listener_does_not_trust_forwarded_client_addresses(website, monkeypatch):
    import uvicorn
    from cirdc.web.cli import run
    captured={}
    monkeypatch.setattr(uvicorn,'run',lambda app,**kwargs:captured.update(kwargs))
    run(website,'serve',host='127.0.0.1',port=18190)
    assert captured['proxy_headers'] is False
