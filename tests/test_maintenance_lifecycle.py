import asyncio
import importlib.util

import pytest

from cirdc.api import invoke
from cirdc.cli import parser
from cirdc.engine import Service, require_maintenance_scope
from cirdc.mcp_server import server
from test_engine import setup as setup, run_id


@pytest.mark.parametrize('module', ['collector', 'cooperation', 'selection', 'monitor'])
def test_historical_modules_are_not_installed(module):
    assert importlib.util.find_spec('cirdc.' + module) is None


@pytest.mark.parametrize('command', ['distribute', 'collect', 'apply-collected',
                                      'collector-status', 'collector-watch'])
def test_historical_commands_are_rejected_by_cli_and_api(command, monkeypatch):
    with pytest.raises(SystemExit):
        parser().parse_args([command])
    def unexpected_store(*args, **kwargs):
        raise AssertionError('An unsupported operation must not open the database')
    monkeypatch.setattr('cirdc.api.Store', unexpected_store)
    result = invoke(command)
    assert result['status'] == 'error' and result['error_type'] == 'ValueError'


@pytest.mark.parametrize('params', [{'article_list': 'old-selection.txt'},
                                    {'refresh_existing': True},
                                    {'mode': 'distributed_collection'},
                                    {'manifest': 'old-manifest.json'}])
def test_selection_requests_cannot_turn_into_broader_maintenance(params):
    with pytest.raises(ValueError, match='frozen runtime'):
        require_maintenance_scope(params)
    service = Service.__new__(Service)
    with pytest.raises(ValueError, match='frozen runtime'):
        service.plan(params)
    with pytest.raises(ValueError, match='frozen runtime'):
        service.start(params)


def test_mcp_schemas_do_not_advertise_historical_selection():
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools}.isdisjoint(
        {'prepare_collection', 'collect_shard', 'apply_collection', 'collector_status'})
    for tool in tools:
        assert {'article_list', 'refresh_existing'}.isdisjoint(
            tool.inputSchema.get('properties', {}))


def test_existing_repair_cannot_be_resumed_or_modified_by_maintenance(setup):
    ctx = setup
    job = run_id(ctx, {'mode': 'distributed_collection', 'stage': 'enrich'})
    ctx['store'].set_run(job, status='collecting')
    before = ctx['store'].run(job)
    with pytest.raises(ValueError, match='frozen runtime'):
        ctx['service'].resume(job, workers=4, max_tasks=1)
    after = ctx['store'].run(job)
    assert after['params'] == before['params']
    assert after['status'] == before['status']
    assert ctx['store'].counts(job)['total'] == 0


def test_deferred_catalog_work_does_not_become_completed(setup):
    ctx = setup
    params = {'stage': 'metadata', 'workers': 1, 'skip_import': True,
              'skip_catalog': True, 'cooperative_writes': True}
    job = run_id(ctx, params)
    stats = {key: True for key in ('import_seeded', 'catalog_seeded', 'fetch_seeded',
                                   'early_access_seeded', 'enrich_seeded')}
    ctx['store'].set_run(job, stats=stats)
    ctx['store'].add_tasks(job, 'catalog', [('future', {'kind': 'Journals', 'year': 9999})])
    task = ctx['store'].next_task(job)
    ctx['store'].task_state(task['id'], 'deferred', 'confirmed future absence')
    ctx['service'].work(job)
    assert ctx['store'].run(job)['status'] == 'partial'
    assert ctx['store'].counts(job)['deferred'] == 1


def test_runtime_imports_do_not_depend_on_retired_modules():
    import ast
    import cirdc
    from pathlib import Path
    phase = {'collector', 'cooperation', 'selection', 'monitor'}
    for path in Path(cirdc.__file__).parent.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level and node.module:
                assert node.module.split('.')[0] not in phase, str(path)


def test_windows_forwarding_keeps_its_private_marker_without_repair_dependency(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from cirdc.ssh import SSH
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    replies = iter([False, True])
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def connect(*args, **kwargs):
        if not next(replies): raise OSError('not listening yet')
        return Connection()
    monkeypatch.setattr('cirdc.ssh.socket.create_connection', connect)
    monkeypatch.setattr('cirdc.ssh.subprocess.Popen', lambda *a, **k:
                        SimpleNamespace(pid=12345, poll=lambda: None))
    channel = SSH('fixture-server', {'local_port': 43307})
    channel._windows_forward()
    marker = channel.control.with_suffix('.forward.json')
    assert json.loads(marker.read_text()) == {'target': str(channel.control), 'pid': 12345}
    assert marker.stat().st_mode & 0o777 == 0o600
