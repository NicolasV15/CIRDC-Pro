import json
from types import SimpleNamespace
import pymysql
import pytest
from cirdc.author_jobs import Bridge
from cirdc.author_profiles import AuthorError,envelope


@pytest.fixture
def setup_bridge(tmp_path,monkeypatch):
    config=tmp_path/'profile.json';config.write_text(json.dumps({'database_id':'fixture'}))
    state=SimpleNamespace(stores=[],unavailable=False,broken_read=False,broken_write=False,pin='fixture',writes=0)
    class Store:
        def __init__(self,config):
            if state.unavailable:raise pymysql.err.OperationalError(2003,'private diagnostic')
            self.closed=False;self.db=SimpleNamespace(open=True);self.queries=[];state.stores.append(self)
        def execute(self,sql,*args):
            self.queries.append(sql)
            return [{'application':'cirdc-pro','schema_version':4,'instance_id':state.pin}]
        def close(self):self.closed=True;self.db.open=False
    class Repo:
        def __init__(self,store,*args):self.store=store
        def ready(self):pass
        def show(self,aid):
            if state.broken_read:raise pymysql.err.InterfaceError(0,'private diagnostic')
            return {'author_id':aid,'fetched_at':None}
        def _save_validated(self,value):
            state.writes+=1
            if state.broken_write:raise pymysql.err.OperationalError(2013,'commit response lost')
            return {'status':'saved'}
    monkeypatch.setattr('cirdc.author_jobs.Store',Store)
    monkeypatch.setattr('cirdc.author_jobs.AuthorRepository',Repo)
    monkeypatch.setattr('cirdc.author_jobs.Config.load',lambda _:SimpleNamespace(state_dir=tmp_path))
    bridge=Bridge({'config':str(config),'queue':str(tmp_path/'queue.sqlite')})
    yield bridge,state
    bridge.close()


def test_read_after_idle_uses_fresh_connection_and_closes_read_transaction(setup_bridge):
    bridge,state=setup_bridge
    assert all(s.closed for s in state.stores)
    bridge.read('123');first=state.stores[-1]
    bridge.read('123');second=state.stores[-1]
    assert first is not second and first.closed and second.closed
    assert bridge.store is None and bridge.repo is None


def test_health_checks_mysql_and_outage_is_not_reported_as_success(setup_bridge):
    bridge,state=setup_bridge
    assert bridge.heartbeat()['database']['state']=='ready'
    assert 'SELECT 1 AS ready' in state.stores[-1].queries
    state.unavailable=True
    health=bridge.heartbeat()
    assert not health['compatible'] and health['database']['state']=='unavailable'
    assert 'private diagnostic' not in str(health)
    assert bridge.peek()['priority'] is None
    state.unavailable=False
    assert bridge.read('123')['state']=='missing'


def test_broken_read_propagates_once_then_next_request_can_recover(setup_bridge):
    bridge,state=setup_bridge
    state.broken_read=True;before=len(state.stores)
    with pytest.raises(pymysql.err.InterfaceError):bridge.read('123')
    assert len(state.stores)==before+1 and state.stores[-1].closed
    state.broken_read=False
    assert bridge.read('123')['state']=='missing'


def test_identity_change_blocks_reconnection(setup_bridge):
    bridge,state=setup_bridge;state.pin='different'
    with pytest.raises(AuthorError,match='author_database_identity_mismatch'):bridge.read('123')
    assert state.stores[-1].closed


def test_ambiguous_write_is_not_retried_and_job_remains_replayable(setup_bridge):
    bridge,state=setup_bridge
    bridge.queue.enqueue('123');task=bridge.claim()
    value={'records':envelope([{'idStr':'123','preferredName':'Researcher'}],'123')}
    state.broken_write=True
    with pytest.raises(pymysql.err.OperationalError):bridge.apply(task,value)
    assert state.writes==1 and bridge.queue.read('123')['state']=='fetching'
    assert state.stores[-1].closed
    state.broken_write=False
    assert bridge.apply(task,value)['status']=='complete'
    assert state.writes==2 and bridge.queue.read('123')['id']==task['id']
