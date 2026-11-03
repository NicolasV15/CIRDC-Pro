import json
from datetime import datetime,timedelta
import pytest
from cirdc import citations,references
from cirdc.citation_source import fetch_citations
from test_reference_storage import reference_store as reference_store
from test_engine import setup as setup
from test_citation_source import Source,summary


@pytest.fixture
def citation_store(reference_store,monkeypatch):
    ctx=reference_store;s=ctx['store']
    for name,definition in citations.TABLES.items():
        with s.db.cursor() as cursor:cursor.execute('CREATE TEMPORARY TABLE '+name+' ('+definition+') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4')
    monkeypatch.setattr(citations,'check',lambda store:True)
    monkeypatch.setattr(citations,'available',lambda store:True)
    return ctx


def enqueue(ctx,retry=False):
    response=citations.enqueue(ctx['store'],[ctx['numbers'][0]],retry=retry)
    task=ctx['store'].execute('SELECT t.* FROM tasks t JOIN paper_citation_state s ON s.task_id=t.id WHERE s.number=%s',(ctx['numbers'][0],))[0]
    task['payload']=json.loads(task['payload'])
    return response,task


def result(ctx,ieee=2,other=1):
    data=fetch_citations(Source([summary(ieee,other)]),'123');data['number']=ctx['numbers'][0]
    return data


def test_ttl_dedup_group_paging_and_snapshot_integrity(citation_store):
    ctx=citation_store;s=ctx['store'];n=ctx['numbers'][0]
    first,task=enqueue(ctx);assert first['queued']==[n]
    assert enqueue(ctx)[0]['status']=='reused'
    good=result(ctx);citations.apply_result(s,task,{'records':good})
    timestamp=s.execute('SELECT last_attempt_at,next_check_at FROM paper_citation_state')[0]
    citations.apply_result(s,task,{'records':good})
    assert s.execute('SELECT last_attempt_at,next_check_at FROM paper_citation_state')[0]==timestamp
    assert s.execute('SELECT COUNT(*) n FROM paper_citations')[0]['n']==3
    page=citations.read(s,n,group='nonIeee',limit=1)
    assert page['counts']=={'ieee':2,'nonIeee':1,'total':3}
    assert page['total']==1 and page['items'][0]['group']=='nonIeee'
    assert enqueue(ctx)[0]['status']=='reused'
    s.execute('UPDATE paper_citation_state SET next_check_at=UTC_TIMESTAMP()-INTERVAL 1 DAY WHERE number=%s',(n,));s.db.commit()
    assert enqueue(ctx)[0]['status']=='queued'


def test_failed_refresh_preserves_snapshot_and_cools_down(citation_store):
    ctx=citation_store;s=ctx['store'];n=ctx['numbers'][0]
    _,task=enqueue(ctx);good=result(ctx);citations.apply_result(s,task,{'records':good})
    _,again=enqueue(ctx,True);citations.apply_result(s,again,{'error':'access_restricted'})
    page=citations.read(s,n)
    assert page['state']=='blocked' and page['version']==good['version'] and len(page['items'])==2
    assert page['stale'] and enqueue(ctx)[0]['status']=='reused'
    assert enqueue(ctx,True)[0]['status']=='queued'


def test_empty_one_group_and_unknown_other_are_reported_independently(citation_store):
    ctx=citation_store;s=ctx['store'];n=ctx['numbers'][0]
    _,task=enqueue(ctx)
    data=fetch_citations(Source([{'ieeeCitationCount':'0','paperCitations':{'ieee':[]}}]),'123');data['number']=n
    citations.apply_result(s,task,{'records':data})
    page=citations.read(s,n)
    assert page['counts']=={'ieee':0,'nonIeee':None,'total':None}
    assert page['group_states']=={'ieee':'no_data','nonIeee':'unavailable'}
    assert page['state']=='unavailable'


def test_empty_cache_is_rechecked_after_seven_days(citation_store):
    ctx=citation_store;s=ctx['store'];n=ctx['numbers'][0]
    _,task=enqueue(ctx);citations.apply_result(s,task,{'records':result(ctx,0,0)})
    page=citations.read(s,n)
    assert page['state']=='no_data' and page['empty_reason']=='zero_count'
    assert enqueue(ctx)[0]['status']=='reused'
    s.execute('UPDATE paper_citation_state SET next_check_at=UTC_TIMESTAMP()-INTERVAL 1 DAY WHERE number=%s',(n,));s.db.commit()
    _,new=enqueue(ctx);citations.apply_result(s,new,{'records':result(ctx,1,1)})
    assert citations.read(s,n)['counts']['total']==2


def test_partial_refresh_keeps_old_version_and_export_recovery(citation_store,monkeypatch):
    ctx=citation_store;s=ctx['store'];n=ctx['numbers'][0]
    _,task=enqueue(ctx);good=result(ctx);publish=citations.publish_exports
    monkeypatch.setattr(citations,'publish_exports',lambda s:(_ for _ in ()).throw(OSError('storage unavailable')))
    with pytest.raises(OSError):citations.apply_result(s,task,{'records':good})
    assert citations.read(s,n)['version']==good['version']
    monkeypatch.setattr(citations,'publish_exports',publish)
    citations.apply_result(s,task,{'records':good})
    assert s.execute("SELECT COUNT(*) n FROM exports WHERE status='pending'")[0]['n']==0
    _,new=enqueue(ctx,True);partial=result(ctx);partial.update(state='partial',error='coverage_incomplete')
    citations.apply_result(s,new,{'records':partial,'error':'coverage_incomplete'})
    assert citations.read(s,n)['version']==good['version']


def test_legacy_reference_unknown_gets_one_check_without_changing_v1(citation_store):
    ctx=citation_store;s=ctx['store'];n=ctx['numbers'][0]
    references.enqueue(s,[n]);old=s.execute('SELECT task_id FROM paper_reference_state WHERE number=%s',(n,))[0]['task_id']
    s.execute("UPDATE paper_reference_state SET state='unavailable' WHERE number=%s",(n,));s.db.commit()
    view=references.read(s,n);assert view['needs_availability_check']
    references.enqueue(s,[n],check_availability=True)
    task=s.execute('SELECT t.* FROM tasks t JOIN paper_reference_state r ON r.task_id=t.id WHERE r.number=%s',(n,))[0]
    assert task['id']!=old
    data={'number':n,'version':'a'*32,'state':'no_data','items':[],'raw':[],'expected_total':None,'fetched_at':'2026-11-01T00:00:00+00:00','error':None,'source_presence':'absent','empty_reason':'section_absent','evidence':{'section_flag':False}}
    references.apply_result(s,task,{'records':data})
    view=references.read(s,n)
    assert view['source_presence']=='absent' and view['empty_reason']=='section_absent'
    assert not view['needs_availability_check']
    assert references.enqueue(s,[n],check_availability=True)['status']=='reused'
