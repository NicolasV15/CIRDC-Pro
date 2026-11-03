"""Optional references schema and explicit-ID queue; never scans a catalog."""
import hashlib
import json
import re
import uuid
from contextlib import ExitStack
from datetime import datetime, timezone

from .config import Config
from .model import digest
from .reference_source import article_id
from .storage import Dataset
from .store import Store

VERSION = 1
COMMENT = 'cirdc.references.v1'
TABLES = {
    'reference_schema_migrations': ('version,applied_at', 'version INT PRIMARY KEY,applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
    'paper_reference_state': (
        'number,state,version,total,expected_total,checked_at,error,run_id,task_id',
        "number VARCHAR(64) PRIMARY KEY,state VARCHAR(24) NOT NULL,version CHAR(32) NULL,"
        "total INT UNSIGNED NOT NULL DEFAULT 0,expected_total INT UNSIGNED NULL,checked_at DATETIME(6) NULL,"
        "error VARCHAR(64) NULL,run_id CHAR(32) NULL,task_id BIGINT NULL,INDEX reference_queue(state,number)"),
    'paper_reference_snapshots': (
        'number,version,state,total,expected_total,fetched_at,digest',
        'number VARCHAR(64) NOT NULL,version CHAR(32) NOT NULL,state VARCHAR(24) NOT NULL,'
        'total INT UNSIGNED NOT NULL,expected_total INT UNSIGNED NULL,fetched_at DATETIME(6) NOT NULL,'
        'digest CHAR(64) NOT NULL,PRIMARY KEY(number,version)'),
    'paper_references': (
        'number,version,ordinal,target_number,data',
        'number VARCHAR(64) NOT NULL,version CHAR(32) NOT NULL,ordinal INT UNSIGNED NOT NULL,'
        'target_number VARCHAR(64) NULL,data LONGTEXT NOT NULL,PRIMARY KEY(number,version,ordinal),'
        'INDEX reference_target(target_number,number)'),
}


def check(store):
    rows = store.execute('SELECT TABLE_NAME,TABLE_COMMENT,ENGINE,TABLE_COLLATION FROM information_schema.tables '
                         'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (' + ','.join(['%s'] * len(TABLES)) + ')', tuple(TABLES))
    if not rows:
        return False
    if {r['TABLE_NAME'] for r in rows} != set(TABLES):
        raise ValueError('references_schema_mismatch')
    for row in rows:
        name = row['TABLE_NAME']
        columns = store.execute('SHOW FULL COLUMNS FROM `' + name + '`')
        expected = TABLES[name][0].split(',')
        if (row['TABLE_COMMENT'] != COMMENT or row['ENGINE'] != 'InnoDB'
                or not row['TABLE_COLLATION'].startswith('utf8mb4_')
                or [c['Field'] for c in columns] != expected):
            raise ValueError('references_schema_mismatch')
        types = {'number': 'varchar(64)', 'state': 'varchar(24)', 'version': 'char(32)',
                 'total': 'int unsigned', 'expected_total': 'int unsigned', 'checked_at': 'datetime(6)',
                 'error': 'varchar(64)', 'run_id': 'char(32)', 'task_id': 'bigint',
                 'fetched_at': 'datetime(6)', 'digest': 'char(64)', 'ordinal': 'int unsigned',
                 'target_number': 'varchar(64)', 'data': 'longtext', 'applied_at': 'timestamp'}
        nullable = {'version', 'expected_total', 'checked_at', 'error', 'run_id', 'task_id'} if name == 'paper_reference_state' else (
            {'expected_total'} if name == 'paper_reference_snapshots' else {'target_number'} if name == 'paper_references' else {'applied_at'})
        for column in columns:
            key = column['Field']
            kind = re.sub(r'\b(int|bigint)\(\d+\)', r'\1', column['Type'].lower())
            wanted_type = 'int' if name == 'reference_schema_migrations' and key == 'version' else types[key]
            if (kind != wanted_type or (key != 'applied_at' and (column['Null'] == 'YES') != (key in nullable))
                    or (column.get('Collation') and column['Collation'] != 'utf8mb4_bin')):
                raise ValueError('references_schema_mismatch')
            if name == 'paper_reference_state' and key == 'total' and str(column['Default']) != '0':
                raise ValueError('references_schema_mismatch')
        keys = store.execute('SHOW INDEX FROM `' + name + '`')
        primary = [k['Column_name'] for k in sorted(keys, key=lambda k: k['Seq_in_index']) if k['Key_name'] == 'PRIMARY']
        wanted = ['version'] if name == 'reference_schema_migrations' else ['number']
        if name in ('paper_reference_snapshots', 'paper_references'):
            wanted += ['version']
        if name == 'paper_references':
            wanted += ['ordinal']
        if primary != wanted:
            raise ValueError('references_schema_mismatch')
        secondary = {}
        for key in sorted(keys, key=lambda k: k['Seq_in_index']):
            if key['Key_name'] != 'PRIMARY':
                secondary.setdefault(key['Key_name'], []).append(key['Column_name'])
                if not key['Non_unique']:
                    raise ValueError('references_schema_mismatch')
        expected_secondary = {'reference_queue': ['state', 'number']} if name == 'paper_reference_state' else (
            {'reference_target': ['target_number', 'number']} if name == 'paper_references' else {})
        if secondary != expected_secondary:
            raise ValueError('references_schema_mismatch')
    if [r['version'] for r in store.execute('SELECT version FROM reference_schema_migrations ORDER BY version')] != [VERSION]:
        raise ValueError('references_schema_mismatch')
    return True


def initialize(store):
    store.require_schema(force=True)
    with store.lock('references-schema'):
        if not check(store):
            for name, (_, fields) in TABLES.items():
                store.execute('CREATE TABLE `' + name + '` (' + fields + ') ENGINE=InnoDB '
                              "DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='" + COMMENT + "'")
            store.execute('INSERT INTO reference_schema_migrations(version) VALUES (%s)', (VERSION,))
            store.db.commit()
        check(store)
    return {'status': 'ready', 'reference_schema_version': VERSION}


def require(store):
    store.require_schema()
    if not check(store):
        raise ValueError('references_not_initialized')


def enqueue(store, numbers, retry=False, check_availability=False):
    numbers = list(dict.fromkeys(article_id(n) for n in numbers))
    if not numbers or len(numbers) > 20:
        raise ValueError('Pass between 1 and 20 explicit article numbers')
    require(store)
    from .citations import available
    detector_enabled = available(store)
    queued, reused = [], []
    # A short enqueue lock serializes concurrent tabs, independent of the HTTP worker lease.
    with store.lock('references-enqueue'):
        store.db.commit()
        for number in numbers:
            if not store.execute('SELECT number FROM papers WHERE number=%s', (number,)):
                raise ValueError('paper_not_found')
        run_id = None
        for number in numbers:
            old = store.execute('SELECT * FROM paper_reference_state WHERE number=%s', (number,))
            recheck = False
            if check_availability and detector_enabled and old and old[0]['state'] == 'unavailable':
                evidence = store.execute('SELECT detector_version FROM paper_relationship_availability WHERE number=%s AND direction=%s', (number, 'references'))
                recheck = not evidence or evidence[0]['detector_version'] < 1
            if old and (not (retry or recheck) or old[0]['state'] in ('queued', 'fetching')):
                reused.append(number)
                continue
            if run_id is None:
                run_id = uuid.uuid4().hex
                store.execute('INSERT INTO runs(id,status,params,stats) VALUES (%s,%s,%s,%s)',
                              (run_id, 'references_pending', json.dumps({'stage': 'references', 'mode': 'paper_relationships', 'selection': numbers, 'explicit_ids': True}), '{}'))
            payload = {'number': number}
            if detector_enabled:
                payload['required_capability'] = 'paper_relationships_v1'
            store.execute('INSERT INTO tasks(run_id,kind,task_key,payload) VALUES (%s,%s,%s,%s)',
                          (run_id, 'references', number, json.dumps(payload)))
            task_id = store.execute('SELECT LAST_INSERT_ID() id')[0]['id']
            store.execute('INSERT INTO paper_reference_state(number,state,run_id,task_id) VALUES (%s,%s,%s,%s) '
                          "ON DUPLICATE KEY UPDATE state='queued',error=NULL,run_id=VALUES(run_id),task_id=VALUES(task_id)",
                          (number, 'queued', run_id, task_id))
            queued.append(number)
        store.db.commit()
    return {'status': 'queued' if queued else 'reused', 'run_id': run_id, 'queued': queued, 'reused': reused}


def publish_exports(store):
    rows = store.execute("SELECT e.* FROM exports e JOIN runs r ON r.id=e.run_id WHERE "
                         "JSON_UNQUOTE(JSON_EXTRACT(r.params,'$.stage'))='references' AND e.status='pending' ORDER BY e.id")
    for row in rows:
        storage = Dataset(store.config)
        if storage.remote:
            storage.publish(row)
        else:
            from pathlib import Path
            from .engine import atomic_write
            content = Path(row['staged_path']).read_bytes()
            if digest(content) != row['digest']:
                raise ValueError('Reference snapshot staging digest differs')
            atomic_write(store.config.destination(row['path']), content)
        store.execute("UPDATE exports SET status='done',error=NULL WHERE id=%s", (row['id'],))
        store.db.commit()


def apply_result(store, task, value):
    number = article_id(task['task_key'])
    current = store.execute('SELECT * FROM paper_reference_state WHERE number=%s FOR UPDATE', (number,))[0]
    if current['task_id'] != task['id']:
        raise ValueError('Reference result belongs to a superseded task')
    if value.get('error') == 'paused':
        store.execute("UPDATE paper_reference_state SET state='queued' WHERE number=%s", (number,))
        store.execute("UPDATE tasks SET status='pending' WHERE id=%s", (task['id'],))
        store.db.commit()
        return {'state': 'queued'}
    if value.get('error') and not isinstance(value.get('records'), dict):
        error = value['error']
        state = 'blocked' if error in ('access_restricted', 'access_denied') else 'failed'
        store.execute('UPDATE paper_reference_state SET state=%s,error=%s,checked_at=UTC_TIMESTAMP(6) WHERE number=%s',
                      (state, error[:64], number))
        store.execute('UPDATE tasks SET status=%s,error=%s WHERE id=%s', (state, error[:64], task['id']))
    else:
        result = value['records']
        if result['number'] != number or not re.fullmatch('[a-f0-9]{32}', result['version']):
            raise ValueError('Reference snapshot identity differs')
        if result['state'] not in ('complete', 'no_data', 'unavailable', 'partial', 'blocked', 'failed'):
            raise ValueError('Invalid reference result state')
        snapshot = json.dumps(result, ensure_ascii=False, sort_keys=True)
        sha = hashlib.sha256(snapshot.encode()).hexdigest()
        version, state = result['version'], result['state']
        previous = store.execute('SELECT digest FROM paper_reference_snapshots WHERE number=%s AND version=%s', (number, version))
        if previous and previous[0]['digest'] != sha:
            raise ValueError('Reference snapshot replay differs')
        if not previous:
            fetched = datetime.fromisoformat(result['fetched_at']).astimezone(timezone.utc).replace(tzinfo=None)
            store.execute('INSERT INTO paper_reference_snapshots(number,version,state,total,expected_total,fetched_at,digest) '
                          'VALUES (%s,%s,%s,%s,%s,%s,%s)',
                          (number, version, state, len(result['items']), result['expected_total'], fetched, sha))
            store.many('INSERT INTO paper_references(number,version,ordinal,target_number,data) VALUES (%s,%s,%s,%s,%s)',
                       [(number, version, item['order'], item['target_number'], json.dumps(item, ensure_ascii=False))
                        for item in result['items']])
            store.stage_export(task['run_id'], f'referenceInfo/{number}/{version}.json', result)
        activate = state in ('complete', 'no_data') or (state == 'partial' and not current['version'] and bool(result['items']))
        if activate:
            store.execute('UPDATE paper_reference_state SET version=%s,total=%s,expected_total=%s WHERE number=%s',
                          (version, len(result['items']), result['expected_total'], number))
        store.execute('UPDATE paper_reference_state SET state=%s,error=%s,checked_at=UTC_TIMESTAMP(6) WHERE number=%s',
                      (state, result.get('error'), number))
        task_state = 'done' if state in ('complete', 'no_data', 'unavailable') else 'blocked' if state == 'blocked' else 'failed'
        store.execute('UPDATE tasks SET status=%s,error=%s WHERE id=%s', (task_state, result.get('error'), task['id']))
    if isinstance(value.get('records'), dict):
        from .citations import save_availability
        save_availability(store, number, 'references', value['records'])
    store.db.commit()
    counts = store.counts(task['run_id'])
    store.set_run(task['run_id'], status='references_running' if counts.get('pending') or counts.get('running') else
                  'needs_attention' if counts.get('failed') or counts.get('blocked') else 'completed', stats=counts)
    # A publication failure leaves the committed pending export for journal recovery.
    publish_exports(store)
    return {'number': number, 'state': state}


class ReferenceBridge:
    """SQL-only adapter for the coordinator's existing claim/fetch/journal/apply loop."""
    def __init__(self, cfg):
        job = cfg['jobs']['references']
        self.store = Store(Config.load(job.get('profile', cfg['target_profile'])))
        self.stack = ExitStack()
        self.active = False

    def inspect(self):
        self.store.db.commit()
        require(self.store)
        groups = self.store.execute('SELECT state,COUNT(*) n FROM paper_reference_state GROUP BY state')
        states = {r['state']: r['n'] for r in groups}
        counts = {'pending': states.get('queued', 0), 'running': states.get('fetching', 0),
                  'done': sum(states.get(k, 0) for k in ('complete', 'no_data', 'unavailable')),
                  'failed': states.get('failed', 0) + states.get('partial', 0), 'blocked': states.get('blocked', 0),
                  'total': sum(states.values())}
        counts['exports_pending'] = self.store.execute("SELECT COUNT(*) n FROM exports WHERE path LIKE 'referenceInfo/%%' AND status='pending'")[0]['n']
        owners = [self.store.execute('SELECT IS_USED_LOCK(%s) owner', (name,))[0]['owner']
                  for name in self.store.lock_names('references')]
        return {'compatible': True, 'run_id': 'references', 'status': 'running' if counts['running'] else 'idle',
                'counts': counts, 'states': states, 'locks': owners}

    def acquire(self):
        if not self.active:
            self.stack.enter_context(self.store.lock('references'))
            self.active = True
            self.connection = self.store.execute('SELECT CONNECTION_ID() id')[0]['id']
            self.store.execute("UPDATE tasks t JOIN paper_reference_state s ON s.task_id=t.id SET t.status='pending' "
                               "WHERE s.state='fetching' AND t.kind='references'")
            self.store.execute("UPDATE paper_reference_state SET state='queued' WHERE state='fetching'")
            self.store.db.commit()
            publish_exports(self.store)
        return self.inspect()

    def check(self):
        if not self.active or any(self.store.execute('SELECT IS_USED_LOCK(%s) owner', (name,))[0]['owner'] != self.connection
                                  for name in self.store.lock_names('references')):
            raise RuntimeError('References adapter lease lost')

    def claim(self, allow_retry=False):
        self.check()
        self.store.db.commit()
        rows = self.store.execute("SELECT t.* FROM tasks t JOIN paper_reference_state s ON s.task_id=t.id "
                                  "WHERE s.state='queued' AND t.status='pending' AND t.kind='references' ORDER BY t.id LIMIT 1")
        if not rows:
            return None
        task = rows[0]
        task['payload'] = json.loads(task['payload'])
        self.store.execute("UPDATE tasks SET status='running',attempts=attempts+1 WHERE id=%s", (task['id'],))
        self.store.execute("UPDATE paper_reference_state SET state='fetching' WHERE number=%s", (task['task_key'],))
        self.store.db.commit()
        return {**task, 'role': 'references'}

    def apply(self, task, value):
        self.check()
        from .basic_worker import scope_digest
        if task.get('role') != 'references' or task.get('kind') != 'references' or value.get('scope_digest') != scope_digest(task):
            raise ValueError('Reference result scope differs')
        return apply_result(self.store, task, value)

    def heartbeat(self):
        self.check()
        return self.inspect()

    def pause(self):
        return self.inspect()

    def close(self):
        self.stack.close()
        self.store.close()


class ReferenceReadError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def read(store, number, offset=0, limit=50, version=None, order=None):
    from .citations import reference_availability
    article_id(number)
    if not 0 <= offset <= 10000000 or not 1 <= limit <= 100 or (order is not None and order < 1):
        raise ReferenceReadError('invalid_reference_page')
    if version is not None and not re.fullmatch('[a-f0-9]{32}', version):
        raise ReferenceReadError('invalid_reference_version')
    if not store.execute('SELECT number FROM papers WHERE number=%s', (number,)):
        raise ReferenceReadError('not_found')
    out = {'number': number, 'state': 'missing', 'version': None, 'total': 0, 'expected_total': None,
           'checked_at': None, 'error': None, 'offset': offset, 'limit': limit, 'next_offset': None, 'items': []}
    rows = store.execute('SELECT * FROM paper_reference_state WHERE number=%s', (number,))
    if rows:
        current = rows[0]
        out.update({k: current[k] for k in ('state', 'version', 'total', 'expected_total', 'error')})
        out['checked_at'] = current['checked_at'].isoformat() + 'Z' if current['checked_at'] else None
    selected = version or out['version']
    if version:
        snapshots = store.execute('SELECT * FROM paper_reference_snapshots WHERE number=%s AND version=%s', (number, version))
        if not snapshots:
            raise ReferenceReadError('reference_version_not_found')
        snapshot = snapshots[0]
        if selected != out['version']:
            out.update(state=snapshot['state'], error=None, checked_at=snapshot['fetched_at'].isoformat() + 'Z')
        out.update(version=version, total=snapshot['total'], expected_total=snapshot['expected_total'])
    if not selected:
        if order is not None:
            raise ReferenceReadError('reference_not_found')
        return reference_availability(store, number, out)
    if order is not None:
        items = store.execute('SELECT data FROM paper_references WHERE number=%s AND version=%s AND ordinal=%s',
                              (number, selected, order))
        if not items:
            raise ReferenceReadError('reference_not_found')
        return {'number': number, 'version': selected, 'item': json.loads(items[0]['data'])}
    items = store.execute('SELECT data FROM paper_references WHERE number=%s AND version=%s ORDER BY ordinal LIMIT %s OFFSET %s',
                          (number, selected, limit, offset))
    out['items'] = [json.loads(r['data']) for r in items]
    end = offset + len(items)
    out['next_offset'] = end if end < out['total'] else None
    return reference_availability(store, number, out)


def cli(config, action, numbers=(), retry=False, offset=0, limit=50, version=None, order=None, check_availability=False):
    store = Store(config)
    try:
        if action == 'init':
            return initialize(store)
        if action == 'enqueue':
            return enqueue(store, numbers, retry=retry, check_availability=check_availability)
        if action == 'read':
            if len(numbers) != 1:
                raise ValueError('Read exactly one article number')
            with store.db.cursor() as cursor:
                cursor.execute('START TRANSACTION READ ONLY')
            require(store)
            return read(store, numbers[0], offset, limit, version, order)
        if action == 'publish':
            require(store)
            with store.lock('references'):
                publish_exports(store)
            return {'status': 'ready'}
        require(store)
        conditions = ' WHERE number IN (' + ','.join(['%s'] * len(numbers)) + ')' if numbers else ''
        rows = store.execute('SELECT number,state,version,total,expected_total,checked_at,error,run_id FROM paper_reference_state' + conditions,
                             tuple(article_id(n) for n in numbers))
        for row in rows:
            row['checked_at'] = row['checked_at'].isoformat() + 'Z' if row['checked_at'] else None
        return {'items': rows}
    finally:
        store.close()
