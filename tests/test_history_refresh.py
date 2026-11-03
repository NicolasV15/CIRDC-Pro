"""History freshness uses successful checks; fixtures shadow all permanent tables."""
from datetime import datetime
import pytest
from test_engine import setup,run_id
from cirdc.provider import UpstreamError


DAY=86400


def shard(ctx,monkeypatch,kind,year):
    service=ctx['service']
    if kind=='Journals':
        path=f'articleInfo/Journals/4/{year}.json'
        indexes={'Journals':{'4':{'start_year':str(year),'end_year':str(year)}},'Conferences':{}}
    else:
        path='articleInfo/Conferences/100/101.json'
        indexes={'Journals':{},'Conferences':{'100':{'titleHistory':[{'publicationNumber':'101','year':str(year)}]}}}
    monkeypatch.setattr(service,'indexes',lambda:indexes)
    monkeypatch.setattr(service.storage,'article_paths',lambda:[])
    return path


def cursor(ctx,path,age):
    store=ctx['store']
    now=int(store.execute('SELECT UNIX_TIMESTAMP() AS now')[0]['now'])
    store.execute('SET timestamp=%s',(now,))
    store.execute('INSERT INTO sync_cursors(path,source_count,checked_at) VALUES(%s,1,FROM_UNIXTIME(%s))',(path,now-age))
    store.db.commit()
    return store.execute('SELECT * FROM sync_cursors WHERE path=%s',(path,))[0]


@pytest.mark.parametrize('kind',['Journals','Conferences'])
@pytest.mark.parametrize('age,due',[(None,True),(0,False),(7*DAY-1,False),(7*DAY,True),(7*DAY+1,True)])
def test_history_seven_day_success_boundary(setup,monkeypatch,kind,age,due):
    c=setup;path=shard(c,monkeypatch,kind,datetime.now().year-4)
    before=None
    if age is not None:
        file=c['config'].destination(path);file.parent.mkdir(parents=True,exist_ok=True);file.write_text('[]')
        before=cursor(c,path,age)
    run=run_id(c,{'stage':'metadata'})
    c['service']._seed_fetch(run,{'stage':'metadata'}, {})
    tasks=c['store'].execute("SELECT task_key FROM tasks WHERE run_id=%s AND kind='fetch'",(run,))
    assert (path in {r['task_key'] for r in tasks})==due
    after=c['store'].execute('SELECT * FROM sync_cursors WHERE path=%s',(path,))
    assert list(after)==([before] if before else [])


@pytest.mark.parametrize('kind',['Journals','Conferences'])
@pytest.mark.parametrize('offset',[-1,0,1])
def test_recent_shards_still_checked_with_fresh_history_cursor(setup,monkeypatch,kind,offset):
    c=setup;path=shard(c,monkeypatch,kind,datetime.now().year+offset)
    cursor(c,path,0)
    run=run_id(c,{'stage':'metadata'})
    c['service']._seed_fetch(run,{'stage':'metadata'}, {})
    assert c['store'].execute("SELECT id FROM tasks WHERE run_id=%s AND kind='fetch' AND task_key=%s",(run,path))


@pytest.mark.parametrize('kind',['Journals','Conferences'])
@pytest.mark.parametrize('code',['access_restricted','coverage_incomplete'])
def test_failed_or_restricted_fetch_does_not_advance_success(setup,monkeypatch,kind,code):
    c=setup;path=shard(c,monkeypatch,kind,datetime.now().year-4)
    before=cursor(c,path,8*DAY)
    class Source:
        def search_all(self,*args):raise UpstreamError(code,'fixture failure')
    c['service'].provider=Source()
    run=run_id(c,{'stage':'metadata'})
    with pytest.raises(UpstreamError):c['service']._fetch(run,{'number':'4','year':2022,'path':path},{})
    assert c['store'].execute('SELECT * FROM sync_cursors WHERE path=%s',(path,))==[before]
