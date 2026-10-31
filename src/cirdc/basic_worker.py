"""Serial catalog/basic refresh with short shared write transactions."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
import json
import os
import signal
import socket
import time

from .model import digest
from .provider import UpstreamError
from .store import BusyError


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def scope_digest(task):
    payload = {k: v for k, v in task['payload'].items() if k not in ('_source_check', 'result')}
    return digest(canonical({'kind': task['kind'], 'key': task['task_key'], 'payload': payload}))


def reconcile_enrichment(service, own_run):
    """Regenerate committed document exports from SQL before refreshing basic JSON."""
    rows = service.store.execute(
        "SELECT DISTINCT e.run_id,r.params FROM exports e JOIN runs r ON r.id=e.run_id "
        "WHERE e.run_id<>%s AND e.status IN ('pending','dirty')", (own_run,))
    for row in rows:
        params = json.loads(row['params'])
        if params.get('stage') != 'enrich':
            continue
        # Rebuild from canonical records instead of relying on another host's
        # absolute staging path or publishing a stale bibliographic snapshot.
        service.store.execute("UPDATE exports SET status='dirty',error=NULL "
                              "WHERE run_id=%s AND status='pending'", (row['run_id'],))
        service.store.db.commit()
        service.flush_exports(row['run_id'])


def work_metadata(service, run_id):
    from .engine import FutureYearPending, atomic_write
    store = service.store
    run = store.run(run_id)
    params, stats = run['params'], run['stats']
    if params.get('stage') not in ('catalog', 'metadata') or int(params.get('workers', 1)) != 1:
        raise ValueError('Shared basic updates require a catalog/metadata stage and one HTTP worker')
    if params['stage'] == 'metadata' and not params.get('skip_import'):
        raise ValueError('Shared basic updates do not import enrichment from snapshots')
    folder = service.config.state_dir / 'basic-network-cache' / run_id
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    stopping = [False]
    previous = {}
    began = time.monotonic()
    processed = 0

    def heartbeat(phase):
        stats.update(metadata_phase=phase, executor_host=socket.gethostname(), fetch_workers=1,
                     session_seconds=round(time.monotonic() - began, 3),
                     requests=service.request_limiter.snapshot())
        store.set_run(run_id, stats=stats)

    def write_lock():
        while True:
            manager = store.lock()
            try:
                manager.__enter__()
                return manager
            except BusyError:
                heartbeat('waiting_for_shared_writer')
                if stopping[0]:
                    return None
                time.sleep(1)

    def network(task):
        payload = task['payload']
        if task['kind'] == 'catalog':
            return service.provider.publication_year(payload['kind'], payload['year'])
        if task['kind'] == 'early_access':
            return [] if payload.get('result', {}).get('applied') else [service.provider.bibliography(payload['number'])]
        return service.provider.search_all(payload['number'], payload['year'])

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda *_: stopping.__setitem__(0, True))
        with store.lock(service._worker_role(run)), ThreadPoolExecutor(max_workers=1) as pool:
            store.set_run(run_id, status='running', stats=stats, pid=os.getpid(), error='')
            store.execute("UPDATE tasks SET status='pending' WHERE run_id=%s AND status='running'", (run_id,))
            store.db.commit()
            service._seed(run_id, params, stats)
            while not stopping[0]:
                task = store.next_task(run_id, ['catalog'])
                if task is None:
                    heartbeat('seeding_article_partitions')
                    service._seed_fetch(run_id, params, stats)
                    task = store.next_task(run_id, ['fetch'])
                if task is None:
                    heartbeat('seeding_early_access')
                    service._seed_early_access(run_id, params, stats)
                    task = store.next_task(run_id, ['early_access'])
                if task is None:
                    manager = write_lock()
                    if manager is None:
                        break
                    try:
                        reconcile_enrichment(service, run_id)
                        service.flush_exports(run_id)
                    finally:
                        manager.__exit__(None, None, None)
                    counts = store.counts(run_id)
                    stats['enrich_seeded'] = True
                    heartbeat('finished')
                    state = 'partial' if any(counts.get(s) for s in ('failed', 'blocked', 'deferred')) else 'completed'
                    store.set_run(run_id, status=state, stats=stats)
                    return
                store.task_state(task['id'], 'running')
                cache = folder / (str(task['id']) + '.json')
                try:
                    value = json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else None
                    if value and value.get('scope_digest') != scope_digest(task):
                        raise ValueError('Cached network result belongs to a different task scope')
                    if value is None:
                        future = pool.submit(network, task)
                        while True:
                            try:
                                records = future.result(timeout=5)
                                break
                            except TimeoutError:
                                heartbeat('fetching_' + task['kind'])
                        value = {'scope_digest': scope_digest(task), 'records': records,
                                 'fetched_at': datetime.now(timezone.utc).isoformat()}
                        atomic_write(cache, canonical(value))
                    manager = write_lock()
                    if manager is None:
                        store.task_state(task['id'], 'pending')
                        break
                    try:
                        heartbeat('publishing_' + task['kind'])
                        reconcile_enrichment(service, run_id)
                        service.flush_exports(run_id)
                        if task['kind'] == 'catalog':
                            service._catalog(run_id, task['payload'], records=value['records'])
                        elif task['kind'] == 'fetch':
                            service._fetch(run_id, task['payload'], stats, rows=value['records'])
                            if not value['records']:
                                stats['source_empty_partitions'] = stats.get('source_empty_partitions', 0) + 1
                        else:
                            service._refresh_early_access(run_id, task['payload'], stats,
                                                          record=value['records'][0] if value['records'] else None)
                        service.flush_exports(run_id)
                        check = {'fetched_at': value['fetched_at'], 'record_count': len(value['records']),
                                 'records_digest': digest(canonical(value['records']))}
                        payload = {**task['payload'], '_source_check': check}
                        store.execute('UPDATE tasks SET payload=%s WHERE id=%s', (json.dumps(payload), task['id']))
                        store.task_state(task['id'], 'done')
                        cache.unlink(missing_ok=True)
                    finally:
                        manager.__exit__(None, None, None)
                except FutureYearPending as error:
                    store.db.rollback()
                    detail = {**error.detail, 'checked_at': value['fetched_at']}
                    store.task_state(task['id'], 'deferred', json.dumps(detail))
                    stats['future_year_deferrals'] = stats.get('future_year_deferrals', 0) + 1
                    cache.unlink(missing_ok=True)
                except UpstreamError as error:
                    store.db.rollback()
                    blocked = error.code in ('access_restricted', 'network_error')
                    store.task_state(task['id'], 'blocked' if blocked else 'failed', error.code + ': ' + str(error))
                    heartbeat('source_blocked' if blocked else 'source_failed')
                    if blocked:
                        store.set_run(run_id, status='blocked', stats=stats, error=error.code)
                        return
                except ValueError as error:
                    store.db.rollback()
                    store.task_state(task['id'], 'failed', str(error)[:300])
                processed += 1
                heartbeat('checkpoint')
                if params.get('max_tasks') and processed >= params['max_tasks']:
                    break
            store.set_run(run_id, status='paused', stats=stats)
    except Exception as error:
        store.db.rollback()
        store.set_run(run_id, status='blocked', stats=stats,
                      error=type(error).__name__ + ': metadata update interrupted; retained network checkpoints')
        raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if hasattr(service.provider, 'session'):
            service.provider.session.close()
