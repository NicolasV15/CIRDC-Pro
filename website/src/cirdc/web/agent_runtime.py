"""Bounded synchronous hooks. Timed-out work retains its slot until completion."""
import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context

OVERHEAD = 10
READ_TIMEOUT = 10
SUBMIT_WORKERS = 16
READ_WORKERS = 32
DEADLINE = ContextVar('agent_deadline', default=None)
LOG = logging.getLogger('cirdc.agent')


class BusyError(Exception):
    code = 'resource_service_unavailable'
    status = 503

    def __init__(self, accepted=None, reason='submission_in_progress'):
        self.accepted = accepted
        self.details = {'reason': reason}


class BoundedExecutor:
    def __init__(self, workers):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='agent')
        self.slots = threading.BoundedSemaphore(workers)

    async def call(self, function, *args):
        deadline = DEADLINE.get() or time.monotonic() + READ_TIMEOUT
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BusyError(accepted=False, reason='request_deadline_exceeded')
        while not self.slots.acquire(blocking=False):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BusyError(accepted=False, reason='request_deadline_exceeded')
            await asyncio.sleep(min(0.005, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self.slots.release()
            raise BusyError(accepted=False, reason='request_deadline_exceeded')
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
            raise BusyError(reason='hook_timeout') from None

    def close(self):
        self.pool.shutdown(wait=False)
