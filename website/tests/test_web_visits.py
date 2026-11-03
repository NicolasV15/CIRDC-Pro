import asyncio
import sqlite3

from cirdc.web.visits import ReaderVisitRecords,VisitStore,client_address,tracked_request
from test_web import website as website


def scope(path='/',ip='198.51.100.20',method='GET',headers=None):
    return {'type':'http','method':method,'path':path,'client':(ip,12345),'headers':headers or []}


def test_address_is_real_peer_not_forwarded_or_http_host():
    request=scope(headers=[(b'x-forwarded-for',b'203.0.113.55'),(b'host',b'client.example.invalid'),(b'cookie',b'private')])
    assert client_address(request)=='198.51.100.20'
    assert client_address(scope(ip='::ffff:198.51.100.20'))=='198.51.100.20'
    assert client_address({'client':None}) is None


def test_reader_requests_exclude_health_assets_nodes_and_our_directory_probe():
    for path in ('/','/papers/100','/api/papers','/api/papers/100','/api/overview','/authors/ieee/100'):
        assert tracked_request(scope(path))
    for path in ('/healthz','/assets/app.js','/api/content-nodes/claim','/admin/','/not-a-route'):
        assert not tracked_request(scope(path))
    assert not tracked_request(scope(method='POST'))
    assert not tracked_request(scope(headers=[(b'user-agent',b'Example-Monitor/1.0 (local service inventory)')]))


def test_store_retains_first_last_and_request_count_without_headers_or_queries(tmp_path):
    store=VisitStore(tmp_path/'visitors.sqlite')
    store.record('198.51.100.20',20);store.record('198.51.100.20',10);store.record('198.51.100.20',30)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT ip,first_seen,last_seen,requests FROM visitors').fetchone()==('198.51.100.20',10,30,3)
        assert [r[1] for r in db.execute('PRAGMA table_info(visitors)')]==['ip','first_seen','last_seen','requests']


def test_response_stream_and_anonymous_cookie_behavior_are_unchanged(tmp_path):
    async def app(request,receive,send):
        await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'text/plain')]})
        await send({'type':'http.response.body','body':b'hello','more_body':True})
        await send({'type':'http.response.body','body':b'world','more_body':False})
    middleware=ReaderVisitRecords(app,tmp_path/'visitors.sqlite');messages=[]
    async def receive():return {'type':'http.request','body':b''}
    async def send(value):messages.append(value)
    asyncio.run(middleware(scope(headers=[(b'cookie',b'private')]),receive,send))
    assert [m.get('body') for m in messages[1:]]==[b'hello',b'world']
    assert not any(name==b'set-cookie' for name,value in messages[0]['headers'])
    with sqlite3.connect(middleware.store.path) as db:assert db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]==1


def test_recording_failure_does_not_change_reader_response(tmp_path,monkeypatch):
    async def app(request,receive,send):await send({'type':'http.response.start','status':200,'headers':[]});await send({'type':'http.response.body','body':b'ok'})
    middleware=ReaderVisitRecords(app,tmp_path/'visitors.sqlite')
    monkeypatch.setattr(middleware.store,'record',lambda *args:(_ for _ in ()).throw(sqlite3.OperationalError('private path')))
    messages=[]
    async def send(value):messages.append(value)
    asyncio.run(middleware(scope(),None,send))
    assert messages[-1]['body']==b'ok'


def test_public_reader_integration_is_opt_in_and_does_not_add_account_login(website,tmp_path,monkeypatch):
    from starlette.testclient import TestClient
    from cirdc.web.app import create_app
    path=tmp_path/'visitors.sqlite';monkeypatch.setenv('CIRDC_WEB_VISITS_FILE',str(path))
    with TestClient(create_app(website,reader_auth='public'),client=('198.51.100.20',1234)) as client:
        response=client.get('/api/overview',headers={'X-Forwarded-For':'203.0.113.55'})
        assert response.status_code==200
        assert 'set-cookie' not in response.headers
        assert client.get('/api/auth/session').json()['user'] is None
    with sqlite3.connect(path) as db:assert db.execute('SELECT ip FROM visitors').fetchall()==[('198.51.100.20',)]


def test_monitor_can_read_closed_store_with_no_directory_or_file_write_permission(tmp_path):
    from contextlib import closing
    path=tmp_path/'visitors.sqlite'
    store=VisitStore(path);store.record('198.51.100.20',30)
    path.chmod(0o400);tmp_path.chmod(0o500)
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            assert db.execute('SELECT ip,requests FROM visitors').fetchall()==[('198.51.100.20',1)]
        assert sorted(p.name for p in tmp_path.iterdir())==['visitors.sqlite']
    finally:
        tmp_path.chmod(0o700);path.chmod(0o600)
