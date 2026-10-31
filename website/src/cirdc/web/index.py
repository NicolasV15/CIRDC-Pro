import base64
import fcntl
import hashlib
import json
import re
import shutil
import sqlite3
import time
import threading
from collections import OrderedDict
from concurrent.futures import Future
from contextlib import closing
from datetime import datetime, timezone
from html import unescape
from .settings import connect, state_dir
from .venues import parse_venue_any, add_filter as add_venue_filter


def now():
    return datetime.now(timezone.utc).isoformat()


def plain(value):
    return unescape(re.sub(r'<[^>]*>', '', str(value or ''))).strip()


def initialize(db):
    required = {'docs_group_year', 'docs_abstract_year', 'docs_keywords_year', 'docs_venue_cover', 'docs_facets_by_id'}
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='docs'").fetchone() and not required.issubset(existing):
        save_meta(db, phase='upgrading')
        db.commit()
        print(json.dumps({'phase': 'upgrading', 'new_indexes': len(required - existing)}), flush=True)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS venue_members(
      kind TEXT NOT NULL,series TEXT NOT NULL,member TEXT NOT NULL,PRIMARY KEY(kind,series,member));
    CREATE TABLE IF NOT EXISTS docs(
      id INTEGER PRIMARY KEY, number TEXT UNIQUE NOT NULL, doi TEXT NOT NULL,
      title TEXT NOT NULL, authors TEXT NOT NULL, keywords TEXT NOT NULL, abstract TEXT NOT NULL,
      year INTEGER NOT NULL, kind TEXT NOT NULL, venue TEXT NOT NULL, publication TEXT NOT NULL,
      abstract_state TEXT NOT NULL, keywords_state TEXT NOT NULL, updated TEXT NOT NULL,
      order_number TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS docs_year ON docs(year DESC,order_number DESC);
    CREATE INDEX IF NOT EXISTS docs_venue ON docs(venue,year DESC,order_number DESC);
    CREATE INDEX IF NOT EXISTS docs_kind ON docs(kind,year DESC,order_number DESC);
    CREATE INDEX IF NOT EXISTS docs_doi ON docs(doi);
    CREATE INDEX IF NOT EXISTS docs_group_year ON docs(
      (CASE WHEN kind IN ('Journals','Magazines','Early Access Articles') THEN 'Journals' ELSE kind END),
      year DESC,order_number DESC,number DESC,abstract_state,keywords_state,venue);
    CREATE INDEX IF NOT EXISTS docs_abstract_year ON docs(
      abstract_state,year DESC,order_number DESC,number DESC,keywords_state,kind,venue);
    CREATE INDEX IF NOT EXISTS docs_keywords_year ON docs(
      keywords_state,year DESC,order_number DESC,number DESC,abstract_state,kind,venue);
    CREATE INDEX IF NOT EXISTS docs_venue_cover ON docs(
      venue,year DESC,order_number DESC,number DESC,kind,abstract_state,keywords_state);
    CREATE INDEX IF NOT EXISTS docs_facets_by_id ON docs(
      id,kind,venue,year,abstract_state,keywords_state,order_number,number);
    CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(title,authors,keywords,abstract,
      content='docs',content_rowid='id',tokenize='unicode61 remove_diacritics 2');
    CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
      INSERT INTO search(rowid,title,authors,keywords,abstract)
      VALUES(new.id,new.title,new.authors,new.keywords,new.abstract); END;
    CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
      INSERT INTO search(search,rowid,title,authors,keywords,abstract)
      VALUES('delete',old.id,old.title,old.authors,old.keywords,old.abstract); END;
    CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON docs BEGIN
      INSERT INTO search(search,rowid,title,authors,keywords,abstract)
      VALUES('delete',old.id,old.title,old.authors,old.keywords,old.abstract);
      INSERT INTO search(rowid,title,authors,keywords,abstract)
      VALUES(new.id,new.title,new.authors,new.keywords,new.abstract); END;
    ''')
    db.execute("INSERT INTO search(search,rank) VALUES('rank','bm25(8,3,5,1)')")
    for name in required - existing:
        db.execute('ANALYZE ' + name)
    db.commit()

    from .authors import initialize as initialize_authors
    initialize_authors(db)


def metadata(db):
    return {r['key']: json.loads(r['value']) for r in db.execute('SELECT * FROM meta')}


def publication_year_range(db):
    # Separate boundary lookups use docs_year without scanning every document.
    first = db.execute('SELECT year FROM docs WHERE year BETWEEN 1800 AND 2200 ORDER BY year LIMIT 1').fetchone()
    last = db.execute('SELECT year FROM docs WHERE year BETWEEN 1800 AND 2200 ORDER BY year DESC LIMIT 1').fetchone()
    return {'min': first[0] if first else None, 'max': last[0] if last else None}


def validate_year_range(params):
    years = {}
    for key in ('year_from', 'year_to'):
        if params.get(key):
            year = int(params[key])
            if not 1800 <= year <= 2200:
                raise ValueError('Year must be between 1800 and 2200')
            years[key] = year
    if len(years) == 2 and years['year_from'] > years['year_to']:
        raise ValueError('Start year must not be later than end year')
    return years


def save_meta(db, **values):
    db.executemany('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                   [(k, json.dumps(v, default=str)) for k, v in values.items()])


def project(row):
    record = json.loads(row['data']) if isinstance(row['data'], str) else row['data']
    words = record.get('keywords') or {}
    if not isinstance(words, dict):
        from ..model import keywords
        words = keywords(words)
    year = str(record.get('publicationYear', ''))
    number = str(row['number'])
    return (number, str(record.get('doi') or '').strip().lower(), plain(record.get('articleTitle')),
            '; '.join(plain(a.get('preferredName') or ' '.join(str(a.get(k) or '') for k in ['firstName', 'lastName']))
                      for a in record.get('authors', []) if isinstance(a, dict)),
            ' '.join(plain(w) for values in words.values() if isinstance(values, list) for w in values),
            plain(record.get('abstract')), int(year) if year.isdigit() else 0,
            str(record.get('articleContentType') or ''), str(record.get('publicationNumber') or ''),
            plain(record.get('publicationTitle')), row['abstract_state'], row['keywords_state'],
            str(row.get('updated_at') or ''), number.zfill(64))


COLUMNS = 'number,doi,title,authors,keywords,abstract,year,kind,venue,publication,abstract_state,keywords_state,updated,order_number'
UPSERT = ('INSERT INTO docs(' + COLUMNS + ') VALUES(' + ','.join('?' for _ in range(14)) + ') '
          'ON CONFLICT(number) DO UPDATE SET ' + ','.join(c + '=excluded.' + c for c in COLUMNS.split(',')[1:]))


def put_rows(db, rows):
    db.executemany(UPSERT, [project(r) for r in rows])
    from .authors import sync_rows
    sync_rows(db, rows)


def refresh_overview(store, db):
    from ..engine import Service
    summary = Service(store.config, store=store).summary()
    venues = store.execute('SELECT kind,COUNT(*) AS n FROM venues GROUP BY kind')
    definitions = store.execute('SELECT kind,number,data FROM venues')
    queue = store.execute('SELECT COUNT(*) AS n,MIN(changed_at) AS oldest FROM web_index_queue')[0]
    store.db.commit()
    members = []
    for venue in definitions:
        data = json.loads(venue['data'])
        members.append((venue['kind'], venue['number'], venue['number']))
        for history in data.get('titleHistory', []):
            if isinstance(history, dict) and history.get('publicationNumber'):
                members.append((venue['kind'], venue['number'], str(history['publicationNumber'])))
    db.executemany('INSERT OR IGNORE INTO venue_members(kind,series,member) VALUES(?,?,?)', members)
    save_meta(db, overview={**summary, 'venues': venues, 'sampled_at': now()},
              backlog=queue['n'], oldest_event=str(queue['oldest']) if queue['oldest'] else None,
              checked_at=now())
    db.commit()


def consume(store, db, limit=500):
    # Read the event version and current record in a single database snapshot.
    store.db.rollback()
    events = store.execute('SELECT number,token FROM web_index_queue ORDER BY changed_at,number LIMIT %s', (limit,))
    if not events:
        store.db.commit()
        return 0
    numbers = [e['number'] for e in events]
    rows = store.execute('SELECT * FROM papers WHERE number IN (' + ','.join(['%s'] * len(numbers)) + ')', numbers)
    store.db.commit()
    try:
        put_rows(db, rows)
        present = {r['number'] for r in rows}
        db.executemany('DELETE FROM docs WHERE number=?', [(n,) for n in numbers if n not in present])
        save_meta(db, synced_at=now())
        db.commit()
    except Exception:
        db.rollback()
        raise
    # A newer event must survive acknowledgement of this version.
    store.many('DELETE FROM web_index_queue WHERE number=%s AND token=%s', [(e['number'], e['token']) for e in events])
    store.db.commit()
    return len(events)


def run_index(config, max_rows=None, once=False):
    from ..store import Store
    lock = (state_dir() / 'index.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another search indexer is running') from None
    store = Store(config)
    db = connect('search.sqlite')
    try:
        db.execute('PRAGMA cache_size=-524288')
        initialize(db)
        store.migrate()
        from .capture import install, seed_missed
        install(store)
        store.execute("INSERT INTO web_settings(name,value) VALUES('index_enabled','1') ON DUPLICATE KEY UPDATE value='1'")
        store.db.commit()
        meta = metadata(db)
        seed_missed(config, store, db, meta)
        meta = metadata(db)
        processed = 0
        last_report = time.monotonic()
        last_refresh = 0
        if meta.get('phase') != 'ready':
            last = meta.get('last_number', '')
            indexed = meta.get('indexed', 0)
            refresh_overview(store, db)
            last_refresh = time.monotonic()
            save_meta(db, phase='building', started_at=meta.get('started_at') or now())
            db.commit()
            while True:
                if shutil.disk_usage(state_dir()).free < 20 * 1024**3:
                    raise OSError('Search index paused: less than 20 GiB free on the index volume')
                batch = min(1000, max_rows - processed) if max_rows is not None else 1000
                if batch <= 0:
                    return {'phase': 'building', 'indexed': indexed}
                rows = store.execute('SELECT * FROM papers WHERE number>%s ORDER BY number LIMIT %s', (last, batch))
                store.db.commit()
                if not rows:
                    break
                try:
                    put_rows(db, rows)
                    last = rows[-1]['number']
                    indexed += len(rows)
                    processed += len(rows)
                    save_meta(db, last_number=last, indexed=indexed, checked_at=now())
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                if time.monotonic() - last_report > 10:
                    print(json.dumps({'phase': 'building', 'indexed': indexed, 'last_number': last}), flush=True)
                    last_report = time.monotonic()
                if time.monotonic() - last_refresh > 60:
                    refresh_overview(store, db)
                    last_refresh = time.monotonic()
            save_meta(db, phase='catching_up')
            db.commit()
            while consume(store, db):
                pass
            count = db.execute('SELECT COUNT(*) FROM docs').fetchone()[0]
            save_meta(db, phase='ready', indexed=count, completed_at=now(), error=None)
            db.commit()
        while True:
            changed = consume(store, db)
            from .authors import backfill_step
            author_progress = backfill_step(store, db)
            if author_progress and time.monotonic() - last_report > 10:
                current = metadata(db)
                print(json.dumps({'phase': 'author_backfill', 'papers': current.get('authors_papers_seen', 0),
                                  'signatures': current.get('authors_signatures_seen', 0)}), flush=True)
                last_report = time.monotonic()
            if time.monotonic() - last_refresh > 60:
                refresh_overview(store, db)
                save_meta(db, indexed=db.execute('SELECT COUNT(*) FROM docs').fetchone()[0], error=None)
                db.commit()
                last_refresh = time.monotonic()
            if once:
                return metadata(db)
            if not changed and not author_progress:
                time.sleep(2)
    except BaseException as error:
        db.rollback()
        try:
            save_meta(db, error=type(error).__name__, checked_at=now())
            db.commit()
        except sqlite3.Error:
            pass
        raise
    finally:
        db.close()
        store.close()
        lock.close()


def _search_uncached(params):
    years = validate_year_range(params)
    with closing(connect('search.sqlite')) as db:
        meta = metadata(db)
        query = str(params.get('q') or '').strip()
        if len(query) > 200:
            raise ValueError('Search is limited to 200 characters')
        size = max(1, min(100, int(params.get('limit', 25))))
        field = params.get('field', 'all')
        if field not in ('all', 'title', 'authors', 'keywords', 'abstract'):
            raise ValueError('Invalid search field')
        order = params.get('sort', 'relevance' if query else 'year')
        if order not in ('relevance', 'year'):
            raise ValueError('Invalid sort order')
        clauses, args = [], []
        venue_any = parse_venue_any(params.get('venue_any'))
        from .authors import add_filter
        author_filtered = add_filter(db, params, clauses, args)
        author_query = field == 'authors' and bool(query)
        use_fts = bool(query and not author_query and not query.isdigit() and not re.match(r'^(?:https?://(?:dx\.)?doi\.org/)?10\.\d+/', query, re.I))
        if author_query:
            pass
        elif query.isdigit():
            clauses.append('d.number=?'); args.append(query)
        elif query and not use_fts:
            clauses.append('d.doi=?'); args.append(re.sub(r'^https?://(?:dx\.)?doi\.org/', '', query, flags=re.I).lower())
        elif use_fts:
            words = re.findall(r'[^\W_]+', query, re.UNICODE)
            if not words:
                raise ValueError('Enter a searchable word')
            expression = ' AND '.join('"' + w.replace('"', '""') + '"' for w in words[:30])
            if field != 'all':
                expression = field + ':(' + expression + ')'
            clauses.append('search MATCH ?'); args.append(expression)
        if params.get('venue'):
            clauses.append('d.venue IN (SELECT member FROM venue_members WHERE series=? UNION SELECT ?)')
            args.extend([str(params['venue']), str(params['venue'])])
        add_venue_filter(venue_any, clauses, args)
        for key in ('kind', 'abstract_state', 'keywords_state'):
            if params.get(key):
                if key == 'kind':
                    clauses.append("(CASE WHEN d.kind IN ('Journals','Magazines','Early Access Articles') THEN 'Journals' ELSE d.kind END)=?")
                    args.append(str(params[key]))
                else:
                    clauses.append('d.' + key + '=?'); args.append(str(params[key]))
        for key, op in [('year_from', '>='), ('year_to', '<=')]:
            if key in years:
                clauses.append('d.year' + op + '?'); args.append(years[key])
        ranked = use_fts and order == 'relevance'
        fingerprint = hashlib.sha256(json.dumps({k: str(v) for k, v in sorted(params.items()) if k != 'cursor'}, sort_keys=True).encode()).hexdigest()[:16]
        if params.get('cursor'):
            try:
                cursor = json.loads(base64.urlsafe_b64decode(str(params['cursor']) + '==='))
                if cursor['query'] != fingerprint:
                    raise ValueError()
                if ranked:
                    clauses.append('(search.rank>? OR (search.rank=? AND search.rowid>?))')
                    args.extend([float(cursor['rank']), float(cursor['rank']), int(cursor['index_id'])])
                else:
                    clauses.append('(d.year<? OR (d.year=? AND (d.order_number<? OR (d.order_number=? AND d.number<?))))')
                    args.extend([int(cursor['year']), int(cursor['year']), str(cursor['order_number']), str(cursor['order_number']), str(cursor['number'])])
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                raise ValueError('Invalid page cursor') from None
        filtered = author_filtered or bool(venue_any) or any(params.get(k) for k in ('kind', 'venue', 'year_from', 'year_to', 'abstract_state', 'keywords_state'))
        impossible = False
        if use_fts:
            for field_name, index_name in [('abstract_state', 'docs_abstract_year'), ('keywords_state', 'docs_keywords_year')]:
                if params.get(field_name) and not db.execute('SELECT 1 FROM docs INDEXED BY ' + index_name
                                                           + ' WHERE ' + field_name + '=? LIMIT 1',
                                                           (str(params[field_name]),)).fetchone():
                    impossible = True
        source = ('search' if ranked and not filtered else
                  'search CROSS JOIN docs d INDEXED BY docs_facets_by_id ON d.id=search.rowid') if use_fts else 'docs d'
        if not query and not author_filtered:
            preferred = ('docs_venue_cover' if params.get('venue') or venue_any else
                         'docs_abstract_year' if params.get('abstract_state') else
                         'docs_keywords_year' if params.get('keywords_state') else
                         'docs_group_year' if params.get('kind') else 'docs_year')
            source = 'docs d INDEXED BY ' + preferred
        score = 'search.rank' if ranked else '0.0'
        sort = 'search.rank,search.rowid' if ranked else 'd.year DESC,d.order_number DESC,d.number DESC'
        row_id = 'search.rowid' if use_fts else 'd.id'
        outer_sort = 'h.score,h.id' if ranked else 'd.year DESC,d.order_number DESC,d.number DESC'
        # Rank only identifiers first; fetching abstracts for every candidate makes common
        # searches proportional to the full text payload instead of the selected page.
        sql = ('WITH hits AS (SELECT ' + row_id + ' AS id,' + score + ' AS score FROM ' + source
               + (' WHERE ' + ' AND '.join(clauses) if clauses else '') + ' ORDER BY ' + sort + ' LIMIT ?) '
               'SELECT d.number,d.doi,d.title,d.authors,d.publication,d.year,d.kind,d.venue,'
               'd.abstract_state,d.keywords_state,d.updated,d.order_number,substr(d.abstract,1,400) AS snippet,'
               'h.score AS rank,h.id AS index_id FROM hits h CROSS JOIN docs d ON d.id=h.id ORDER BY ' + outer_sort)
        started = time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic() - started > 4), 10000)
        rows = [] if impossible else [dict(r) for r in db.execute(sql, (*args, size + 1))]
        cursor = None
        if len(rows) > size:
            rows = rows[:size]
            last = rows[-1]
            cursor = base64.urlsafe_b64encode(json.dumps({'query': fingerprint, **{k: last[k] for k in ['rank', 'index_id', 'number', 'year', 'order_number']}}).encode()).decode().rstrip('=')
        try:
            stale = time.time() - datetime.fromisoformat(meta['checked_at']).timestamp() > 120
        except (KeyError, TypeError, ValueError):
            stale = True
        return {'items': rows, 'next_cursor': cursor, 'index': meta,
                'partial': meta.get('phase') != 'ready' or bool(meta.get('error')) or stale or
                           (author_filtered and meta.get('authors_phase') != 'ready')}


_RESULTS = OrderedDict()
_PENDING = {}
_RESULT_LOCK = threading.Lock()


def search(params):
    """Share repeated reads; any committed index change invalidates cached results."""
    path = state_dir() / 'search.sqlite'
    if not path.exists():
        return _search_uncached(params)
    snapshot = path.stat()
    key = (str(path), snapshot.st_dev, snapshot.st_ino, snapshot.st_mtime_ns, snapshot.st_size,
           json.dumps(params, sort_keys=True, default=str))
    leader = False
    result = None
    with _RESULT_LOCK:
        entry = _RESULTS.get(key)
        if entry and entry[0] > time.monotonic():
            _RESULTS.move_to_end(key)
            result = entry[1]
        elif key in _PENDING:
            future = _PENDING[key]
        else:
            future = Future()
            _PENDING[key] = future
            leader = True
    cache_hit = not leader
    if result is None:
        if leader:
            try:
                result = _search_uncached(params)
            except BaseException as error:
                with _RESULT_LOCK:
                    _PENDING.pop(key, None)
                future.set_exception(error)
                raise
            with _RESULT_LOCK:
                _RESULTS[key] = (time.monotonic() + 30, result)
                while len(_RESULTS) > 64:
                    _RESULTS.popitem(last=False)
                _PENDING.pop(key, None)
            future.set_result(result)
        else:
            result = future.result(timeout=6)
    # Never cache health/coverage timestamps, and do not let a caller mutate a shared page.
    with closing(connect('search.sqlite')) as db:
        current = metadata(db)
    try:
        stale = time.time() - datetime.fromisoformat(current['checked_at']).timestamp() > 120
    except (KeyError, TypeError, ValueError):
        stale = True
    return {**result, 'items': [dict(row) for row in result['items']], 'index': current,
            'partial': current.get('phase') != 'ready' or bool(current.get('error')) or stale or
                       (bool(params.get('field') == 'authors' or params.get('author_id')) and current.get('authors_phase') != 'ready'),
            'cache_hit': cache_hit}
