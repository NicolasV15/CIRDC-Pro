import json
from contextlib import ExitStack

import pytest

from cirdc import references
from cirdc.reference_source import fetch_references
from cirdc.engine import require_maintenance_scope
from test_engine import setup as setup
from test_reference_source import Source, page, row


@pytest.fixture
def reference_store(setup, monkeypatch):
    from cirdc import citations
    monkeypatch.setattr(citations, 'available', lambda store: False)
    store = setup['store']
    for name, (_, definition) in references.TABLES.items():
        with store.db.cursor() as cursor:
            cursor.execute('CREATE TEMPORARY TABLE ' + name + ' (' + definition + ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4')
    monkeypatch.setattr(references, 'check', lambda store: True)
    store.upsert_records(setup['rows'])
    store.db.commit()
    return setup


def make_task(ctx, retry=False):
    store, number = ctx['store'], ctx['numbers'][0]
    response = references.enqueue(store, [number], retry=retry)
    task = store.execute('SELECT t.* FROM tasks t JOIN paper_reference_state s ON s.task_id=t.id WHERE s.number=%s', (number,))[0]
    task['payload'] = json.loads(task['payload'])
    return response, task


def result_for(ctx):
    result = fetch_references(Source([page([row(1)])], 1), '123')
    result['number'] = ctx['numbers'][0]
    return result


def test_enqueue_is_idempotent_and_no_missing_paper_import(reference_store):
    ctx = reference_store
    first, task = make_task(ctx)
    second, again = make_task(ctx)
    assert first['status'] == 'queued' and second['status'] == 'reused'
    assert task['id'] == again['id']
    assert ctx['store'].execute('SELECT COUNT(*) n FROM runs')[0]['n'] == 1
    assert ctx['store'].execute('SELECT status FROM runs')[0]['status'] == 'references_pending'
    with pytest.raises(ValueError, match='explicit references queue'):
        require_maintenance_scope({'stage': 'references'})
    with pytest.raises(ValueError, match='paper_not_found'):
        references.enqueue(ctx['store'], ['123456789'])
    with pytest.raises(ValueError, match='20 explicit'):
        references.enqueue(ctx['store'], [str(i) for i in range(21)])


def test_snapshot_replay_is_idempotent_and_failure_preserves_good_data(reference_store):
    ctx = reference_store
    _, task = make_task(ctx)
    result = result_for(ctx)
    references.apply_result(ctx['store'], task, {'records': result})
    references.apply_result(ctx['store'], task, {'records': result})
    store = ctx['store']
    assert store.execute('SELECT COUNT(*) n FROM paper_references')[0]['n'] == 1
    assert len(list(ctx['config'].data_root.rglob('referenceInfo/*/*.json'))) == 1
    _, retry_task = make_task(ctx, retry=True)
    references.apply_result(store, retry_task, {'error': 'access_restricted'})
    state = store.execute('SELECT * FROM paper_reference_state')[0]
    assert state['state'] == 'blocked' and state['version'] == result['version'] and state['total'] == 1
    assert make_task(ctx)[0]['status'] == 'reused'


def test_sql_commit_survives_export_failure_and_replay(reference_store, monkeypatch):
    ctx = reference_store
    _, task = make_task(ctx)
    result = result_for(ctx)
    original = references.publish_exports
    monkeypatch.setattr(references, 'publish_exports', lambda store: (_ for _ in ()).throw(OSError('unavailable storage')))
    with pytest.raises(OSError):
        references.apply_result(ctx['store'], task, {'records': result})
    assert ctx['store'].execute('SELECT total FROM paper_reference_state')[0]['total'] == 1
    assert ctx['store'].execute("SELECT COUNT(*) n FROM exports WHERE status='pending'")[0]['n'] == 1
    monkeypatch.setattr(references, 'publish_exports', original)
    references.apply_result(ctx['store'], task, {'records': result})
    assert ctx['store'].execute("SELECT COUNT(*) n FROM exports WHERE status='pending'")[0]['n'] == 0
    assert ctx['store'].execute('SELECT COUNT(*) n FROM paper_reference_snapshots')[0]['n'] == 1


def test_partial_journal_result_is_saved_without_replacing_complete_version(reference_store):
    ctx = reference_store
    _, task = make_task(ctx)
    good = result_for(ctx)
    references.apply_result(ctx['store'], task, {'records': good})
    _, again = make_task(ctx, retry=True)
    partial = result_for(ctx)
    partial.update(state='partial', error='coverage_incomplete')
    references.apply_result(ctx['store'], again, {'records': partial, 'error': 'coverage_incomplete'})
    state = ctx['store'].execute('SELECT * FROM paper_reference_state')[0]
    assert state['state'] == 'partial' and state['version'] == good['version']
    assert ctx['store'].execute('SELECT COUNT(*) n FROM paper_reference_snapshots')[0]['n'] == 2
    view = references.read(ctx['store'], ctx['numbers'][0], version=good['version'], order=1)
    assert view['item']['order'] == 1
    with pytest.raises(references.ReferenceReadError, match='reference_version_not_found'):
        references.read(ctx['store'], ctx['numbers'][0], version='f' * 32)


def test_abandoned_reference_claim_recovers_without_resetting_other_tasks(reference_store):
    ctx = reference_store
    _, task = make_task(ctx)
    store = ctx['store']
    other = store.create_run({'stage': 'enrich'})
    store.add_tasks(other, 'enrich', [('other-article', {'number': '999'})])
    def adapter():
        bridge = references.ReferenceBridge.__new__(references.ReferenceBridge)
        bridge.store, bridge.stack, bridge.active = store, ExitStack(), False
        return bridge
    first = adapter()
    first.acquire()
    claimed = first.claim()
    assert claimed['id'] == task['id']
    first.stack.close()
    second = adapter()
    try:
        second.acquire()
        restored = second.claim()
        assert restored['id'] == task['id']
        assert store.execute('SELECT status FROM tasks WHERE run_id=%s', (other,))[0]['status'] == 'pending'
    finally:
        second.stack.close()
