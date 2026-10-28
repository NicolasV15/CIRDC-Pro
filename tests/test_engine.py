import json
import os
import uuid
import pytest
from cirdc.config import Config
from cirdc.engine import Service
from cirdc.store import Store
from cirdc.provider import UpstreamError


@pytest.fixture
def setup(tmp_path):
    if os.environ.get('CIRDC_INTEGRATION') != '1':
        pytest.skip('Set CIRDC_INTEGRATION=1 for the configured dedicated database')
    current = Config.load()
    c = Config(tmp_path / 'collection', tmp_path / 'state', current.mysql)
    c.data_root.mkdir()
    s = Store(c)
    # Connection-local tables isolate fixtures from the existing metadata corpus and jobs.
    for table in ['schema_migrations', 'venues', 'papers', 'paper_files', 'manifests',
                  'sync_cursors', 'runs', 'tasks', 'exports', 'cirdc_identity']:
        definition = s.execute('SHOW CREATE TABLE ' + table)[0]['Create Table']
        with s.db.cursor() as cursor:
            cursor.execute(definition.replace('CREATE TABLE', 'CREATE TEMPORARY TABLE', 1))
    s.migrate()
    token = str(int(uuid.uuid4().hex[:12], 16))
    numbers = ['99000000' + token + str(i) for i in range(2)]
    publication = '88000000' + token
    relative = f'articleInfo/Journals/{publication}/2026.json'
    path = c.destination(relative)
    path.parent.mkdir(parents=True)
    rows = [{'articleNumber': n, 'doi': '', 'abstract': '', 'keywords': {},
             'articleTitle': 'Synthetic metadata fixture'} for n in numbers]
    path.write_text(json.dumps(rows))
    index = c.data_root / 'publicationInfo';index.mkdir()
    (index / 'all_journals.json').write_text(json.dumps({publication: {'title': 'Synthetic venue',
                                                                 'start_year': '2026', 'end_year': 'Present'}}))
    (index / 'all_conferences.json').write_text('{}')
    service = Service(c, store=s)
    context = {'config': c, 'store': s, 'service': service, 'rows': rows,
               'numbers': numbers, 'relative': relative, 'publication': publication, 'runs': []}
    yield context
    # All test tables are connection-local, including deliberately malformed schemas.
    s.close()


def run_id(ctx, params=None):
    n = ctx['store'].create_run(params or {})
    ctx['runs'].append(n)
    return n


def test_reimport_is_idempotent_and_empty_doi_not_identity(setup):
    c = setup
    stats = {}
    c['service']._import({'path': c['relative']}, stats)
    c['service']._import({'path': c['relative']}, stats)
    assert stats == {'files_imported': 1, 'records_imported': 2, 'files_skipped': 1}
    assert all(c['store'].paper(n) for n in c['numbers'])


def test_empty_existing_fields_are_scheduled(setup):
    c = setup
    c['service']._import({'path': c['relative']}, {})
    n = run_id(c)
    c['service']._seed_enrich(n, {}, {})
    assert c['store'].counts(n)['pending'] == 2


def test_confirmed_absence_is_not_requeued(setup):
    c = setup
    c['service']._import({'path': c['relative']}, {})
    for n in c['numbers']:
        c['store'].update_document({'articleNumber': n}, {'abstract': 'no_data', 'keywords': 'no_data'})
    c['store'].db.commit()
    n = run_id(c)
    c['service']._seed_enrich(n, {}, {})
    assert c['store'].counts(n)['total'] == 0


def test_missing_page_preserves_old_snapshot(setup):
    c = setup
    n = run_id(c)
    old = c['config'].destination(c['relative']).read_bytes()
    class BadSource:
        def search_all(self, *args):
            raise UpstreamError('coverage_incomplete', 'missing page')
    c['service'].provider = BadSource()
    with pytest.raises(UpstreamError):
        c['service']._fetch(n, {'number': c['publication'], 'year': 2026, 'path': c['relative']}, {})
    assert c['config'].destination(c['relative']).read_bytes() == old
    assert c['store'].counts(n)['exports_pending'] == 0


def test_export_failure_recovers_without_losing_database_progress(setup, monkeypatch):
    c = setup
    n = run_id(c)
    values = [{**r, 'abstract': 'Updated'} for r in c['rows']]
    c['store'].upsert_records(values, c['relative'])
    c['store'].stage_export(n, c['relative'], values)
    c['store'].db.commit()
    old = c['config'].destination(c['relative']).read_bytes()
    import cirdc.engine as module
    real_write = module.atomic_write
    monkeypatch.setattr(module, 'atomic_write', lambda *a: (_ for _ in ()).throw(OSError('disk unavailable')))
    with pytest.raises(OSError):
        c['service'].flush_exports(n)
    assert c['store'].paper(c['numbers'][0])['record']['abstract'] == 'Updated'
    assert c['config'].destination(c['relative']).read_bytes() == old
    assert c['store'].counts(n)['exports_pending'] == 1
    monkeypatch.setattr(module, 'atomic_write', real_write)
    c['service'].flush_exports(n)
    assert c['store'].counts(n)['exports_pending'] == 0
    assert json.loads(c['config'].destination(c['relative']).read_text())[0]['abstract'] == 'Updated'
    assert (c['config'].state_dir / 'backups' / n / c['relative']).read_bytes() == old


def test_database_rollback_cannot_publish_staged_content(setup):
    c = setup
    n = run_id(c)
    old = c['config'].destination(c['relative']).read_bytes()
    c['store'].stage_export(n, c['relative'], [])
    c['store'].db.rollback()
    c['service'].flush_exports(n)
    assert c['config'].destination(c['relative']).read_bytes() == old


def test_two_agent_connections_share_one_worker_lock(setup):
    c = setup
    other = Store(c['config'])
    try:
        with c['store'].lock():
            with pytest.raises(RuntimeError, match='Another'):
                with other.lock():
                    pass
    finally:
        other.close()


def test_same_scope_reuses_queued_job(setup, monkeypatch):
    c = setup
    monkeypatch.setattr(c['service'], '_spawn', lambda *args: None)
    first = c['service'].start({'publication': c['publication']})
    c['runs'].append(first['run_id'])
    second = c['service'].start({'publication': c['publication']})
    assert second['reused'] is True
    assert first['run_id'] == second['run_id']
    with pytest.raises(RuntimeError, match='different update scope'):
        c['service'].start({'publication': '999999'})


def test_pause_resume_and_enrichment_preserve_progress(setup):
    c = setup
    class Source:
        def document(self, number):
            return {'articleNumber': number, 'abstract': 'Verified', 'keywords': {'Author Keywords': ['x']}}, {
                'abstract': 'complete', 'keywords': 'complete'}
    c['service'].provider = Source()
    n = run_id(c, {'stage': 'enrich', 'max_tasks': 1})
    c['service'].work(n)
    assert c['store'].run(n)['status'] == 'paused'
    for _ in range(4):
        if c['store'].run(n)['status'] == 'completed':
            break
        c['service'].resume(n, foreground=True)
    assert c['store'].run(n)['status'] == 'completed'
    assert c['store'].counts(n)['done'] == 3
    assert all(c['store'].paper(x)['keywords_state'] == 'complete' for x in c['numbers'])


def test_interrupted_running_task_is_recovered(setup):
    c = setup
    n = run_id(c, {'stage': 'catalog', 'skip_catalog': True})
    c['store'].add_tasks(n, 'import', [(c['relative'], {'path': c['relative']})])
    task = c['store'].next_task(n)
    c['store'].task_state(task['id'], 'running')
    c['service'].resume(n, foreground=True)
    assert c['store'].counts(n)['done'] == 1
