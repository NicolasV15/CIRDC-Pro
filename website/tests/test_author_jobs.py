from cirdc.author_jobs import Queue


def test_foreground_reuses_and_promotes_background(tmp_path):
    q=Queue(tmp_path/'jobs.sqlite')
    one=q.enqueue('123','background');two=q.enqueue('123')
    assert one['id']==two['id'] and two['priority']==0
    task=q.claim();assert task['payload']['attempt']==1
    assert q.claim() is None
    assert q.enqueue('123')['id']==one['id']
    q.db.close()
    recovered=Queue(tmp_path/'jobs.sqlite')
    assert recovered.read('123')['state']=='fetching'
    assert recovered.db.execute('SELECT DISTINCT subject_type FROM author_origins').fetchone()[0]=='author'


def test_pause_and_resume_leave_pending_work(tmp_path):
    q=Queue(tmp_path/'jobs.sqlite');q.enqueue('123');q.control('pause')
    assert q.claim() is None
    q.control('resume');assert q.claim()['task_key']=='123'


def test_bridge_rejects_stale_attempt_and_mismatched_identity(tmp_path):
    import pytest
    from cirdc.author_jobs import Bridge
    from cirdc.author_profiles import envelope,AuthorError
    class Repo:
        def _save_validated(self,value):self.saved=value;return {"status":"saved"}
        def failed(self,*args):self.failure=args
    b=Bridge.__new__(Bridge);b.queue=Queue(tmp_path/'jobs.sqlite');b.repo=Repo()
    b.queue.enqueue('123');task=b.claim()
    good=envelope([{'idStr':'123','preferredName':'Researcher'}],'123')
    bad=envelope([{'idStr':'124','preferredName':'Other'}],'124')
    assert b.apply(task,{'records':bad})['status']=='failed'
    assert not hasattr(b.repo,'saved')
    assert b.queue.read('123')['state']=='failed'
    b.queue.enqueue('123');task=b.claim()
    assert b.apply(task,{'records':good})['status']=='complete'
    assert b.apply(task,{'records':good})['status']=='stale'


def test_public_button_requires_origin_and_get_never_ensures(tmp_path,monkeypatch):
    from starlette.testclient import TestClient
    from cirdc.web.app import create_app
    from cirdc.config import Config
    from cirdc.author_profiles import AuthorRepository
    monkeypatch.setenv('CIRDC_WEB_STATE',str(tmp_path/'web'))
    monkeypatch.setenv('CIRDC_WEB_READER_AUTH','public')
    class Store:
        def __init__(self,*args):pass
        def close(self):pass
        def execute(self,*args):return []
    monkeypatch.setattr('cirdc.web.app.Store',Store)
    monkeypatch.setattr(AuthorRepository,'show',lambda *args,**kwargs:None)
    operations=[]
    def call(config,operation,aid,refresh=False):
        operations.append(operation);return {'state':'queued','id':'job-1','author_id':aid}
    monkeypatch.setattr('cirdc.web.author_acquisition.call',call)
    app=create_app(Config(tmp_path,tmp_path,{}))
    path='/api/author-profiles/ieee/123'
    with TestClient(app) as client:
        assert client.get(path).status_code==200
        assert operations==['read']
        assert client.post(path+'/ensure',json={}).status_code==403
        r=client.post(path+'/ensure',json={'refresh':True},headers={'Origin':'http://testserver'})
        assert r.status_code==202 and r.json()['acquisition']['id']=='job-1'
        assert client.post(path+'/ensure',json={'refresh':'yes'},headers={'Origin':'http://testserver'}).status_code==422


def test_restart_recovers_only_unretained_work(tmp_path):
    from cirdc.author_jobs import Bridge
    b=Bridge.__new__(Bridge);b.settings={'coordinator_state':str(tmp_path)};b.queue=Queue(tmp_path/'authors.sqlite')
    b.inspect=lambda:{'compatible':True}
    b.queue.enqueue('123');b.claim();b.acquire()
    assert b.queue.read('123')['state']=='queued'


def test_background_never_retries_previous_attempt(tmp_path):
    from cirdc.author_jobs import Bridge
    b=Bridge.__new__(Bridge);b.queue=Queue(tmp_path/'authors.sqlite');b.eligible=lambda aid:True
    class Repo:
        def show(self,aid):return None
    b.repo=Repo();b.queue.enqueue('123');task=b.queue.claim()
    with b.queue.db:b.queue.db.execute("UPDATE author_jobs SET state='failed' WHERE id=?",(task['id'],))
    assert b.enqueue('123',trigger='background')['state']=='failed'
    assert b.enqueue('123',refresh=True)['state']=='queued'


def test_curated_discovery_uses_current_index_not_frozen_repair_list(tmp_path):
    import json,sqlite3
    from cirdc.author_jobs import Bridge
    scope=tmp_path/'scope.json';scope.write_text(json.dumps({'families':[{'kind':'Journals','seriesIds':['12']},{'kind':'Conferences','seriesIds':['34']}]}))
    index=tmp_path/'index.sqlite'
    with sqlite3.connect(index) as db:
        db.executescript('CREATE TABLE docs(number TEXT,venue TEXT); CREATE TABLE venue_members(kind TEXT,series TEXT,member TEXT);')
        db.execute("INSERT INTO venue_members VALUES('Conferences','34','35')")
        db.executemany('INSERT INTO docs VALUES(?,?)',[('1','12'),('2','35'),('3','99')])
    b=Bridge.__new__(Bridge);b.settings={'scope_file':str(scope),'index':str(index)}
    assert b.curated_papers()==['1','2']
    with sqlite3.connect(index) as db:db.execute("INSERT INTO docs VALUES('4','12')")
    assert b.curated_papers()==['1','2','4']


def test_concurrent_visitors_create_one_active_job(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path=tmp_path/'jobs.sqlite';Queue(path).db.close()
    def submit(i):
        q=Queue(path)
        try:return q.enqueue('123','manual' if i%2 else 'background')['id']
        finally:q.db.close()
    with ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(submit,range(32)))
    assert len(set(ids))==1
    q=Queue(path)
    assert q.read('123')['priority']==0
    assert q.db.execute('SELECT COUNT(*) FROM author_jobs').fetchone()[0]==1
    q.db.close()
