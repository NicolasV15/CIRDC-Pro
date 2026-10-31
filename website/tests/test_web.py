from contextlib import closing
import pytest
pytest.importorskip('argon2', reason='Install the web extra to run browser-interface tests')
from starlette.testclient import TestClient
from cirdc.config import Config
from cirdc.web.auth import Accounts
from cirdc.web.app import create_app
from cirdc.web.index import initialize, put_rows, save_meta, search, consume
from cirdc.web.settings import connect
from test_engine import setup  # noqa: F401 - register the existing integration fixture


@pytest.fixture
def website(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'web'))
    with closing(connect('search.sqlite')) as db:
        initialize(db)
        rows = []
        for i in range(9):
            rows.append({'number': str(100+i), 'data': {'articleTitle': 'RF AI 5G study '+str(i),
                 'authors': [{'preferredName': 'Alice Researcher'}], 'abstract': 'UniqueBodyToken analog amplifier',
                 'keywords': {'Author Keywords': ['RingAmp']}, 'publicationYear': '2025', 'publicationNumber': '4',
                 'doi': '' if i == 0 else '10.1234/example'+str(i), 'articleContentType': 'Journals'},
                 'abstract_state': 'complete', 'keywords_state': 'complete'})
        put_rows(db, rows)
        save_meta(db, phase='building', indexed=9)
        db.commit()
    config = Config(tmp_path, tmp_path / 'runtime', {})
    return config


def signin(client, name, password):
    info = client.get('/api/auth/session').json()
    headers = {'Origin': str(client.base_url).rstrip('/'), 'X-CSRF-Token': info['csrf']}
    result = client.post('/api/auth/login', json={'username': name, 'password': password}, headers=headers)
    if result.status_code == 200:
        headers['X-CSRF-Token'] = result.json()['csrf']
    return result, headers


def test_public_app_never_registers_management_routes(website):
    with TestClient(create_app(website)) as client:
        assert client.get('/api/papers').status_code == 401
        assert client.get('/api/admin/users').status_code == 404
        assert client.get('/admin/').status_code == 404
        assert client.get('/healthz').status_code == 200


def test_first_login_requires_change_and_revokes_all_sessions(website):
    app = create_app(website)
    app.state.accounts.create('alice', 'fixture-old-password')
    with TestClient(app) as one, TestClient(app) as two:
        r, h = signin(one, 'alice', 'fixture-old-password')
        assert r.status_code == 200
        signin(two, 'alice', 'fixture-old-password')
        assert one.get('/api/overview').status_code == 403
        assert one.post('/api/auth/password', json={'current_password': 'wrong', 'new_password': 'a-different-password'}, headers=h).status_code == 422
        assert one.post('/api/auth/password', json={'current_password': 'fixture-old-password', 'new_password': 'a-different-password'}, headers=h).status_code == 200
        assert two.get('/api/auth/session').json()['user'] is None
        assert one.get('/api/auth/session').json()['user'] is None
        r, h = signin(one, 'alice', 'a-different-password')
        assert not r.json()['user']['must_change']
        assert one.get('/api/overview').status_code == 200
        assert one.post('/api/auth/logout', json={}, headers=h).status_code == 200
        assert one.get('/api/overview').status_code == 401


def test_csrf_and_admin_sessions_are_separate(website):
    reader, admin = create_app(website), create_app(website, 'admin')
    reader.state.accounts.create('fixture_admin', 'fixture-admin-password', 'admin')
    reader.state.accounts.reset('fixture_admin', 'fixture-admin-password', must_change=False)
    reader.state.accounts.create('alice', 'fixture-reader-password')
    with TestClient(reader, base_url='http://127.0.0.1:18088') as public, TestClient(admin, base_url='http://127.0.0.1:18089') as local:
        _, h = signin(public, 'fixture_admin', 'fixture-admin-password')
        assert public.post('/api/auth/logout', json={}, headers={'Origin':'http://127.0.0.1:18088'}).status_code == 403
        assert public.post('/api/auth/logout', json={}, headers={**h,'Origin':'http://evil.invalid'}).status_code == 403
        local.cookies.update(public.cookies)
        assert local.get('/api/admin/users').status_code == 401
        r, _ = signin(local, 'alice', 'fixture-reader-password')
        assert r.status_code == 401
        r, h = signin(local, 'fixture_admin', 'fixture-admin-password')
        assert r.status_code == 200
        assert local.get('/api/admin/users').status_code == 200
        assert local.post('/api/admin/users/active', json={'username':'alice','active':False}, headers=h).status_code == 200
        assert local.get('/api/admin/audit').json()['items'][0]['action']=='account_disable'
        assert local.get('/api/admin/users', headers={'Host':'example.com'}).status_code == 400


def test_passwords_are_hashed_and_login_throttled(website):
    accounts = Accounts()
    accounts.create('alice','fixture-secret-password')
    with accounts.db() as db:
        value=db.execute('SELECT password_hash FROM users').fetchone()[0]
    assert value.startswith('$argon2id$') and 'fixture-secret-password' not in value
    for _ in range(5):
        with pytest.raises(ValueError):
            accounts.login('alice','wrong','reader','fixture-ip')
    with pytest.raises(PermissionError):
        accounts.login('alice','fixture-secret-password','reader','fixture-ip')


def test_bootstrap_never_resets_existing_account_password(website):
    accounts=Accounts()
    assert accounts.create('alice','fixture-original-password')
    assert accounts.create('alice','fixture-other-password') is False
    token,_=accounts.login('alice','fixture-original-password','reader','fixture-ip')
    assert accounts.session(token,'reader')['must_change'] is True


def test_disk_full_keeps_index_and_checkpoint(website,monkeypatch):
    import cirdc.web.index as module
    import cirdc.store
    import cirdc.web.capture
    from types import SimpleNamespace
    class Source:
        def __init__(self,config): self.db=SimpleNamespace(commit=lambda:None,rollback=lambda:None)
        def migrate(self): pass
        def execute(self,*args): return []
        def close(self): pass
    monkeypatch.setattr(cirdc.store,'Store',Source)
    monkeypatch.setattr(module,'refresh_overview',lambda *args:None)
    monkeypatch.setattr(cirdc.web.capture,'install',lambda *args:None)
    monkeypatch.setattr(cirdc.web.capture,'seed_missed',lambda *args:None)
    monkeypatch.setattr(module.shutil,'disk_usage',lambda *args:SimpleNamespace(free=0))
    with pytest.raises(OSError,match='20 GiB'):
        module.run_index(website,max_rows=1)
    assert len(search({'q':'RF'})['items'])==9
    with closing(connect('search.sqlite')) as db:
        meta=module.metadata(db)
        assert meta['indexed']==9 and meta['error']=='OSError'


def test_fts_short_words_abstract_fields_and_cursor(website):
    for word in ['RF', 'AI', '5G', 'RingAmp']:
        assert len(search({'q':word})['items'])==9
    assert search({'q':'UniqueBodyToken','field':'abstract'})['items']
    assert not search({'q':'UniqueBodyToken','field':'title'})['items']
    assert search({'q':'Alice','field':'authors'})['items']
    assert not search({'q':'RF','year_from':'2026'})['items']
    assert not search({'q':'RF','venue':'999'})['items']
    result=search({'q':'RF','limit':'3'})
    second=search({'q':'RF','limit':'3','cursor':result['next_cursor']})
    assert not {r['number'] for r in result['items']} & {r['number'] for r in second['items']}
    assert result['partial'] is True
    assert search({'q':'10.1234/example1'})['items'][0]['number']=='101'
    assert search({'q':'100'})['items'][0]['doi']==''
    with pytest.raises(ValueError):
        search({'cursor':'not-a-cursor'})


def test_year_browsing_and_field_filters_have_stable_pages(website):
    first=search({'sort':'year','limit':'3'})
    second=search({'sort':'year','limit':'3','cursor':first['next_cursor']})
    assert [p['number'] for p in first['items']]==['108','107','106']
    assert [p['number'] for p in second['items']]==['105','104','103']
    assert not search({'kind':'Journals','keywords_state':'no_data'})['items']
    assert not search({'q':'RF','keywords_state':'no_data'})['items']


def test_shared_query_cache_invalidates_on_committed_changes(website,monkeypatch):
    import concurrent.futures
    import time
    import cirdc.web.index as module
    original=module._search_uncached
    calls=[]
    def counted(params):
        calls.append(1);time.sleep(.05)
        return original(params)
    monkeypatch.setattr(module,'_search_uncached',counted)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        result=list(pool.map(lambda _:module.search({'q':'UniqueBodyToken'}),range(5)))
    assert len(calls)==1 and all(len(r['items'])==9 for r in result)
    with closing(connect('search.sqlite')) as db:
        put_rows(db,[{'number':'100','data':{'articleTitle':'Updated','abstract':'different content'},
                      'abstract_state':'complete','keywords_state':'pending'}]);db.commit()
    assert len(module.search({'q':'UniqueBodyToken'})['items'])==8
    assert len(calls)==2


def test_sqlite_updates_and_rollback_preserve_search_state(website):
    with closing(connect('search.sqlite')) as db:
        row={'number':'100','data':{'articleTitle':'ChangedTitle','authors':[],'abstract':'new content'},
             'abstract_state':'complete','keywords_state':'no_data'}
        put_rows(db,[row]);db.rollback()
        assert len(search({'q':'RF'})['items'])==9
        put_rows(db,[row]);db.commit()
        assert len(search({'q':'RF'})['items'])==8
        assert search({'q':'ChangedTitle'})['items']


def test_conference_series_filter_includes_individual_editions(website):
    with closing(connect('search.sqlite')) as db:
        put_rows(db,[{'number':'999','data':{'articleTitle':'Edition paper', 'publicationNumber':'9272',
                     'articleContentType':'Conferences'},'abstract_state':'pending','keywords_state':'pending'}])
        db.execute('INSERT INTO venue_members VALUES(?,?,?)',('Conferences','1000000','9272'))
        db.commit()
    assert search({'venue':'1000000','kind':'Conferences'})['items'][0]['number']=='999'


def test_journal_filter_keeps_early_access_records(website):
    with closing(connect('search.sqlite')) as db:
        put_rows(db,[{'number':'999','data':{'articleTitle':'Early Access example',
                     'articleContentType':'Early Access Articles'},'abstract_state':'pending','keywords_state':'pending'}])
        put_rows(db,[{'number':'998','data':{'articleTitle':'Magazine example',
                     'articleContentType':'Magazines'},'abstract_state':'pending','keywords_state':'pending'}])
        db.commit()
    assert search({'q':'Early Access','kind':'Journals'})['items'][0]['number']=='999'
    assert search({'q':'Magazine','kind':'Journals'})['items'][0]['number']=='998'


def test_index_ack_failure_and_newer_event_are_recoverable(website):
    class Source:
        class DB:
            def rollback(self): pass
            def commit(self): pass
        db=DB()
        def __init__(self): self.ack_fails=True;self.events=[{'number':'777','token':'old'}]
        def execute(self,sql,params=()):
            if 'web_index_queue' in sql:return list(self.events)
            return [{'number':'777','data':{'articleTitle':'RecoveredDoc'},'abstract_state':'pending','keywords_state':'pending'}]
        def many(self,sql,params):
            if self.ack_fails:raise OSError('Simulated MySQL acknowledgement failure')
            for n,t in params:self.events=[e for e in self.events if (e['number'],e['token'])!=(n,t)]
    store=Source()
    with closing(connect('search.sqlite')) as db:
        with pytest.raises(OSError):consume(store,db)
        assert search({'q':'RecoveredDoc'})['items']
        assert store.events
        store.ack_fails=False
        consume(store,db)
        assert not store.events
        assert len(search({'q':'RecoveredDoc'})['items'])==1


def test_mysql_queue_version_is_atomic_with_record(request):
    ctx=request.getfixturevalue('setup')
    store=ctx['store']
    store.execute("INSERT INTO web_settings(name,value) VALUES('index_enabled','1') ON DUPLICATE KEY UPDATE value='1'")
    store.db.commit()
    row=ctx['rows'][0];number=row['articleNumber']
    try:
        store.upsert_records([row]);store.db.rollback()
        assert not store.execute('SELECT * FROM web_index_queue WHERE number=%s',(number,))
        store.upsert_records([row]);store.db.commit()
        first=store.execute('SELECT token FROM web_index_queue WHERE number=%s',(number,))[0]['token']
        store.update_document(row,{'abstract':'no_data','keywords':'no_data'});store.db.commit()
        second=store.execute('SELECT token FROM web_index_queue WHERE number=%s',(number,))[0]['token']
        assert first!=second
        store.execute('DELETE FROM web_index_queue WHERE number=%s AND token=%s',(number,first));store.db.commit()
        assert store.execute('SELECT * FROM web_index_queue WHERE number=%s',(number,))
    finally:
        store.execute('DELETE FROM web_index_queue WHERE number=%s',(number,))
        store.db.commit()


def test_enrichment_scope_honors_selected_year(request):
    ctx=request.getfixturevalue('setup')
    rows=[{**r,'publicationYear':str(2024+i)} for i,r in enumerate(ctx['rows'])]
    ctx['store'].upsert_records(rows)
    ctx['store'].db.commit()
    run=ctx['store'].create_run({'stage':'enrich','year':2025})
    ctx['runs'].append(run)
    ctx['service']._seed_enrich(run,{'stage':'enrich','year':2025},{})
    assert ctx['store'].counts(run)['pending']==1


def test_duplicate_resume_or_retry_reuses_queued_worker(request,monkeypatch):
    import os
    ctx=request.getfixturevalue('setup')
    run=ctx['store'].create_run({})
    ctx['runs'].append(run)
    calls=[]
    def spawn(identifier):
        calls.append(identifier)
        ctx['store'].set_run(identifier,pid=os.getpid())
    monkeypatch.setattr(ctx['service'],'_spawn',spawn)
    ctx['service'].resume(run)
    result=ctx['service'].resume(run,retry=True)
    assert result['reused'] is True and result['run_id']==run
    assert calls==[run]
