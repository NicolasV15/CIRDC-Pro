import json
import threading
from dataclasses import replace

import pytest

from cirdc.provider import RequestLimiter, UpstreamError
from cirdc.store import Store, BusyError
from test_engine import setup as setup, run_id


def prepare(ctx, workers=2, budget=None):
    ctx['service']._import({'path': ctx['relative']}, {})
    params = {'stage': 'enrich', 'skip_import': True, 'skip_catalog': True, 'workers': workers}
    if budget:
        params['max_tasks'] = budget
    return run_id(ctx, params)


def document(number):
    return {'articleNumber': number, 'abstract': 'Concurrent result',
            'keywords': {'Author Keywords': [number]}}, {'abstract': 'complete', 'keywords': 'complete'}


def test_fetches_overlap_but_sql_and_shared_file_updates_are_serial(setup, monkeypatch):
    ctx = setup
    run = prepare(ctx)
    coordinator = threading.get_ident()
    seen = set()
    barrier = threading.Barrier(2)
    class Source:
        def document(self, number):
            seen.add(threading.get_ident())
            barrier.wait(timeout=5)
            return document(number)
    ctx['service'].provider = Source()
    execute = ctx['store'].execute
    def main_thread_only(*args, **kwargs):
        assert threading.get_ident() == coordinator
        return execute(*args, **kwargs)
    monkeypatch.setattr(ctx['store'], 'execute', main_thread_only)
    ctx['service'].work(run)
    status = ctx['service'].status(run)
    assert status['status'] == 'completed'
    assert status['counts']['done'] == 2
    assert status['counts']['exports_pending'] == 0
    assert status['stats']['inflight_tasks_peak'] == 2
    assert len(seen) == 2
    rows = json.loads(ctx['config'].destination(ctx['relative']).read_text())
    assert all(r['abstract'] == 'Concurrent result' and r['keywords'] for r in rows)


def test_task_budget_does_not_overclaim_when_workers_exceed_budget(setup):
    ctx = setup
    run = prepare(ctx, workers=4, budget=1)
    class Source:
        def document(self, number):
            return document(number)
    ctx['service'].provider = Source()
    ctx['service'].work(run)
    status = ctx['service'].status(run)
    assert status['status'] == 'paused'
    assert status['counts']['done'] == 1
    assert status['counts']['pending'] == 1
    attempts = ctx['store'].execute('SELECT attempts FROM tasks WHERE run_id=%s ORDER BY id', (run,))
    assert [row['attempts'] for row in attempts] == [1, 0]


def test_access_restriction_drains_inflight_success_without_losing_work(setup):
    ctx = setup
    run = prepare(ctx)
    barrier = threading.Barrier(2)
    class Source:
        def document(self, number):
            barrier.wait(timeout=5)
            if number == ctx['numbers'][0]:
                raise UpstreamError('access_restricted', 'Restricted fixture')
            return document(number)
    ctx['service'].provider = Source()
    ctx['service'].work(run)
    status = ctx['service'].status(run)
    assert status['status'] == 'blocked'
    assert status['counts']['blocked'] == 1
    assert status['counts']['done'] == 1
    assert status['counts']['exports_pending'] == 0
    assert ctx['store'].paper(ctx['numbers'][1])['keywords_state'] == 'complete'


def test_database_lock_is_shared_across_different_client_data_paths(setup):
    ctx = setup
    other = Store(replace(ctx['config'], data_root=ctx['config'].data_root / 'another-client'))
    try:
        with ctx['store'].lock():
            with pytest.raises(BusyError):
                with other.lock():
                    pass
        with other.lock():
            assert other.worker_active()
    finally:
        other.close()


def test_legacy_server_lock_also_prevents_a_new_client_worker(setup):
    ctx = setup
    other = Store(ctx['config'])
    legacy = other.lock_names()[1]
    other.execute('SELECT GET_LOCK(%s,0)', (legacy,))
    try:
        with pytest.raises(BusyError):
            with ctx['store'].lock():
                pass
    finally:
        other.execute('SELECT RELEASE_LOCK(%s)', (legacy,))
        other.close()
    with ctx['store'].lock():
        assert ctx['store'].worker_active()


def test_enrichment_year_scope_excludes_other_years(setup):
    ctx = setup
    ctx['service']._import({'path': ctx['relative']}, {})
    old = {**ctx['rows'][0], 'articleNumber': ctx['numbers'][0] + '99'}
    path = f'articleInfo/Journals/{ctx["publication"]}/2025.json'
    ctx['store'].upsert_records([old], path)
    ctx['store'].db.commit()
    run = run_id(ctx)
    ctx['service']._seed_enrich(run, {'publication': ctx['publication'], 'year': 2026}, {})
    rows = ctx['store'].execute('SELECT task_key FROM tasks WHERE run_id=%s', (run,))
    assert {r['task_key'] for r in rows} == set(ctx['numbers'])


def test_shared_request_budget_serializes_request_start_times():
    from concurrent.futures import ThreadPoolExecutor
    now = [0.0]
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds
    limiter = RequestLimiter(1, clock=lambda: now[0], sleep=sleep)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: limiter.wait(), range(8)))
    assert sleeps == [1.0] * 7
    assert now[0] == 7.0


def test_parallel_coordinator_preserves_future_catalog_deferral(setup):
    from datetime import datetime
    ctx = setup
    future = datetime.now().year + 1
    class Source:
        def publication_year(self, kind, year):
            return []
    ctx['service'].provider = Source()
    run = run_id(ctx, {'stage': 'catalog', 'skip_catalog': True, 'workers': 4})
    ctx['store'].add_tasks(run, 'catalog', [(f'Conferences/{future}', {'kind': 'Conferences', 'year': future})])
    ctx['service'].work(run)
    result = ctx['service'].status(run)
    assert result['status'] == 'partial'
    assert result['counts']['deferred'] == 1
    assert result['counts']['exports_pending'] == 0
    assert not ctx['config'].destination(f'publicationInfo/Conferences/{future}/cirdc.json').exists()
