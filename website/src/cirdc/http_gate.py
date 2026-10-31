"""Cross-process request spacing, shared by optional interactive/background clients."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import time


def location():
    return Path(os.environ.get('CIRDC_HTTP_GATE', Path.home() / '.local/state/cirdc/http-gate.sqlite'))


def wait(interval=1.0, priority=False):
    path = location()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(path, timeout=10) as db:
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('CREATE TABLE IF NOT EXISTS gate(id INTEGER PRIMARY KEY,last REAL,priority_until REAL)')
        db.execute('INSERT OR IGNORE INTO gate VALUES(1,0,0)')
        db.commit()
        while True:
            db.execute('BEGIN IMMEDIATE')
            last, until = db.execute('SELECT last,priority_until FROM gate WHERE id=1').fetchone()
            now = time.time()
            # Reset stale wall-clock reservations after clock corrections.
            if last > now + 60:
                last = 0
            if priority:
                until = now + 3
                db.execute('UPDATE gate SET priority_until=? WHERE id=1', (until,))
            delay = max(0, last + max(1.0, interval) - now, 0 if priority else min(3, until - now))
            if delay <= 0:
                db.execute('UPDATE gate SET last=? WHERE id=1', (now,))
                db.commit()
                return
            db.commit()
            time.sleep(min(0.25, delay))


@contextmanager
def interactive():
    try:
        yield
    finally:
        path = location()
        if path.exists():
            with sqlite3.connect(path, timeout=10) as db:
                db.execute('UPDATE gate SET priority_until=0 WHERE id=1')
