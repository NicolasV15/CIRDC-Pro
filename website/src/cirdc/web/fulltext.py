"""Paragraph index of provider-cached cleaned documents. Opt-in and read-only: the
indexer reads documents that already exist and never requests acquisition."""
import base64
import fcntl
import hashlib
import json
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone

from lxml import html as markup

from .settings import connect, state_dir
from .query import describe, excerpt, fts_expression, locate, parse, phrase_expression, spans, tokens

BLOCKS = frozenset('p li blockquote figcaption caption dt dd pre tr h1 h2 h3 h4 h5 h6'.split())
LOOSE = frozenset('div section article figure'.split())
CONTAINERS = BLOCKS | LOOSE
HEADINGS = frozenset('h1 h2 h3 h4 h5 h6'.split())
LABEL = re.compile(r'^SECTION\s+([IVXLCDM]+|[1-9]\d*)\.?$', re.I)
STOP = frozenset('a an and are as at be by for from in into is it its of on or that the their this to was were which with'.split())
# Cell and line boundaries separate words even when the markup has no whitespace.
SEPARATED = frozenset('td th br tr li dt dd p div section article figure figcaption caption pre blockquote table tbody thead tfoot ul ol dl h1 h2 h3 h4 h5 h6'.split())
FORMULA = ' ⋯ '
SENTENCE = 6
COVERAGE = 0.6
APPROXIMATE_LIMIT = 5000
TOP_CANDIDATES = 300
INDEXABLE = ('ready', 'partial')
MAX_ATTEMPTS = 5
RETRY_DELAY = 30
PENDING = "c.state IN ('ready','partial') AND (d.version IS NULL OR d.version IS NOT c.version)"


def now():
    return datetime.now(timezone.utc).isoformat()


def path():
    return state_dir() / 'fulltext.sqlite'


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS catalog(number TEXT PRIMARY KEY,version TEXT,state TEXT NOT NULL,source TEXT,
      seen_at TEXT NOT NULL,error TEXT);
    CREATE TABLE IF NOT EXISTS index_retries(number TEXT NOT NULL,version TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0,next_retry_at REAL,error TEXT,
      failures TEXT NOT NULL DEFAULT '[]',resolved_at TEXT,PRIMARY KEY(number,version));
    CREATE TABLE IF NOT EXISTS documents(number TEXT PRIMARY KEY,version TEXT NOT NULL,source TEXT,
      passages INTEGER NOT NULL,indexed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS passages(id INTEGER PRIMARY KEY,number TEXT NOT NULL,version TEXT NOT NULL,
      ordinal INTEGER NOT NULL,kind TEXT NOT NULL,section TEXT NOT NULL,section_id TEXT,text TEXT NOT NULL,
      UNIQUE(number,ordinal));
    CREATE VIRTUAL TABLE IF NOT EXISTS passage_search USING fts5(text,content='passages',content_rowid='id',
      tokenize='unicode61 remove_diacritics 2');
    CREATE VIRTUAL TABLE IF NOT EXISTS passage_vocab USING fts5vocab(passage_search,'row');
    CREATE TRIGGER IF NOT EXISTS passages_ai AFTER INSERT ON passages BEGIN
      INSERT INTO passage_search(rowid,text) VALUES(new.id,new.text); END;
    CREATE TRIGGER IF NOT EXISTS passages_ad AFTER DELETE ON passages BEGIN
      INSERT INTO passage_search(passage_search,rowid,text) VALUES('delete',old.id,old.text); END;
    ''')
    # Older indexes retained only the last catalog error. Keep that evidence when
    # introducing a retry budget; the previous attempt count is unknown.
    legacy = db.execute('SELECT c.* FROM catalog c LEFT JOIN index_retries r '
                        'ON r.number=c.number AND r.version=c.version '
                        "WHERE c.error IS NOT NULL AND c.version IS NOT NULL AND c.version<>'' AND r.number IS NULL").fetchall()
    db.executemany('INSERT INTO index_retries(number,version,error,failures) VALUES(?,?,?,?)',
                   [(row['number'], row['version'], row['error'],
                     json.dumps([{'at': row['seen_at'], 'error': row['error'], 'legacy': True}])) for row in legacy])
    db.commit()


def metadata(db):
    return {row['key']: json.loads(row['value']) for row in db.execute('SELECT key,value FROM meta')}


def save_meta(db, **values):
    db.executemany('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                   [(key, json.dumps(value, default=str)) for key, value in values.items()])


# ---------- Passage extraction (mirrors web/src/passageLocate.ts) ----------

def _source_widget(node):
    """IEEE 'View Source' TeX duplicates beside a formula are not body text."""
    children = [child for child in node if isinstance(child.tag, str)]
    return (node.tag == 'span' and len(children) == 2 and all(child.tag == 'span' for child in children)
            and (children[0].text or '').strip() == 'View Source')


def block_text(node):
    parts = []

    def walk(element):
        if 'doc-math' in (element.get('class') or '').split():
            parts.append(FORMULA)
            return
        if _source_widget(element):
            return
        if element.text:
            parts.append(element.text)
        for child in element:
            if isinstance(child.tag, str) and child.tag not in ('script', 'style'):
                if child.tag in SEPARATED:
                    parts.append(' ')
                walk(child)
            if child.tail:
                parts.append(child.tail)
    walk(node)
    return ' '.join(''.join(parts).split())


def passages(html):
    """Ordered leaf blocks with their nearest heading. Ordinals are positions among leaves."""
    root = markup.fragment_fromstring(html or '<p></p>', create_parent='div')
    # Containers with a container descendant are not leaves; formula internals never are.
    outer, formula = set(), set()
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if 'doc-math' in (node.get('class') or '').split():
            formula.update(node.iterdescendants())
        if node.tag in CONTAINERS and node not in formula:
            for parent in node.iterancestors():
                if parent in outer:
                    break
                outer.add(parent)
    result, section, section_id, label = [], '', None, None
    for node in root.iter():
        if not isinstance(node.tag, str) or node is root or node.tag not in CONTAINERS or node in outer or node in formula:
            continue
        text = block_text(node)
        if not tokens(text):
            continue
        following = node.getnext()
        # The reader merges a standalone "SECTION II." label into the following heading.
        if LABEL.match(text) and following is not None and following.tag in HEADINGS and following.get('id'):
            label = LABEL.match(text).group(1).upper()
            continue
        if node.tag in HEADINGS:
            if LABEL.match(text):
                label = LABEL.match(text).group(1).upper()
            else:
                section = (label + '. ' if label and not text.upper().startswith(label + '.') else '') + text
                label = None
            anchor = node.get('id') or next((parent.get('id') for parent in node.iterancestors() if parent.get('id')), None)
            section_id = anchor
        kind = ('heading' if node.tag in HEADINGS else 'caption' if node.tag in ('figcaption', 'caption')
                else 'table' if node.tag == 'tr' else 'text')
        result.append({'ordinal': len(result), 'kind': kind, 'section': section, 'section_id': section_id, 'text': text})
    return result


def fingerprint(text):
    return ' '.join(tokens(text)[:12])


# ---------- Indexer ----------

def catalog_provider(providers):
    found = [p for p in providers.providers if callable(getattr(p, 'agent_document_catalog', None))
             and callable(getattr(p, 'agent_document', None))]
    if len(found) != 1:
        raise RuntimeError('Enable exactly one resource provider that offers agent_document_catalog')
    return found[0]


def store_document(db, number, version, source, rows):
    db.execute('DELETE FROM passages WHERE number=?', (number,))
    db.executemany('INSERT INTO passages(number,version,ordinal,kind,section,section_id,text) VALUES(?,?,?,?,?,?,?)',
                   [(number, version, row['ordinal'], row['kind'], row['section'], row['section_id'], row['text']) for row in rows])
    db.execute('INSERT INTO documents(number,version,source,passages,indexed_at) VALUES(?,?,?,?,?) '
               'ON CONFLICT(number) DO UPDATE SET version=excluded.version,source=excluded.source,'
               'passages=excluded.passages,indexed_at=excluded.indexed_at', (number, version, source, len(rows), now()))


def remove_document(db, number):
    db.execute('DELETE FROM passages WHERE number=?', (number,))
    db.execute('DELETE FROM documents WHERE number=?', (number,))


def index_pending(db, provider, limit=100):
    """Retry durable missing/stale versions, even when the catalog has no changes."""
    rows = db.execute('SELECT c.number,c.version,COALESCE(r.attempts,0) AS attempts,'
                      "COALESCE(r.failures,'[]') AS failures FROM catalog c "
                      'LEFT JOIN documents d ON d.number=c.number '
                      'LEFT JOIN index_retries r ON r.number=c.number AND r.version=c.version '
                      'WHERE ' + PENDING + " AND c.version IS NOT NULL AND c.version<>'' "
                      'AND COALESCE(r.attempts,0)<? AND COALESCE(r.next_retry_at,0)<=? '
                      'ORDER BY COALESCE(r.next_retry_at,0),c.number LIMIT ?',
                      (MAX_ATTEMPTS, time.time(), limit)).fetchall()
    for row in rows:
        number, version = row['number'], row['version']
        # A failed replacement must not commit the DELETE or any partial FTS inserts.
        db.execute('SAVEPOINT index_document')
        try:
            document = provider.agent_document(number, version)
            if str(document.get('version')) != version:
                raise ValueError('version_mismatch')
            html = document.get('html')
            if not isinstance(html, str) or not html.strip():
                raise ValueError('missing_document_html')
            store_document(db, number, version, document.get('source'), passages(html))
        except Exception as failure:
            db.execute('ROLLBACK TO index_document')
            error = getattr(failure, 'code', None) or type(failure).__name__
            attempts = row['attempts'] + 1
            failures = json.loads(row['failures']) + [{'at': now(), 'error': error}]
            due = time.time() + min(1800, RETRY_DELAY * 2 ** (attempts - 1)) if attempts < MAX_ATTEMPTS else None
            db.execute('INSERT INTO index_retries(number,version,attempts,next_retry_at,error,failures) '
                       'VALUES(?,?,?,?,?,?) ON CONFLICT(number,version) DO UPDATE SET '
                       'attempts=excluded.attempts,next_retry_at=excluded.next_retry_at,error=excluded.error,'
                       'failures=excluded.failures,resolved_at=NULL',
                       (number, version, attempts, due, error, json.dumps(failures)))
            db.execute('UPDATE catalog SET error=? WHERE number=?', (error, number))
        else:
            db.execute('UPDATE catalog SET error=NULL WHERE number=?', (number,))
            db.execute('UPDATE index_retries SET next_retry_at=NULL,resolved_at=? WHERE number=? AND version=?',
                       (now(), number, version))
        finally:
            db.execute('RELEASE index_document')
        db.commit()
    return len(rows)


def run_fulltext_index(config, max_rows=None, once=False, providers=None, retry_failed=False):
    """Follow the provider's catalog of cached documents; never asks for new acquisition."""
    if providers is None:
        from .resources import ResourceProviders
        providers = ResourceProviders(config, 'reader')
    provider = catalog_provider(providers)
    lock = (state_dir() / 'fulltext.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another full-text indexer is running') from None
    db = connect('fulltext.sqlite')
    try:
        initialize(db)
        if retry_failed:
            # Explicit operator retry grants a new bounded budget but retains failure history.
            db.execute('UPDATE index_retries SET attempts=0,next_retry_at=0 WHERE resolved_at IS NULL')
            db.commit()
        meta = metadata(db)
        cursor, processed = meta.get('catalog_cursor'), 0
        if meta.get('phase') != 'ready':
            save_meta(db, phase='building', started_at=meta.get('started_at') or now())
            db.commit()
        while True:
            page = provider.agent_document_catalog(cursor, 100)
            items = page.get('items') if isinstance(page, dict) else None
            if not isinstance(items, list):
                raise RuntimeError('Invalid document catalog page')
            for item in items:
                number, version = str(item.get('number') or ''), str(item.get('version') or '')
                state = str(item.get('state') or '')
                if not re.fullmatch(r'[0-9]{1,64}', number):
                    continue
                error = 'missing_version' if state in INDEXABLE and not version else None
                if state not in INDEXABLE:
                    remove_document(db, number)
                db.execute('INSERT INTO catalog(number,version,state,source,seen_at,error) VALUES(?,?,?,?,?,?) '
                           'ON CONFLICT(number) DO UPDATE SET version=excluded.version,state=excluded.state,'
                           'source=excluded.source,seen_at=excluded.seen_at,error=CASE '
                           "WHEN catalog.version IS excluded.version AND excluded.state IN ('ready','partial') "
                           'THEN catalog.error ELSE excluded.error END',
                           (number, version or None, state or 'unknown', item.get('source'), now(), error))
            cursor = page.get('cursor', cursor)
            more = bool(page.get('more'))
            total = page.get('total')
            save_meta(db, catalog_cursor=cursor, checked_at=now(), error=None,
                      **({'catalog_total': total} if isinstance(total, int) and total >= 0 else {}),
                      **({} if more else {'phase': 'ready', 'synced_at': now()}))
            db.commit()
            # Commit discovery before reading bodies; a crash cannot lose a failed item
            # behind the cursor. At the catalog tail, drain all currently due work.
            while True:
                attempted = index_pending(db, provider)
                processed += attempted
                if more or not attempted or (max_rows is not None and processed >= max_rows):
                    break
            if max_rows is not None and processed >= max_rows:
                return status_from(db)
            if not more:
                if once:
                    return status_from(db)
                time.sleep(30)
    except BaseException as failure:
        db.rollback()
        try:
            save_meta(db, error=type(failure).__name__, checked_at=now())
            db.commit()
        except sqlite3.Error:
            pass
        raise
    finally:
        db.close()
        lock.close()


# ---------- Coverage ----------

def status_from(db):
    meta = metadata(db)
    documents = db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    cataloged = db.execute("SELECT COUNT(*) FROM catalog WHERE state IN ('ready','partial')").fetchone()[0]
    pending = db.execute('SELECT COUNT(*) FROM catalog c LEFT JOIN documents d ON d.number=c.number WHERE ' + PENDING).fetchone()[0]
    failed = db.execute('SELECT COUNT(*) FROM catalog c LEFT JOIN documents d ON d.number=c.number WHERE '
                        + PENDING + ' AND c.error IS NOT NULL').fetchone()[0]
    blocked, next_retry_at = 0, None
    # Reader processes may see a pre-upgrade index before the indexer migrates it.
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='index_retries'").fetchone():
        retry = db.execute('SELECT COALESCE(SUM(r.attempts>=?),0),MIN(r.next_retry_at),'
                           'COALESCE(SUM(c.error IS NOT NULL OR (r.error IS NOT NULL AND r.resolved_at IS NULL)),0) '
                           'FROM catalog c LEFT JOIN documents d ON d.number=c.number '
                           'LEFT JOIN index_retries r ON r.number=c.number AND r.version=c.version WHERE ' + PENDING,
                           (MAX_ATTEMPTS,)).fetchone()
        blocked, next_retry_at, failed = retry
    return {'enabled': True, 'phase': meta.get('phase', 'building'), 'documents': documents, 'cataloged': cataloged,
            'pending': pending, 'failed': failed, 'blocked': blocked, 'next_retry_at': next_retry_at,
            'catalog_total': meta.get('catalog_total'), 'synced_at': meta.get('synced_at'),
            'checked_at': meta.get('checked_at'), 'error': meta.get('error')}


_STATUS = {}


def status():
    """Coverage counts, recomputed only after the index file changes."""
    if not path().exists():
        return {'enabled': False, 'phase': 'missing', 'documents': 0, 'cataloged': 0, 'pending': 0}
    snapshot = path().stat()
    key = (snapshot.st_ino, snapshot.st_mtime_ns, snapshot.st_size)
    if _STATUS.get('key') == key:
        return dict(_STATUS['value'])
    with closing(connect('fulltext.sqlite')) as db:
        try:
            value = status_from(db)
        except sqlite3.OperationalError:
            return {'enabled': False, 'phase': 'missing', 'documents': 0, 'cataloged': 0, 'pending': 0}
    _STATUS.update(key=key, value=value)
    return dict(value)


def paper_state(db, number, prefix=''):
    meta = {row['key']: json.loads(row['value']) for row in db.execute('SELECT key,value FROM ' + prefix + 'meta')}
    document = db.execute('SELECT version FROM ' + prefix + 'documents WHERE number=?', (number,)).fetchone()
    entry = db.execute('SELECT version,state,error FROM ' + prefix + 'catalog WHERE number=?', (number,)).fetchone()
    if document and (not entry or entry['version'] == document['version']):
        return 'indexed', document['version']
    if entry and entry['state'] in INDEXABLE:
        return 'not_indexed', entry['version']
    if entry or meta.get('phase') == 'ready':
        return 'no_body', None
    return 'unknown', None


# ---------- Matching ----------

def plan(query, terms):
    """Sentences try an exact token sequence first; otherwise words/phrases must share a passage."""
    groups = parse(query, terms)
    if not groups:
        raise ValueError('Enter a searchable word')
    words = tokens(query)
    sentence = len(words) >= SENTENCE and all(group['kind'] != 'phrase' for group in groups)
    # Approximate matching keeps content words; very short tokens are often fragments of
    # inline formulas that a cached body represents differently.
    distinctive = list(dict.fromkeys(word for word in words if word not in STOP and (len(word) > 2 or word.isdigit())))
    if len(distinctive) < 2:
        distinctive = list(dict.fromkeys(word for word in words if word not in STOP)) or list(dict.fromkeys(words))
    return {'groups': groups, 'words': words, 'sentence': sentence, 'distinctive': distinctive}


def mode_expression(query_plan, mode):
    if mode == 'exact':
        return phrase_expression(query_plan['words'])
    if mode == 'approximate':
        return ' AND '.join('"' + word.replace('"', '""') + '"' for word in query_plan['distinctive'])
    return fts_expression(query_plan['groups'])


def alternatives(query_plan, mode):
    if mode == 'exact':
        return [[tuple(query_plan['words'])]]
    if mode == 'approximate':
        return [[(word,)] for word in query_plan['distinctive']]
    return [group['alternatives'] for group in query_plan['groups']]


def match_passage(text, groups, mode='terms'):
    """Highlight ranges when the passage matches, otherwise None. Approximate matches need
    most content words; every other mode needs every group."""
    ranges, present, words = [], 0, spans(text)
    for options in groups:
        found = locate(text, options, words)
        if found:
            present += 1
            ranges.extend(found)
        elif mode != 'approximate':
            return None
    if mode == 'approximate' and present < max(2, COVERAGE * len(groups)):
        return None
    return ranges


def public_passage(row, ranges, query_plan, mode):
    return {'ordinal': row['ordinal'], 'kind': row['kind'], 'section': row['section'], 'section_id': row['section_id'],
            'version': row['version'], 'fingerprint': fingerprint(row['text']), 'match': mode,
            'excerpt': excerpt(row['text'], ranges)}


def paper_hits(db, number, query_plan, mode, prefix=''):
    rows = db.execute('SELECT ordinal,kind,section,section_id,text,version FROM ' + prefix + 'passages '
                      'WHERE number=? ORDER BY ordinal', (number,)).fetchall()
    groups, hits = alternatives(query_plan, mode), []
    for row in rows:
        ranges = match_passage(row['text'], groups, mode)
        if ranges is not None:
            hits.append((row, ranges))
    return hits


def public_plan(query_plan, mode, terms):
    return {'terms': terms, 'groups': describe(query_plan['groups']), 'match': mode,
            'alternatives': [[' '.join(option) for option in options] for options in alternatives(query_plan, mode)]}


# ---------- Search ----------

DOC_COLUMNS = ('d.number,d.doi,d.title,d.authors,d.publication,d.year,d.kind,d.venue,d.abstract_state,'
               'd.keywords_state,d.updated,d.order_number,substr(d.abstract,1,400) AS snippet')


def approximate_papers(db, query_plan):
    """Recall passages by the rarest content words, then keep those covering most words."""
    words = query_plan['distinctive']
    marks = ','.join('?' for _ in words)
    frequent = {row['term']: row['doc'] for row in db.execute('SELECT term,doc FROM ft.passage_vocab WHERE term IN (' + marks + ')', words)}
    rare = sorted((word for word in words if frequent.get(word)), key=lambda word: frequent[word])[:4]
    if len(rare) < 2:
        return {}, False
    expression = ' AND '.join('"' + word.replace('"', '""') + '"' for word in rare)
    rows = db.execute('SELECT p.number,p.text,passage_search.rank AS rank FROM ft.passage_search CROSS JOIN ft.passages p '
                      'ON p.id=passage_search.rowid WHERE passage_search MATCH ? ORDER BY rank LIMIT ?',
                      (expression, APPROXIMATE_LIMIT + 1)).fetchall()
    groups, papers = alternatives(query_plan, 'approximate'), {}
    for row in rows[:APPROXIMATE_LIMIT]:
        ranges = match_passage(row['text'], groups, 'approximate')
        if ranges is None:
            continue
        coverage = len({key for _, _, key in ranges}) / len(groups)
        entry = papers.setdefault(row['number'], {'best': row['rank'], 'coverage': coverage})
        entry['best'], entry['coverage'] = min(entry['best'], row['rank']), max(entry['coverage'], coverage)
    return papers, len(rows) > APPROXIMATE_LIMIT


def search_body(params):
    """Papers whose indexed body passages match; exact totals, cursor pages, metadata filters."""
    from .index import filter_clauses, metadata as index_metadata, validate_year_range
    from .venues import parse_venue_any
    totals = params.get('totals', 'include')
    if totals not in ('include', 'defer', 'only'):
        raise ValueError('Invalid totals mode')
    view = params.get('view', 'all')
    if view not in ('all', 'top'):
        raise ValueError('Invalid result view')
    years = validate_year_range(params)
    query = str(params.get('q') or '').strip()
    if len(query) > 600:
        raise ValueError('Full-text search is limited to 600 characters')
    terms = params.get('terms') or 'expand'
    if terms not in ('expand', 'exact'):
        raise ValueError('Invalid term mode')
    size = max(1, min(100, int(params.get('k' if view == 'top' else 'limit', 20 if view == 'top' else 25))))
    order = params.get('sort', 'relevance')
    if order not in ('relevance', 'year'):
        raise ValueError('Invalid sort order')
    coverage = status()
    empty = {'items': [], 'total': 0, 'next_cursor': None, 'view': view, 'fulltext': coverage, 'partial': False}
    if not query or not coverage['enabled']:
        return {**empty, 'query': {'terms': terms}}
    query_plan = plan(query, terms)
    key = hashlib.sha256(json.dumps({k: str(v) for k, v in sorted(params.items()) if k not in ('cursor', 'totals')},
                                    sort_keys=True).encode()).hexdigest()[:16]
    relevance = view == 'top' or order == 'relevance'
    with closing(connect('search.sqlite')) as db:
        db.execute('ATTACH DATABASE ? AS ft', (str(path()),))
        db.execute('BEGIN')
        meta = index_metadata(db)
        started = time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic() - started > 6), 10000)
        clauses, args, _, _ = filter_clauses(db, params, years, parse_venue_any(params.get('venue_any')))
        # Counting and paging never compute BM25: scoring every passage of a common term is the
        # dominant cost. Relevance order uses matching passages; Top-K rescoring is bounded.
        hits = ('WITH hits AS (SELECT p.number AS number,COUNT(*) AS matches '
                'FROM ft.passage_search CROSS JOIN ft.passages p ON p.id=passage_search.rowid '
                'WHERE passage_search MATCH ? GROUP BY p.number) ')
        count_sql = hits + 'SELECT COUNT(*) FROM hits h CROSS JOIN docs d ON d.number=h.number' + ((' WHERE ' + ' AND '.join(clauses)) if clauses else '')
        mode = 'phrase' if all(group['kind'] == 'phrase' for group in query_plan['groups']) else 'terms'
        if query_plan['sentence']:
            mode = 'exact' if db.execute(count_sql, (mode_expression(query_plan, 'exact'), *args)).fetchone()[0] else 'approximate'
        cursor, exact_total = None, True
        if mode == 'approximate':
            # Candidate passages are materialized, so pages use an offset into one ordered set.
            papers, truncated = approximate_papers(db, query_plan)
            exact_total = not truncated
            rows = []
            numbers = list(papers)
            for offset in range(0, len(numbers), 400):
                chunk = numbers[offset:offset + 400]
                rows += [dict(row) for row in db.execute('SELECT ' + DOC_COLUMNS + ' FROM docs d WHERE d.number IN ('
                         + ','.join('?' for _ in chunk) + ')' + ''.join(' AND ' + clause for clause in clauses), (*chunk, *args))]
            for row in rows:
                row['best'], row['coverage'] = papers[row['number']]['best'], papers[row['number']]['coverage']
            rows.sort(key=(lambda r: (-r['coverage'], r['best'], r['number'])) if relevance
                      else (lambda r: (-r['year'], tuple(-ord(c) for c in r['order_number']), tuple(-ord(c) for c in r['number']))))
            total = None if totals == 'defer' else len(rows)
            start = 0
            if view == 'all' and params.get('cursor'):
                try:
                    token = json.loads(base64.urlsafe_b64decode(str(params['cursor']) + '==='))
                    if token['query'] != key or type(token['offset']) is not int or token['offset'] < 0:
                        raise ValueError()
                    start = token['offset']
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    raise ValueError('Invalid page cursor') from None
            if view == 'all' and start + size < len(rows):
                cursor = base64.urlsafe_b64encode(json.dumps({'query': key, 'offset': start + size}).encode()).decode().rstrip('=')
            rows = [] if totals == 'only' else rows[start:start + size]
        else:
            expression = mode_expression(query_plan, mode)
            total = None if totals == 'defer' else db.execute(count_sql, (expression, *args)).fetchone()[0]
            page_clauses, page_args = list(clauses), list(args)
            if view == 'all' and params.get('cursor'):
                try:
                    token = json.loads(base64.urlsafe_b64decode(str(params['cursor']) + '==='))
                    if token['query'] != key:
                        raise ValueError()
                    if relevance:
                        page_clauses.append('(h.matches<? OR (h.matches=? AND d.number>?))')
                        page_args += [int(token['matches']), int(token['matches']), str(token['number'])]
                    else:
                        page_clauses.append('(d.year<? OR (d.year=? AND (d.order_number<? OR (d.order_number=? AND d.number<?))))')
                        page_args += [int(token['year']), int(token['year']), str(token['order_number']), str(token['order_number']), str(token['number'])]
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    raise ValueError('Invalid page cursor') from None
            sort = 'h.matches DESC,d.number' if relevance else 'd.year DESC,d.order_number DESC,d.number DESC'
            limit = TOP_CANDIDATES if view == 'top' else size + 1
            rows = [] if totals == 'only' else [dict(row) for row in db.execute(
                hits + 'SELECT ' + DOC_COLUMNS + ',h.matches FROM hits h CROSS JOIN docs d ON d.number=h.number'
                + ((' WHERE ' + ' AND '.join(page_clauses)) if page_clauses else '') + ' ORDER BY ' + sort + ' LIMIT ?',
                (expression, *page_args, limit))]
            if view == 'top' and rows:
                # BM25 for the passages of the candidate papers only.
                marks = ','.join('?' for _ in rows)
                best = {row['number']: row['best'] for row in db.execute(
                    'SELECT p.number AS number,MIN(passage_search.rank) AS best FROM ft.passage_search CROSS JOIN ft.passages p '
                    'ON p.id=passage_search.rowid WHERE passage_search MATCH ? AND p.number IN (' + marks + ') GROUP BY p.number',
                    (expression, *[row['number'] for row in rows]))}
                for row in rows:
                    row['best'] = best.get(row['number'], 0.0)
                rows.sort(key=lambda r: (r['best'], -r['matches'], r['number']))
            if view == 'all' and len(rows) > size:
                last = rows[size - 1]
                cursor = base64.urlsafe_b64encode(json.dumps({'query': key, **{k: last[k] for k in ('matches', 'number', 'year', 'order_number')}}).encode()).decode().rstrip('=')
            rows = rows[:size]
            for row in rows:
                row.setdefault('best', None)
        for position, row in enumerate(rows, 1):
            found = paper_hits(db, row['number'], query_plan, mode, 'ft.')
            # Show the passages matching the most query parts, in reading order.
            best = sorted(found, key=lambda hit: (-len({key for _, _, key in hit[1]}), hit[0]['kind'] == 'heading', hit[0]['ordinal']))[:3]
            row['passages'] = [public_passage(hit, ranges, query_plan, mode) for hit, ranges in best]
            row['passage_total'] = len(found)
            row['rank'] = row.pop('best')
            row.pop('coverage', None)
            row.pop('matches', None)
            if view == 'top':
                row['position'] = position
        return {'items': rows, 'total': total, 'total_exact': exact_total, 'next_cursor': cursor, 'view': view,
                'fulltext': coverage, 'query': public_plan(query_plan, mode, terms), 'index': meta,
                **({'k': size} if view == 'top' else {}),
                'partial': coverage.get('phase') != 'ready' or bool(coverage.get('pending')) or bool(coverage.get('error'))}


def paper_passages(number, params):
    query = str(params.get('q') or '').strip()
    terms = params.get('terms') or 'expand'
    if terms not in ('expand', 'exact') or len(query) > 600:
        raise ValueError('Invalid full-text query')
    offset = max(0, int(params.get('offset', 0)))
    limit = max(1, min(200, int(params.get('limit', 50))))
    if not path().exists():
        return {'number': number, 'state': 'disabled', 'items': [], 'total': 0, 'next_offset': None}
    with closing(connect('fulltext.sqlite')) as db:
        state, version = paper_state(db, number)
        result = {'number': number, 'state': state, 'version': version, 'items': [], 'total': 0, 'next_offset': None}
        if state != 'indexed' or not query:
            return result
        query_plan = plan(query, terms)
        mode = 'phrase' if all(group['kind'] == 'phrase' for group in query_plan['groups']) and not query_plan['sentence'] else 'terms'
        found = []
        if query_plan['sentence']:
            mode = 'exact'
            found = paper_hits(db, number, query_plan, mode)
            if not found:
                mode = 'approximate'
        if not found:
            found = paper_hits(db, number, query_plan, mode)
        page = found[offset:offset + limit]
        return {**result, 'items': [public_passage(row, ranges, query_plan, mode) for row, ranges in page], 'total': len(found),
                'next_offset': offset + limit if offset + limit < len(found) else None, 'query': public_plan(query_plan, mode, terms)}
