"""Bounded synchronous hooks. Timed-out work retains its slot until completion."""
import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context

OVERHEAD = 2
READ_TIMEOUT = 10
SUBMIT_WORKERS = 4
READ_WORKERS = 8
DEADLINE = ContextVar('agent_deadline', default=None)
LOG = logging.getLogger('cirdc.agent')


class BusyError(Exception):
    code = 'resource_service_unavailable'
    status = 503

    def __init__(self, accepted=None):
        self.accepted = accepted


class BoundedExecutor:
    def __init__(self, workers):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='agent')
        self.slots = threading.BoundedSemaphore(workers)

    async def call(self, function, *args):
        remaining = (DEADLINE.get() or time.monotonic() + READ_TIMEOUT) - time.monotonic()
        if remaining <= 0 or not self.slots.acquire(blocking=False):
            LOG.warning('agent_capacity_or_deadline_exhausted')
            raise BusyError(accepted=False)
        context = copy_context()
        start = time.monotonic()
        def invoke():
            try:
                return context.run(function, *args)
            finally:
                LOG.info('agent_hook function=%s seconds=%.3f', getattr(function, '__name__', 'hook'), time.monotonic()-start)
                self.slots.release()
        try:
            future = self.pool.submit(invoke)
        except BaseException:
            self.slots.release()
            raise
        wrapped = asyncio.wrap_future(future)
        # Consume late exceptions even after the HTTP coroutine has disconnected.
        wrapped.add_done_callback(lambda f: None if f.cancelled() else f.exception())
        try:
            return await asyncio.wait_for(asyncio.shield(wrapped), remaining)
        except asyncio.TimeoutError:
            LOG.warning('agent_hook_timeout function=%s', getattr(function, '__name__', 'hook'))
            raise BusyError() from None

    def close(self):
        self.pool.shutdown(wait=False)
