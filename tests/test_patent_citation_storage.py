import json
from datetime import datetime, timedelta

import pytest

from cirdc import patent_citations as patents
from cirdc.patent_citation_source import fetch_patent_citations
from test_citation_storage import citation_store as citation_store
from test_reference_storage import reference_store as reference_store
from test_engine import setup as setup
from test_patent_citation_source import Source, row, summary


@pytest.fixture
def patent_store(citation_store, monkeypatch):
    # The parent fixture shadows all citation/availability tables as well as
    # core tables. No synthetic observation can reach the real corpus.
    ctx = citation_store
    for name, definition in patents.TABLES.items():
        with ctx['store'].db.cursor() as cursor:
            cursor.execute('CREATE TEMPORARY TABLE '+name+' ('+definition+') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4')
    monkeypatch.setattr(patents, 'check', lambda store: True)
    return ctx


def enqueue(ctx, retry=False):
    n = ctx['numbers'][0];s = ctx['store']
    value = patents.enqueue(s, [n], retry=retry)
    task = s.execute('SELECT t.* FROM tasks t JOIN paper_patent_citation_state p ON p.task_id=t.id WHERE p.number=%s', (n,))[0]
    task['payload'] = json.loads(task['payload'])
    return value, task


def result(ctx, count=2):
    value = fetch_patent_citations(Source([summary(count, [row(i) for i in range(1,count+1)])]), '123')
    value['number'] = ctx['numbers'][0]
    return value


def test_patent_queue_dedup_ttl_versions_and_paper_isolation(patent_store):
    from cirdc import citations
    ctx = patent_store;s = ctx['store'];n = ctx['numbers'][0]
    first, task = enqueue(ctx)
    assert first['queued'] == [n] and enqueue(ctx)[0]['status'] == 'reused'
    assert task['payload']['required_capability'] == 'paper_patent_citations_v1'
    before = citations.read(s, n)
    good = result(ctx);patents.apply_result(s, task, {'records': good})
    assert citations.read(s, n) == before
    page = patents.read(s, n, limit=1)
    assert page['total'] == page['expected_total'] == 2 and page['next_offset'] == 1
    assert patents.read(s, n, offset=1, version=page['version'])['items'][0]['order'] == 2
    assert enqueue(ctx)[0]['status'] == 'reused'
    s.execute('UPDATE paper_patent_citation_state SET next_check_at=UTC_TIMESTAMP()-INTERVAL 1 DAY');s.db.commit()
    assert enqueue(ctx)[0]['queued'] == [n]


def test_failed_update_retains_old_snapshot_and_cools_down(patent_store):
    ctx = patent_store;s = ctx['store'];n = ctx['numbers'][0]
    _, task = enqueue(ctx);good = result(ctx);patents.apply_result(s, task, {'records': good})
    _, new = enqueue(ctx, True);patents.apply_result(s, new, {'error': 'access_restricted'})
    value = patents.read(s, n)
    assert value['state'] == 'blocked' and value['version'] == good['version'] and len(value['items']) == 2
    assert value['stale'] and enqueue(ctx)[0]['status'] == 'reused'
    assert enqueue(ctx, True)[0]['status'] == 'queued'


def test_zero_can_later_receive_patents_and_absence_is_independent(patent_store):
    ctx = patent_store;s = ctx['store'];n = ctx['numbers'][0]
    _, task = enqueue(ctx);patents.apply_result(s, task, {'records': result(ctx, 0)})
    assert patents.read(s, n)['empty_reason'] == 'zero_count'
    _, task = enqueue(ctx, True);patents.apply_result(s, task, {'records': result(ctx, 1)})
    assert patents.read(s, n)['total'] == 1
    rows = s.execute('SELECT direction FROM paper_relationship_availability WHERE number=%s', (n,))
    assert rows == [{'direction': 'patent_citations'}]


def test_publication_replay_recovers_without_extending_ttl(patent_store, monkeypatch):
    ctx = patent_store;s = ctx['store'];n = ctx['numbers'][0]
    _, task = enqueue(ctx);good = result(ctx);publish = patents.publish_exports
    monkeypatch.setattr(patents, 'publish_exports', lambda s: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):patents.apply_result(s, task, {'records': good})
    assert patents.read(s, n)['version'] == good['version']
    next_check = s.execute('SELECT next_check_at FROM paper_patent_citation_state')[0]['next_check_at']
    monkeypatch.setattr(patents, 'publish_exports', publish)
    patents.apply_result(s, task, {'records': good})
    assert s.execute('SELECT next_check_at FROM paper_patent_citation_state')[0]['next_check_at'] == next_check
    assert s.execute("SELECT COUNT(*) n FROM exports WHERE status='pending'")[0]['n'] == 0


def test_partial_refresh_preserves_good_data_and_unknown_is_not_zero(patent_store):
    ctx = patent_store;s = ctx['store'];n = ctx['numbers'][0]
    _, task = enqueue(ctx);unknown = fetch_patent_citations(Source([{}]), '123');unknown['number'] = n
    patents.apply_result(s, task, {'records': unknown})
    value = patents.read(s, n)
    assert value['source_presence'] == 'unknown' and value['expected_total'] is None
    _, task = enqueue(ctx, True);good = result(ctx);patents.apply_result(s, task, {'records': good})
    _, task = enqueue(ctx, True);partial = result(ctx);partial.update(state='partial',error='coverage_incomplete')
    patents.apply_result(s, task, {'records': partial})
    assert patents.read(s, n)['version'] == good['version']
