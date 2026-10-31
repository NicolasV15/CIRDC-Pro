"""Generic, read-only publication-series resolution for browser queries."""
import re
import sqlite3
import time
from contextlib import closing
from .settings import state_dir


def parse_venue_any(value):
    if value in (None, ''):
        return []
    if not isinstance(value, str):
        raise ValueError('Invalid publication identifiers')
    numbers = [part.strip() for part in value.split(',')]
    if len(numbers) > 32 or any(not re.fullmatch(r'[0-9]{1,64}', n) for n in numbers):
        raise ValueError('Provide at most 32 publication identifiers')
    return list(dict.fromkeys(numbers))


def add_filter(numbers, clauses, args):
    if not numbers:
        return
    placeholders = ','.join('?' for _ in numbers)
    direct = ' UNION '.join('SELECT ?' for _ in numbers)
    clauses.append('d.venue IN (SELECT member FROM venue_members WHERE series IN ('
                   + placeholders + ') UNION ' + direct + ')')
    args.extend(numbers)
    args.extend(numbers)


def attach_series(items):
    """Attach source series IDs, never labels; this connection cannot write data."""
    references = []
    for item in items:
        record = item.get('record') or {}
        number = str(item.get('venue') or record.get('publicationNumber') or '')
        kind = str(item.get('kind') or record.get('articleContentType') or '')
        if kind in ('Early Access Articles', 'Magazines'):
            kind = 'Journals'
        references.append((item, kind, number))
        item['venue_series'] = []
    numbers = list(dict.fromkeys(number for _, _, number in references if number))
    if not numbers:
        return
    path = state_dir() / 'search.sqlite'
    with closing(sqlite3.connect(path.absolute().as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
        started = time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic() - started > 3), 10000)
        rows = db.execute('SELECT kind,member,series FROM venue_members WHERE member IN ('
                          + ','.join('?' for _ in numbers) + ')', numbers)
        memberships = {}
        for kind, member, series in rows:
            memberships.setdefault((kind, member), set()).add(series)
        for item, kind, number in references:
            item['venue_series'] = sorted(memberships.get((kind, number), ()))
