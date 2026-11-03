import asyncio
from contextlib import closing
import json
import sqlite3

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from cirdc.web import task_origins as origins
from cirdc.web.http_cache import PublicTextCompression
from cirdc.web.visits import VisitStore


def records(path):
    with closing(sqlite3.connect(path)) as db:
        requests=db.execute('SELECT id,ip,kind,paper,outcome FROM task_requests ORDER BY ip').fetchall()
        links=db.execute('SELECT request_id,queue,kind,task_id,run_id,binding FROM task_links ORDER BY task_id').fetchall()
    return requests,links


def test_different_hosts_keep_requests_for_same_task_and_ignore_forwarded_header(tmp_path):
    async def endpoint(request):
        return JSONResponse({'number':request.path_params['number'],'state':'queued','job':{'id':'task-1','kind':'opaque_resource'}})
    path=tmp_path/'visits.sqlite';app=Starlette(routes=[Route('/reading/{number}/ensure',endpoint,methods=['POST'])])
    app.add_middleware(origins.TaskSourceRecords,path=path);app.add_middleware(PublicTextCompression)
    for ip in ('198.51.100.20','198.51.100.21'):
        with TestClient(app,client=(ip,1)) as client:
            response=client.post('/reading/100/ensure',json={},headers={'X-Forwarded-For':'203.0.113.99','Cookie':'secret'})
            assert response.status_code==200 and response.json()['job']['id']=='task-1'
            assert 'set-cookie' not in response.headers
    requests,links=records(path)
    assert [r[1] for r in requests]==['198.51.100.20','198.51.100.21']
    assert len({r[0] for r in requests})==2
    assert len(links)==2 and all(r[3]=='task-1' for r in links)
    assert 'secret' not in str(requests)+str(links)


def test_created_run_is_bound_and_changed_reused_task_is_not_guessed():
    context={'kind':'references','paper':'100','created_run':'a'*32}
    before=[{'id':'10','run_id':'b'*32,'kind':'references','paper':'100','state':'running'}]
    after=[{'id':'11','run_id':'a'*32,'kind':'references','paper':'100','state':'done'}]
    links=origins.resolve_links(context,before,after,{'state':'complete'})
    assert len(links)==1 and links[0]['task_id']=='11' and links[0]['binding']=='created_run'
    context.pop('created_run')
    assert origins.resolve_links(context,before,after,{'state':'queued'})==[]
    assert origins.resolve_links(context,before,before,{'state':'queued'})[0]['binding']=='stable_existing'


def test_machine_claims_and_rejected_requests_do_not_become_reader_sources(tmp_path):
    async def claim(request):return JSONResponse({'job':{'id':'task-1','kind':'opaque_resource'}})
    async def rejected(request):return JSONResponse({'error':'denied'},403)
    path=tmp_path/'visits.sqlite';app=Starlette(routes=[Route('/machines/claim',claim,methods=['POST']),Route('/reading/{number}/ensure',rejected,methods=['POST'])]);app.add_middleware(origins.TaskSourceRecords,path=path)
    with TestClient(app,client=('198.51.100.20',1)) as client:
        assert client.post('/machines/claim').status_code==200
        assert client.post('/reading/100/ensure').status_code==403
    assert records(path)==([],[])


def test_database_failure_does_not_change_response_and_app_errors_propagate(tmp_path,monkeypatch):
    async def endpoint(request):return JSONResponse({'number':'100','job':{'id':'task-1','kind':'opaque_resource'}})
    path=tmp_path/'visits.sqlite';app=Starlette(routes=[Route('/reading/{number}/ensure',endpoint,methods=['POST'])]);app.add_middleware(origins.TaskSourceRecords,path=path)
    monkeypatch.setattr(VisitStore,'record_task',lambda *args:(_ for _ in ()).throw(sqlite3.OperationalError('private error')))
    with TestClient(app,client=('198.51.100.20',1)) as client:assert client.post('/reading/100/ensure').json()['job']['id']=='task-1'
    async def failure(scope,receive,send):raise RuntimeError('application error')
    middleware=origins.TaskSourceRecords(failure,tmp_path/'failure.sqlite')
    with pytest.raises(RuntimeError,match='application error'):
        asyncio.run(middleware({'type':'http','method':'POST','path':'/reading/100/ensure','client':('198.51.100.20',1)},None,None))


def test_context_is_isolated_across_concurrent_hosts_and_threadpool(tmp_path,monkeypatch):
    from starlette.concurrency import run_in_threadpool
    path=tmp_path/'visits.sqlite'
    def lookup(command,kind,paper):return [{'id':paper,'run_id':paper.zfill(32),'kind':kind,'paper':paper,'state':'pending'}]
    monkeypatch.setattr(origins,'lookup',lookup)
    async def app(scope,receive,send):
        paper=scope['path'].split('/')[3]
        await asyncio.sleep(.01)
        await run_in_threadpool(origins.note_queue_result,'references',paper,{'run_id':paper.zfill(32),'queued':[paper]})
        await send({'type':'http.response.start','status':202,'headers':[(b'content-type',b'application/json')]})
        await send({'type':'http.response.body','body':json.dumps({'number':paper,'state':'queued'}).encode()})
    middleware=origins.TaskSourceRecords(app,path)
    async def send(message):pass
    async def run():
        await asyncio.gather(*(middleware({'type':'http','method':'POST','path':'/api/papers/'+paper+'/references/ensure','client':(ip,1)},None,send) for paper,ip in [('100','198.51.100.20'),('101','198.51.100.21')]))
    asyncio.run(run());requests,links=records(path)
    assert [(r[1],r[3],r[4]) for r in requests]==[('198.51.100.20','100','created'),('198.51.100.21','101','created')]
    assert {r[3] for r in links}=={'100','101'}
    assert origins.CURRENT.get() is None


def test_linked_subsidiary_tasks_preserve_both_ids_and_reject_wrong_paper():
    value={'number':'100','job':{'id':'body','kind':'body'},'dependency':{'number':'100','job':{'id':'file','kind':'file'}}}
    assert {r['task_id'] for r in origins.response_jobs(value,'100')}=={'body','file'}
    assert origins.response_jobs(value,'101')==[]


def test_unresolved_requests_are_retained_without_attributing_an_execution_task(tmp_path):
    async def endpoint(request):return JSONResponse({'number':'100','state':'queued'})
    path=tmp_path/'visits.sqlite';app=Starlette(routes=[Route('/api/papers/{number}/references/ensure',endpoint,methods=['POST'])]);app.add_middleware(origins.TaskSourceRecords,path=path)
    with TestClient(app,client=('198.51.100.20',1)) as client:assert client.post('/api/papers/100/references/ensure').status_code==200
    requests,links=records(path);assert requests[0][-1]=='unresolved' and not links


def test_metadata_state_response_requires_an_attested_queue_pointer():
    context={'kind':'metadata','paper':'100'}
    after=[{'id':'10','run_id':'a'*32,'kind':'enrich','paper':'100','state':'pending','canonical':True}]
    links=origins.resolve_links(context,[],after,{'job':{'status':'pending'}})
    assert len(links)==1 and links[0]['queue']=='metadata' and links[0]['binding']=='canonical_queue'
    after[0].pop('canonical')
    assert origins.resolve_links(context,[],after,{'job':{'status':'pending'}})==[]


def test_metadata_explicit_identity_is_checked_against_the_resolver():
    context={'kind':'metadata','paper':'100'}
    after=[{'id':'10','run_id':'a'*32,'kind':'enrich','paper':'100','state':'done'}]
    assert origins.resolve_links(context,[],after,{'job':{'id':'11','kind':'enrich'}})==[]
    links=origins.resolve_links(context,[],after,{'job':{'id':'10','run_id':'a'*32}})
    assert len(links)==1 and links[0]['task_id']=='10' and links[0]['queue']=='metadata'
