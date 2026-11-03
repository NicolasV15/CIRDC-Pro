"""Real HTTP deadline and concurrency regression with synthetic resources."""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from test_agent import agent_site, client_for, ensure, website  # noqa: F401
from test_agent_clients import serve

from cirdc.web.agent import PREFIX, AgentError
from cirdc.web.agent_requests import RequestStore
from cirdc.web.agent_runtime import DEADLINE, BoundedExecutor, BusyError
from cirdc.web.app import create_app


@pytest.mark.parametrize('wait', [0, 5])
def test_real_http_timeout_late_commit_and_read_isolation(agent_site, wait, monkeypatch, tmp_path):
    config, provider, resources = agent_site
    release, entered = threading.Event(), threading.Event()
    original = provider.agent_ensure
    calls = []
    def blocked(number, kind, peer, retry=False):
        calls.append(number)
        if number == '100':
            entered.set()
            assert release.wait(15)
        return original(number, kind, peer, retry=retry)
    provider.agent_ensure = blocked
    origin_db = tmp_path / 'origins.sqlite'
    monkeypatch.setenv('CIRDC_WEB_VISITS_FILE', str(origin_db))
    with serve(create_app(config, resource_providers=resources)) as origin, httpx.Client(base_url=origin, timeout=12, trust_env=False) as client:
        try:
            start = time.monotonic()
            result = client.post(PREFIX+'/papers/100/ensure', json={'wait_seconds': wait})
            elapsed = time.monotonic()-start
            assert entered.is_set() and not release.is_set()
            assert result.status_code == 503 and result.json()['accepted'] is None
            assert result.json()['next_action'] == 'wait'
            assert result.headers['retry-after'] == str(result.json()['retry_after_seconds'])
            assert wait+1.8 <= elapsed <= wait+2.7
            other = client.post(PREFIX+'/papers/101/ensure', json={'wait_seconds': 0})
            assert other.status_code == 202
            assert client.get(PREFIX+'/papers/101/content').status_code == 200
        finally:
            release.set()
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            result = client.post(PREFIX+'/papers/100/ensure', json={'wait_seconds': 0})
            if result.status_code == 202:
                break
        assert result.status_code == 202
        assert client.get(result.json()['status_url']).status_code == 202
        assert calls.count('100') == 1
    import sqlite3
    with sqlite3.connect(origin_db) as db:
        assert db.execute("SELECT count(*) FROM task_links l JOIN task_requests r ON r.id=l.request_id WHERE r.paper='100'").fetchone()[0] >= 1


def test_capacity_stays_reserved_until_real_completion():
    async def exercise():
        pool = BoundedExecutor(1)
        release = threading.Event()
        token = DEADLINE.set(time.monotonic()+0.05)
        try:
            with pytest.raises(BusyError):
                await pool.call(release.wait, 3)
            DEADLINE.set(time.monotonic()+1)
            with pytest.raises(BusyError):
                await pool.call(lambda: 'must not run')
        finally:
            release.set()
            DEADLINE.reset(token)
            pool.close()
    asyncio.run(exercise())


def test_cross_paper_submission_does_not_hold_sqlite_write_lock(agent_site):
    store = RequestStore()
    entered, release = threading.Event(), threading.Event()
    def slow(previous):
        entered.set()
        assert release.wait(3)
        return {}, {'content': {'jobs': ['first']}}
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(store.ensure, '100', ['content'], slow)
        assert entered.wait(1)
        try:
            second = pool.submit(store.ensure, '101', ['content'], lambda _: ({}, {}))
            assert second.result(timeout=1)[0]
            with pytest.raises(BusyError):
                store.ensure('100', ['pdf'], lambda _: ({}, {}))
        finally:
            release.set()
        assert first.result(timeout=1)[0]


def test_error_actions_and_limiter_interval(agent_site):
    provider = agent_site[1]
    def missing(*args):
        raise AgentError('content_not_ready', 409)
    provider.agent_document = missing
    with client_for(agent_site) as client:
        assert client.get(PREFIX+'/papers/100/content').json()['next_action'] == 'ensure'
        receipt = ensure(client, ['content', 'pdf']).json()
        response = client.get(PREFIX+'/papers/100/content')
        assert response.json()['request_id'] == receipt['request_id']
        assert response.json()['next_action'] == 'wait'
        def broken(*args):
            raise RuntimeError('not public')
        provider.agent_document = broken
        response = client.get(PREFIX+'/papers/100/content')
        assert response.status_code == 503 and 'not public' not in response.text
        assert response.json()['next_action'] == 'wait'
        for _ in range(119):
            ensure(client)
        response = ensure(client)
        assert response.status_code == 429
        assert 1 <= response.json()['retry_after_seconds'] <= 60
        assert response.headers['retry-after'] == str(response.json()['retry_after_seconds'])


def test_http_helper_preserves_backoff_and_transport_semantics(agent_site, monkeypatch):
    import importlib.util
    from pathlib import Path
    config, provider, resources = agent_site
    script = Path(__file__).parents[1]/'.agents/skills/cirdc-research/scripts/cirdc_client.py'
    spec = importlib.util.spec_from_file_location('stability_client', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def broken(*args):
        raise RuntimeError('private failure detail')
    provider.agent_document = broken
    with serve(create_app(config, resource_providers=resources)) as origin:
        client = module.Client(origin)
        with pytest.raises(module.ClientError) as failure:
            client.read('100')
        value = failure.value.value
        assert value['http_status'] == 503 and value['retry_after_seconds'] == 5
        assert value['next_action'] == 'wait' and 'private failure detail' not in str(value)
    def timeout(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr(module, 'urlopen', timeout)
    with pytest.raises(module.ClientError) as failure:
        client.read('100')
    assert failure.value.value['method'] == 'GET'
    assert failure.value.value['failure_kind'] == 'timeout'
    assert 'accepted' not in failure.value.value
    with pytest.raises(module.ClientError) as failure:
        client.ensure('100')
    assert failure.value.value['accepted'] is None


def test_retry_timeout_does_not_return_old_receipt_as_completed(agent_site, monkeypatch):
    provider = agent_site[1]
    release = threading.Event()
    original = provider.agent_ensure
    with client_for(agent_site) as client:
        first = ensure(client).json()
        provider.finish('content', 'failed')
        def blocked(number, kind, peer, retry=False):
            assert retry
            assert release.wait(3)
            return original(number, kind, peer, retry=retry)
        provider.agent_ensure = blocked
        monkeypatch.setattr('cirdc.web.agent.OVERHEAD', 0.05)
        try:
            response = ensure(client, retry=True)
            assert response.status_code == 503
            assert response.json()['accepted'] is None
            assert 'complete' not in response.json()
        finally:
            release.set()
        deadline = time.monotonic()+2
        while time.monotonic() < deadline:
            value = client.get(first['status_url']).json()
            if value.get('pending'):
                break
            time.sleep(0.01)
        assert value['request_id'] == first['request_id']
        assert value['pending'] and value['prior_attempts'] == 1
