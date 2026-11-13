"""Polling deadlines preserve receipts without hiding genuine request failures."""
from types import SimpleNamespace

import pytest

from cirdc.web.app import create_app
from test_agent import agent_site, website  # noqa: F401
from test_agent_clients import serve
from test_skill_install import SOURCE, load_script

REQUEST_ID = 'a' * 32
PENDING = {'request_id': REQUEST_ID, 'pending': True, 'complete': False,
           'http_status': 202, 'retry_after_seconds': 2}


@pytest.fixture
def helper():
    module = load_script(SOURCE / 'scripts/cirdc_client.py')
    client = module.Client.__new__(module.Client)
    client.base_url = 'https://papers.example.org'
    client.client_id = 'fixture-wait'
    return module, client


@pytest.fixture
def clock(helper, monkeypatch):
    now = [0.0]
    def advance(seconds):
        now[0] += seconds
    monkeypatch.setattr(helper[0], 'time', SimpleNamespace(monotonic=lambda: now[0], sleep=advance))
    return now, advance


@pytest.mark.parametrize('budget', [2, 5, 10])
def test_pending_at_deadline_returns_receipt_without_expired_poll(helper, clock, budget):
    _, client = helper
    now, advance = clock
    calls = []
    def request(path, timeout):
        assert now[0] < budget
        assert timeout > 0.05
        calls.append(now[0])
        advance(0.05)
        return dict(PENDING)
    client.request = request
    result = client.status(REQUEST_ID, budget)
    assert result == PENDING and now[0] == budget
    assert calls and all(b - a >= 2 for a, b in zip(calls, calls[1:]))


def test_inflight_timeout_at_poll_budget_returns_last_pending_receipt(helper, clock):
    module, client = helper
    now, advance = clock
    def request(path, timeout):
        if now[0] == 0:
            advance(0.1)
            return dict(PENDING)
        advance(timeout)
        raise module.ClientError({'error': 'connection_failed', 'failure_kind': 'timeout'})
    client.request = request
    assert client.status(REQUEST_ID, 5) == PENDING
    assert now[0] == 5


@pytest.mark.parametrize('failure', [
    {'error': 'connection_failed', 'failure_kind': 'connection'},
    {'error': 'connection_failed', 'failure_kind': 'timeout'},
    {'error': 'resource_service_unavailable', 'http_status': 503, 'retry_after_seconds': 5},
])
def test_real_errors_before_deadline_retain_receipt_identity(helper, clock, failure):
    module, client = helper
    now, advance = clock
    def request(path, timeout):
        if now[0] == 0:
            advance(0.1)
            return dict(PENDING)
        advance(0.1)
        raise module.ClientError(dict(failure))
    client.request = request
    with pytest.raises(module.ClientError) as caught:
        client.status(REQUEST_ID, 5)
    assert caught.value.value == {**failure, 'request_id': REQUEST_ID,
                                 'status_url': client.base_url + '/api/agent/v1/requests/' + REQUEST_ID}


def test_initial_timeout_does_not_invent_a_receipt(helper, clock):
    module, client = helper
    _, advance = clock
    def request(path, timeout):
        advance(timeout)
        raise module.ClientError({'error': 'connection_failed', 'failure_kind': 'timeout'})
    client.request = request
    with pytest.raises(module.ClientError):
        client.status(REQUEST_ID, 2)


@pytest.mark.parametrize('state', ['ready', 'unavailable'])
def test_terminal_receipt_returns_immediately(helper, clock, state):
    _, client = helper
    now, advance = clock
    terminal = {**PENDING, 'pending': False, 'complete': True, 'http_status': 200,
                'resources': {'pdf': {'state': state}}}
    def request(path, timeout):
        advance(0.1)
        return terminal
    client.request = request
    assert client.status(REQUEST_ID, 10) == terminal
    assert now[0] == 0.1


def test_single_read_allows_server_processing_budget(helper, clock):
    _, client = helper
    _, advance = clock
    def request(path, timeout):
        assert timeout > 10
        advance(4)
        return dict(PENDING)
    client.request = request
    assert client.status(REQUEST_ID) == PENDING


def test_http_pending_wait_and_resume_do_not_resubmit(agent_site, helper):
    _, client = helper
    config, provider, resources = agent_site
    with serve(create_app(config, resource_providers=resources)) as origin:
        client.base_url = origin
        receipt = client.ensure('100', wait_seconds=0)
        result = client.status(receipt['request_id'], wait_seconds=0.15)
        assert result['pending'] and not result['complete']
        assert result['request_id'] == receipt['request_id']
        provider.finish('content')
        assert client.status(receipt['request_id'])['complete']
        assert len(provider.calls) == 1


@pytest.mark.parametrize('state', ['failed', 'partial'])
@pytest.mark.parametrize('action', ['contact_administrator', 'stop'])
def test_terminal_incomplete_receipt_returns_without_another_poll(helper, clock, state, action):
    _, client = helper
    now, advance = clock
    terminal = {**PENDING, 'pending': False, 'complete': False, 'http_status': 200,
                'resources': {'content': {'state': state, 'next_action': action,
                                          'message': 'Conversion has stopped.'},
                              'pdf': {'state': 'ready'}}}
    calls = []
    def request(path, timeout):
        calls.append(path)
        advance(0.1)
        return terminal
    client.request = request
    assert client.status(REQUEST_ID, 30) == terminal
    assert calls == ['/requests/' + REQUEST_ID]
    assert now[0] == 0.1


@pytest.mark.parametrize('action', ['contact_administrator', 'stop'])
def test_mcp_preserves_terminal_incomplete_receipt_and_ready_pdf(agent_site, helper, action):
    import asyncio
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    _, client = helper
    config, provider, resources = agent_site
    with serve(create_app(config, resource_providers=resources)) as origin:
        client.base_url = origin
        receipt = client.ensure('100', resources=['content', 'pdf'], wait_seconds=0)
        provider.finish('content', 'failed')
        provider.current['content'].update(next_action=action, reason='backend_service_error',
                                           message='Conversion has stopped.', max_retry_attempts=10)
        provider.finish('pdf')
        value = client.status(receipt['request_id'], wait_seconds=30)
        assert value['pending'] is False and value['complete'] is False
        assert value['resources']['content']['next_action'] == action
        assert value['resources']['pdf']['state'] == 'ready'

        async def check():
            async with httpx.AsyncClient(trust_env=False) as http_client, streamable_http_client(
                    origin + '/api/agent/v1/mcp', http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await asyncio.wait_for(session.call_tool('get_request',
                        {'request_id': receipt['request_id'], 'wait_seconds': 30}), timeout=5)
                    data = result.structuredContent
                    assert data['request_id'] == receipt['request_id']
                    assert data['pending'] is False and data['complete'] is False
                    assert data['resources']['content']['state'] == 'failed'
                    assert data['resources']['content']['next_action'] == action
                    assert data['resources']['pdf']['state'] == 'ready'
        asyncio.run(check())
        assert len(provider.calls) == 2
