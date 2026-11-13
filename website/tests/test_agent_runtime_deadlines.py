"""Admission and execution share one deadline, including without request context."""
import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from cirdc.web import agent_runtime as runtime


def test_queue_wait_consumes_execution_budget():
    async def exercise():
        pool = runtime.BoundedExecutor(1)
        finished, entered = threading.Event(), threading.Event()
        assert pool.slots.acquire(blocking=False)
        asyncio.get_running_loop().call_later(0.4, pool.slots.release)
        def slow():
            entered.set()
            finished.wait(3)
        token = runtime.DEADLINE.set(time.monotonic() + 0.6)
        start = time.monotonic()
        try:
            with pytest.raises(runtime.BusyError) as caught:
                await pool.call(slow)
            assert entered.is_set()
            assert caught.value.details['reason'] == 'hook_timeout'
            assert caught.value.accepted is None
            assert time.monotonic() - start < 0.85
            assert not pool.slots.acquire(blocking=False)
        finally:
            finished.set()
            runtime.DEADLINE.reset(token)
            pool.close()
    asyncio.run(exercise())


def test_default_deadline_does_not_move_while_waiting(monkeypatch):
    monkeypatch.setattr(runtime, 'READ_TIMEOUT', 0.03)
    async def exercise():
        pool = runtime.BoundedExecutor(1)
        token = runtime.DEADLINE.set(None)
        assert pool.slots.acquire(blocking=False)
        try:
            with pytest.raises(runtime.BusyError) as caught:
                await asyncio.wait_for(pool.call(lambda: pytest.fail('No slot available')), 0.3)
            assert caught.value.accepted is False
            assert caught.value.details['reason'] == 'request_deadline_exceeded'
        finally:
            pool.slots.release()
            runtime.DEADLINE.reset(token)
            pool.close()
    asyncio.run(exercise())


def test_slot_acquired_after_deadline_is_released_without_starting_work(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(runtime, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    async def exercise():
        pool = runtime.BoundedExecutor(1)
        acquire = pool.slots.acquire
        def delayed_acquire(*args, **kwargs):
            clock[0] = 2.0
            return acquire(*args, **kwargs)
        monkeypatch.setattr(pool.slots, 'acquire', delayed_acquire)
        token = runtime.DEADLINE.set(1.0)
        calls = []
        try:
            with pytest.raises(runtime.BusyError) as caught:
                await pool.call(lambda: calls.append(True))
            assert caught.value.accepted is False
            assert calls == []
            assert acquire(blocking=False)
            pool.slots.release()
        finally:
            runtime.DEADLINE.reset(token)
            pool.close()
    asyncio.run(exercise())
