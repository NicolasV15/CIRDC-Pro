import json
from datetime import datetime

import pytest
from starlette.testclient import TestClient

from cirdc.web import references
from cirdc.web.app import create_app
from test_web import website as website


@pytest.fixture
def reference_site(website, monkeypatch):
    website.web['references'] = {'enabled': True, 'enqueue_command': ['maintenance-executable']}
    state = {'number': '100', 'state': 'complete', 'version': 'a' * 32, 'total': 2,
             'expected_total': 2, 'checked_at': datetime(2026, 1, 1), 'error': None}
    statements = []
    items = [{'order': i, 'label': str(i), 'source_id': 'ref' + str(i), 'text': 'Citation ' + str(i),
              'title': 'A title', 'target_number': '999' if i == 1 else None, 'doi': None,
              'target_kind': 'paper' if i == 1 else 'scholar',
              'target_url': '/papers/999' if i == 1 else 'https://scholar.google.com/scholar?q=A+title'} for i in (1, 2)]

    class Reader:
        def __init__(self, config): pass
        def close(self): pass
        def execute(self, sql, params=()):
            statements.append(sql)
            assert sql.startswith('SELECT'), 'Reader attempted a write'
            if 'FROM papers' in sql:
                return [{'number': '100'}] if params[0] == '100' else []
            if 'reference_schema_migrations' in sql:
                return [{'version': 1}]
            if 'paper_reference_state' in sql:
                return [state.copy()] if state.get('state') else []
            if 'paper_reference_snapshots' in sql:
                return [{'state': 'complete', 'total': 2, 'expected_total': 2, 'fetched_at': datetime(2025, 1, 1)}] if params[1] == 'a' * 32 else []
            if 'paper_references' in sql:
                chosen = [r for r in items if r['order'] == params[2]] if 'ordinal=%s' in sql else items[params[3]:params[3] + params[2]]
                return [{'data': json.dumps(r)} for r in chosen]
            raise AssertionError(sql)
    monkeypatch.setattr(references, 'Store', Reader)
    return website, state, statements


def test_list_and_item_keep_snapshot_order_and_select_only(reference_site):
    config, state, statements = reference_site
    result = references.read(config, '100', limit=1)
    assert result['total'] == 2 and result['next_offset'] == 1
    assert result['items'][0]['target_url'] == '/papers/999'
    item = references.read(config, '100', version='a' * 32, order=2)
    assert item['item']['target_kind'] == 'scholar'
    state.update(state='blocked', version='b' * 32, error='access_restricted')
    old = references.read(config, '100', version='a' * 32)
    assert old['state'] == 'complete' and old['error'] is None and old['version'] == 'a' * 32
    assert all(sql.startswith('SELECT') for sql in statements)


def test_ensure_only_submits_missing_and_does_not_retry_terminal_states(reference_site, monkeypatch):
    config, state, _ = reference_site
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        state.update(state='queued', version=None, total=0)
        return type('Result', (), {'returncode': 0, 'stdout': '{"status":"queued"}'})()
    monkeypatch.setattr(references.subprocess, 'run', run)
    assert references.enqueue(config, '100')['state'] == 'complete'
    state['state'] = None
    assert references.enqueue(config, '100')['state'] == 'queued'
    assert len(calls) == 1 and calls[0][0][-3:] == ['references', 'enqueue', '100']
    assert 'shell' not in calls[0][1]
    for terminal in ('failed', 'blocked', 'unavailable', 'partial', 'no_data', 'fetching'):
        state['state'] = terminal
        assert references.enqueue(config, '100')['state'] == terminal
    assert len(calls) == 1


def test_anonymous_ensure_is_explicitly_enabled_and_same_origin(reference_site):
    config, _, _ = reference_site
    with TestClient(create_app(config, reader_auth='public')) as client:
        assert client.post('/api/papers/100/references/ensure', json={}).status_code == 403
        assert client.post('/api/papers/100/references/ensure', json={}, headers={'Origin': 'https://other.example'}).status_code == 403
        assert client.post('/api/papers/100/references/ensure', json={}, headers={'Origin': 'http://testserver'}).status_code == 200
        assert client.get('/api/papers/100/references?limit=1').json()['next_offset'] == 1
        assert client.get('/api/papers/100/references/2?version=' + 'a' * 32).status_code == 200
        assert client.get('/api/papers/999/references').status_code == 404
        assert client.get('/api/papers/100/references?version=' + 'b' * 32).status_code == 404
        assert client.get('/api/papers/100/references?limit=0').status_code == 422
    config.web['references']['enabled'] = False
    with TestClient(create_app(config, reader_auth='public')) as client:
        assert client.post('/api/papers/100/references/ensure', headers={'Origin': 'http://testserver'}).status_code == 405
        assert client.get('/api/papers/100/references').json()['state'] == 'disabled'


def test_enqueue_failure_is_safe_and_never_leaks_command_output(reference_site, monkeypatch):
    config, state, _ = reference_site
    state['state'] = None
    def bad(*args, **kwargs):
        return type('Result', (), {'returncode': 1, 'stdout': 'private diagnostic'})()
    monkeypatch.setattr(references.subprocess, 'run', bad)
    with pytest.raises(references.ReferenceError) as error:
        references.enqueue(config, '100')
    assert error.value.code == 'references_queue_unavailable'


def test_optional_read_bridge_never_loads_writer_credentials_or_returns_private_fields(reference_site, monkeypatch):
    config, _, _ = reference_site
    config.web['references']['read_command'] = ['maintenance-executable']
    observed = []
    def run(command, **kwargs):
        observed.append(command)
        return type('Result', (), {'returncode': 0, 'stdout': json.dumps({
            'number': '100', 'state': 'missing', 'version': None, 'items': [], 'mysql': 'must not expose'})})()
    monkeypatch.setattr(references.subprocess, 'run', run)
    value = references.read(config, '100', offset=2, limit=3)
    assert 'mysql' not in value and value['state'] == 'missing'
    assert observed[0] == ['maintenance-executable', 'references', 'read', '100', '--offset', '2', '--limit', '3']


def test_concurrent_enqueue_observes_other_tab_without_retrying_collection(reference_site, monkeypatch):
    config, state, _ = reference_site
    state['state'] = None
    calls = []
    def busy(command, **kwargs):
        calls.append(command)
        state.update(state='queued', version=None, total=0)
        return type('Result', (), {'returncode': 1, 'stdout': '{"code":"worker_busy"}'})()
    monkeypatch.setattr(references.subprocess, 'run', busy)
    monkeypatch.setattr(references.time, 'sleep', lambda _: None)
    assert references.enqueue(config, '100')['state'] == 'queued'
    assert len(calls) == 1
