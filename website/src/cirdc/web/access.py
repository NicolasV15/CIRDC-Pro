"""Reader access policy; administrator authentication is always required."""
import os
import time
import threading
from collections import OrderedDict, deque


def authentication_required(interface, reader_auth=None):
    if interface == 'admin':
        return True
    value = reader_auth if reader_auth is not None else os.environ.get('CIRDC_WEB_READER_AUTH', 'required')
    if value not in ('required', 'public'):
        raise ValueError('CIRDC_WEB_READER_AUTH must be required or public')
    return value == 'required'


class SearchRateLimiter:
    def __init__(self, limit=10, interval=1.0, capacity=4096):
        self.limit = limit
        self.interval = interval
        self.capacity = capacity
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self.lock:
            timestamps = self.entries.pop(key, deque())
            while timestamps and timestamps[0] < now - self.interval:
                timestamps.popleft()
            self.entries[key] = timestamps
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
            if len(timestamps) >= self.limit:
                return False
            timestamps.append(now)
            return True
