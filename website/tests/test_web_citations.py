from datetime import datetime,timedelta,timezone
import pytest
from starlette.testclient import TestClient
from cirdc.web.app import create_app
from cirdc.web import paper_citations as api
from test_web import website as website


def view(**kwargs):
    return {'number':'100','state':'complete','version':'a'*32,'group':'ieee','total':5,'expected_total':5,
            'counts':{'ieee':5,'nonIeee':3,'total':8},'stored_counts':{'ieee':5,'nonIeee':3,'total':8},
            'group_states':{'ieee':'complete','nonIeee':'complete'},'source_presence':'present','empty_reason':None,
            'items':[],'offset':0,'limit':50,'next_offset':None,'next_check_at':(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(),**kwargs}


def test_refresh_eligibility_includes_empty_and_failure_cooldown():
    for state in ('complete','no_data','unavailable','blocked','failed','partial'):
        assert not api.due(view(state=state))
        assert api.due(view(state=state),True)
        assert api.due(view(state=state,next_check_at='2020-01-01T00:00:00Z'))
    for state in ('queued','fetching','disabled'):
        assert not api.due(view(state=state),True)
    assert api.due(view(state='missing',next_check_at=None))


def test_api_group_paging_and_same_origin_ensure(website,monkeypatch):
    website.web['citations']={'enabled':True}
    calls=[]
    def read(config,number,group='ieee',offset=0,limit=50,version=None):
        assert number=='100'
        calls.append(('read',group,offset,limit,version));return view(group=group)
    def enqueue(config,number,refresh=False):
        calls.append(('enqueue',number,refresh));return view(state='queued')
    monkeypatch.setattr(api,'read',read);monkeypatch.setattr(api,'enqueue',enqueue)
    with TestClient(create_app(website,reader_auth='public')) as client:
        assert client.get('/api/papers/100/citations?group=nonIeee&offset=2&limit=1&version='+'a'*32).status_code==200
        assert calls[-1]==('read','nonIeee',2,1,'a'*32)
        assert client.post('/api/papers/100/citations/ensure',json={}).status_code==403
        origin={'Origin':'http://testserver'}
        assert client.post('/api/papers/100/citations/ensure',json={},headers=origin).status_code==200
        assert not any(c[0]=='enqueue' for c in calls)
        assert client.post('/api/papers/100/citations/ensure',json={'refresh':True},headers=origin).status_code==202
        assert calls[-1]==('enqueue','100',True)
        assert client.post('/api/papers/100/citations/ensure',json={'refresh':'yes'},headers=origin).status_code==422
    website.web['citations']['enabled']=False
    with TestClient(create_app(website,reader_auth='public')) as client:
        assert client.post('/api/papers/100/citations/ensure',json={},headers={'Origin':'http://testserver'}).status_code==405


def test_read_bridge_filters_private_output_and_preserves_snapshot_parameters(website,monkeypatch):
    website.web['citations']={'enabled':True,'read_command':['maintenance-executable']}
    commands=[]
    def run(command,**kwargs):
        import json
        commands.append(command);return type('Result',(),{'returncode':0,'stdout':json.dumps({**view(),'private_profile':'never expose'})})()
    monkeypatch.setattr(api.subprocess,'run',run)
    result=api.read(website,'100',version='a'*32)
    assert 'private_profile' not in result
    assert commands[0][-2:]==['--version','a'*32]
    assert '--group' in commands[0] and 'shell' not in commands[0]
    with pytest.raises(api.ReferenceError):api.read(website,'100',group='non-ieee')


def test_joint_update_is_one_queue_command_and_keeps_existing_api_contract(website,monkeypatch):
    from cirdc.web import patent_citations
    website.web['citations']={'enabled':True}
    website.web['patent_citations']={'enabled':True}
    queued=[False];commands=[]
    monkeypatch.setattr(api,'read',lambda *args,**kwargs:view(state='queued' if queued[0] else 'complete'))
    monkeypatch.setattr(patent_citations,'read',lambda *args,**kwargs:{**view(state='queued' if queued[0] else 'complete'),'group':'patent'})
    def command(config,setting,args):
        commands.append(args);queued[0]=True
        return {'jobs':[{'id':'1','run_id':'a'*32,'kind':'citations'}]}
    monkeypatch.setattr(api,'call',command)
    with TestClient(create_app(website,reader_auth='public')) as client:
        headers={'Origin':'http://testserver'}
        response=client.post('/api/papers/100/citations/ensure',json={'refresh':True,'include_patents':True},headers=headers)
        assert response.status_code==202 and response.json()['papers']['state']==response.json()['patents']['state']=='queued'
        assert commands==[['enqueue','100','--include-patents','--retry']]
        client.post('/api/papers/100/citations/ensure',json={'refresh':True,'include_patents':True},headers=headers)
        assert len(commands)==1  # Existing joint work is reused.
        assert client.post('/api/papers/100/citations/ensure',json={'include_patents':'yes'},headers=headers).status_code==422
        assert client.post('/api/papers/100/citations/ensure',json={'include_patents':True}).status_code==403


def test_joint_update_busy_response_joins_already_queued_work(website,monkeypatch):
    from cirdc.web import patent_citations
    website.web['citations']={'enabled':True};website.web['patent_citations']={'enabled':True}
    queued=[False]
    monkeypatch.setattr(api,'read',lambda *args,**kwargs:view(state='queued' if queued[0] else 'complete'))
    monkeypatch.setattr(patent_citations,'read',lambda *args,**kwargs:view(state='queued' if queued[0] else 'complete',group='patent'))
    def busy(*args,**kwargs):queued[0]=True;raise api.ReferenceError('worker_busy',409)
    monkeypatch.setattr(api,'call',busy)
    result=api.enqueue_joint(website,'100',True)
    assert result['papers']['state']==result['patents']['state']=='queued'
