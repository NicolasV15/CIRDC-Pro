"""Source-scoped author identities and ordered paper signatures; names are not keys."""
import hashlib
import json
import re
import time
from contextlib import closing
from datetime import datetime, timezone
from html import unescape
from .settings import connect


def clean(value):
    return ' '.join(unescape(re.sub(r'<[^>]*>', '', str(value or ''))).split())


def author_references(record):
    result = []
    for ordinal, raw in enumerate(record.get('authors') or []):
        if not isinstance(raw, dict):
            continue
        value = raw.get('id')
        identifier = str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else ''
        if identifier in ('0', 'None', 'null'):
            identifier = ''
        name = clean(raw.get('preferredName') or ' '.join(str(raw.get(k) or '') for k in ['firstName', 'lastName']))
        result.append({'source': 'ieee', 'author_id': identifier or None, 'name': name, 'ordinal': ordinal})
    return result


def identity(reference, paper_number):
    if reference['author_id']:
        return reference['source'] + ':' + reference['author_id']
    name = reference['name'].casefold()
    if name:
        return 'unidentified-name:' + hashlib.sha256(name.encode()).hexdigest()
    return 'unidentified-signature:' + str(paper_number) + ':' + str(reference['ordinal'])


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS author_entities(
      identity_key TEXT PRIMARY KEY,source TEXT NOT NULL,author_id TEXT,
      display_name TEXT NOT NULL,identified INTEGER NOT NULL);
    CREATE UNIQUE INDEX IF NOT EXISTS author_external_id ON author_entities(source,author_id);
    CREATE TABLE IF NOT EXISTS author_names(
      id INTEGER PRIMARY KEY,identity_key TEXT NOT NULL,name TEXT NOT NULL,normalized TEXT NOT NULL,
      UNIQUE(identity_key,normalized));
    CREATE INDEX IF NOT EXISTS author_names_identity ON author_names(identity_key);
    CREATE VIRTUAL TABLE IF NOT EXISTS author_search USING fts5(name,
      content='author_names',content_rowid='id',tokenize='unicode61 remove_diacritics 2');
    CREATE TRIGGER IF NOT EXISTS author_names_insert AFTER INSERT ON author_names BEGIN
      INSERT INTO author_search(rowid,name) VALUES(new.id,new.name); END;
    CREATE TABLE IF NOT EXISTS paper_authors(
      doc_id INTEGER NOT NULL,ordinal INTEGER NOT NULL,identity_key TEXT NOT NULL,
      name TEXT NOT NULL,PRIMARY KEY(doc_id,ordinal));
    CREATE TRIGGER IF NOT EXISTS author_paper_delete AFTER DELETE ON docs BEGIN
      DELETE FROM paper_authors WHERE doc_id=old.id; END;
    ''')
    db.execute('INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)', ('authors_phase', json.dumps('building')))
    db.commit()


def sync_rows(db, rows, build_entities=True):
    if not rows:
        return 0
    entities, aliases, relations = {}, {}, []
    signatures = 0
    for offset in range(0, len(rows), 500):
        chunk = rows[offset:offset + 500]
        identifiers = [str(r['number']) for r in chunk]
        documents = {r['number']: r['id'] for r in db.execute('SELECT number,id FROM docs WHERE number IN ('
                       + ','.join('?' for _ in identifiers) + ')', identifiers)}
        doc_ids = list(documents.values())
        if doc_ids:
            db.execute('DELETE FROM paper_authors WHERE doc_id IN (' + ','.join('?' for _ in doc_ids) + ')', doc_ids)
        for row in chunk:
            number = str(row['number'])
            if number not in documents:
                continue
            raw = row['data']
            record = json.loads(raw) if isinstance(raw, str) else raw
            for ref in author_references(record):
                key = identity(ref, number)
                value = (key, ref['source'], ref['author_id'], ref['name'], int(bool(ref['author_id'])))
                if build_entities:
                    previous = entities.get(key)
                    if previous is None or len(ref['name']) > len(previous[3]):
                        entities[key] = value
                    if ref['name']:
                        aliases[(key, ref['name'].casefold())] = (key, ref['name'], ref['name'].casefold())
                relations.append((documents[number], ref['ordinal'], key, ref['name']))
                signatures += 1
    db.executemany('INSERT INTO author_entities(identity_key,source,author_id,display_name,identified) VALUES(?,?,?,?,?) '
                   'ON CONFLICT(identity_key) DO UPDATE SET display_name=CASE '
                   'WHEN length(excluded.display_name)>length(display_name) THEN excluded.display_name ELSE display_name END',
                   entities.values())
    db.executemany('INSERT OR IGNORE INTO author_names(identity_key,name,normalized) VALUES(?,?,?)', aliases.values())
    db.executemany('INSERT INTO paper_authors(doc_id,ordinal,identity_key,name) VALUES(?,?,?,?)', relations)
    return signatures


def backfill_step(store, db, limit=1000):
    from .index import metadata, save_meta
    meta = metadata(db)
    if meta.get('authors_phase') == 'ready':
        return False
    if meta.get('authors_phase') == 'name_search':
        return finish_backfill(db)
    if meta.get('authors_phase') == 'consolidating':
        return consolidate_step(db, meta)
    if not meta.get('authors_bulk_v2'):
        db.execute('DROP INDEX IF EXISTS papers_by_author')
        save_meta(db, authors_bulk_v2=True)
        db.commit()
    last = meta.get('authors_last_number', '')
    store.db.rollback()
    rows = store.execute("SELECT number,JSON_EXTRACT(data,'$.authors') AS author_data FROM papers "
                         'WHERE number>%s ORDER BY number LIMIT %s', (last, limit))
    store.db.commit()
    if not rows:
        save_meta(db, authors_phase='consolidating')
        db.commit()
        db.execute('CREATE INDEX IF NOT EXISTS papers_by_author ON paper_authors(identity_key,doc_id)')
        db.commit()
        return True
    records = [{'number': r['number'], 'data': {'authors': json.loads(r['author_data']) if r['author_data'] else []}} for r in rows]
    signatures = sync_rows(db, records, build_entities=False)
    save_meta(db, authors_phase='building', authors_last_number=rows[-1]['number'],
              authors_papers_seen=meta.get('authors_papers_seen', 0) + len(rows),
              authors_signatures_seen=meta.get('authors_signatures_seen', 0) + signatures,
              authors_checked_at=datetime.now(timezone.utc).isoformat())
    db.commit()
    return True


def consolidate_step(db, meta, limit=20000):
    from .index import save_meta
    db.execute('CREATE INDEX IF NOT EXISTS papers_by_author ON paper_authors(identity_key,doc_id)')
    # Defer derived name postings until all aliases are collected. Rebuild is atomic
    # and resumable; live events still update relations and the alias table.
    db.execute('DROP TRIGGER IF EXISTS author_names_insert')
    last = meta.get('authors_last_identity', '')
    keys = db.execute('SELECT DISTINCT identity_key FROM paper_authors WHERE identity_key>? '
                      'ORDER BY identity_key LIMIT ?', (last, limit)).fetchall()
    if not keys:
        save_meta(db, authors_phase='name_search')
        db.commit()
        return True
    end = keys[-1]['identity_key']
    names = db.execute('SELECT identity_key,name FROM paper_authors WHERE identity_key>? AND identity_key<=? '
                       'ORDER BY identity_key', (last, end)).fetchall()
    entities, aliases = {}, {}
    for row in names:
        key, name = row['identity_key'], row['name']
        identified = key.startswith('ieee:')
        value = (key, 'ieee', key[5:] if identified else None, name, int(identified))
        if key not in entities or len(name) > len(entities[key][3]):
            entities[key] = value
        if name:
            aliases[(key, name.casefold())] = (key, name, name.casefold())
    db.executemany('INSERT INTO author_entities(identity_key,source,author_id,display_name,identified) VALUES(?,?,?,?,?) '
                   'ON CONFLICT(identity_key) DO UPDATE SET display_name=CASE '
                   'WHEN length(excluded.display_name)>length(display_name) THEN excluded.display_name ELSE display_name END',
                   entities.values())
    db.executemany('INSERT OR IGNORE INTO author_names(identity_key,name,normalized) VALUES(?,?,?)', aliases.values())
    save_meta(db, authors_last_identity=end, authors_identities_built=meta.get('authors_identities_built', 0) + len(keys))
    db.commit()
    return True


def finish_backfill(db):
    from .index import save_meta
    db.execute("INSERT INTO author_search(author_search) VALUES('rebuild')")
    db.execute("""CREATE TRIGGER IF NOT EXISTS author_names_insert AFTER INSERT ON author_names BEGIN
      INSERT INTO author_search(rowid,name) VALUES(new.id,new.name); END""")
    timestamp = datetime.now(timezone.utc).isoformat()
    save_meta(db, authors_phase='ready', authors_completed_at=timestamp, authors_checked_at=timestamp,
              authors_identities=db.execute('SELECT COUNT(*) FROM author_entities WHERE identified=1').fetchone()[0],
              authors_signatures=db.execute('SELECT COUNT(*) FROM paper_authors').fetchone()[0])
    db.commit()
    return False


def matching_keys(db, query, unidentified=False):
    query = query.strip()
    if not query or len(query) > 200:
        raise ValueError('Enter an author name or source identifier')
    if query.isdigit():
        return 'SELECT identity_key FROM author_entities WHERE source=? AND author_id=?', ['ieee', query]
    words = re.findall(r'[^\W_]+', query, re.UNICODE)
    if not words:
        raise ValueError('Enter a searchable author name')
    expression = ' AND '.join('"' + w + '"' for w in words[:30])
    sql = ('SELECT DISTINCT n.identity_key FROM author_search CROSS JOIN author_names n ON n.id=author_search.rowid '
           'JOIN author_entities e ON e.identity_key=n.identity_key WHERE author_search MATCH ?')
    args = [expression]
    if unidentified:
        sql += ' AND e.identified=0'
    return sql, args


def add_filter(db, params, clauses, args):
    source = params.get('author_source') or 'ieee'
    author_id = str(params.get('author_id') or '').strip()
    if source != 'ieee' or len(author_id) > 128:
        raise ValueError('Invalid source author reference')
    if author_id:
        clauses.append('d.id IN (SELECT doc_id FROM paper_authors WHERE identity_key=?)')
        args.append(source + ':' + author_id)
        return True
    if params.get('field') == 'authors' and str(params.get('q') or '').strip():
        sql, values = matching_keys(db, str(params['q']), params.get('author_unidentified') == '1')
        clauses.append('d.id IN (SELECT doc_id FROM paper_authors WHERE identity_key IN (' + sql + '))')
        args.extend(values)
        return True
    return False


def summary(db, key):
    row = db.execute('SELECT * FROM author_entities WHERE identity_key=?', (key,)).fetchone()
    if not row:
        return None
    value = dict(row)
    stats = db.execute('SELECT COUNT(DISTINCT a.doc_id) AS papers,MIN(d.year) AS first_year,MAX(d.year) AS last_year '
                       'FROM paper_authors a CROSS JOIN docs d INDEXED BY docs_facets_by_id ON d.id=a.doc_id '
                       'WHERE a.identity_key=?', (key,)).fetchone()
    value.update(dict(stats))
    value['name_variants'] = [r['name'] for r in db.execute('SELECT name FROM author_names WHERE identity_key=? ORDER BY name LIMIT 20', (key,))]
    value['profile_ref'] = {'source': value['source'], 'author_id': value['author_id']} if value['identified'] else None
    return value


def find_authors(params):
    from .index import metadata
    query = str(params.get('q') or '').strip()
    size = max(1, min(50, int(params.get('limit', 20))))
    with closing(connect('search.sqlite')) as db:
        meta = metadata(db)
        started = time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic() - started > 5), 10000)
        sql, args = matching_keys(db, query)
        cursor = str(params.get('cursor') or '')
        keys = db.execute('SELECT e.identity_key FROM author_entities e WHERE e.identified=1 '
                          'AND e.identity_key IN (' + sql + ') AND e.identity_key>? '
                          'AND EXISTS (SELECT 1 FROM paper_authors a WHERE a.identity_key=e.identity_key) '
                          'ORDER BY e.identity_key LIMIT ?', (*args, cursor, size + 1)).fetchall()
        next_cursor = keys[size-1]['identity_key'] if len(keys) > size else None
        items = [summary(db, row['identity_key']) for row in keys[:size]]
        unknown_sql, unknown_args = matching_keys(db, query, True)
        if query.isdigit():
            unidentified = 0
        else:
            unidentified = db.execute('SELECT COUNT(DISTINCT doc_id) FROM paper_authors WHERE identity_key IN ('
                                      + unknown_sql + ')', unknown_args).fetchone()[0]
        return {'items': items, 'next_cursor': next_cursor, 'unidentified_papers': unidentified,
                'partial': meta.get('authors_phase') != 'ready',
                'index': {k: meta.get(k) for k in ['authors_phase', 'authors_papers_seen', 'authors_identities', 'authors_signatures']}}


def get_author(source, identifier):
    if source != 'ieee' or not identifier or len(identifier) > 128:
        raise ValueError('Invalid source author reference')
    with closing(connect('search.sqlite')) as db:
        return summary(db, source + ':' + str(identifier))


def attach_author_references(items):
    """Read ordered signatures for one result page without loading full records."""
    if not items:
        return
    numbers = list(dict.fromkeys(str(item['number']) for item in items))
    references = {number: [] for number in numbers}
    with closing(connect('search.sqlite')) as db:
        for offset in range(0, len(numbers), 100):
            chunk = numbers[offset:offset + 100]
            rows = db.execute('SELECT d.number,a.ordinal,a.identity_key,a.name FROM docs d '
                              'CROSS JOIN paper_authors a ON a.doc_id=d.id WHERE d.number IN ('
                              + ','.join('?' for _ in chunk) + ') ORDER BY d.number,a.ordinal', chunk)
            for row in rows:
                key = row['identity_key']
                references[row['number']].append({'source': 'ieee',
                    'author_id': key[5:] if key.startswith('ieee:') else None,
                    'name': row['name'], 'ordinal': row['ordinal']})
    for item in items:
        item['author_refs'] = references[str(item['number'])]
