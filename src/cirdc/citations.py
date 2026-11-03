"""Optional incoming-citation snapshots and a bounded on-demand queue."""
import hashlib
import json
import re
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone

from .config import Config
from .reference_source import article_id
from .store import Store

GROUPS = ('ieee', 'nonIeee')
COMMENT = 'cirdc.citations.v1'
TABLES = {
 'citation_schema_migrations': 'version INT PRIMARY KEY,applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
 'paper_citation_state': 'number VARCHAR(64) PRIMARY KEY,state VARCHAR(24) NOT NULL,version CHAR(32) NULL,'
 'checked_at DATETIME(6) NULL,last_attempt_at DATETIME(6) NULL,next_check_at DATETIME(6) NULL,'
 'error VARCHAR(64) NULL,run_id CHAR(32) NULL,task_id BIGINT NULL,INDEX citation_queue(state,number)',
 'paper_citation_snapshots': 'number VARCHAR(64) NOT NULL,version CHAR(32) NOT NULL,fetched_at DATETIME(6) NOT NULL,'
 'digest CHAR(64) NOT NULL,data LONGTEXT NOT NULL,PRIMARY KEY(number,version)',
 'paper_citations': 'number VARCHAR(64) NOT NULL,version CHAR(32) NOT NULL,group_name VARCHAR(16) NOT NULL,'
 'ordinal INT UNSIGNED NOT NULL,data LONGTEXT NOT NULL,PRIMARY KEY(number,version,group_name,ordinal)',
 'paper_relationship_availability': 'number VARCHAR(64) NOT NULL,direction VARCHAR(16) NOT NULL,'
 'source_presence VARCHAR(16) NOT NULL,empty_reason VARCHAR(32) NULL,checked_at DATETIME(6) NOT NULL,'
 'detector_version INT NOT NULL,version CHAR(32) NULL,evidence LONGTEXT NOT NULL,PRIMARY KEY(number,direction)',
}


def check(store):
    rows = store.execute('SELECT TABLE_NAME,TABLE_COMMENT,ENGINE,TABLE_COLLATION FROM information_schema.TABLES '
                         'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (' + ','.join(['%s'] * len(TABLES)) + ')', tuple(TABLES))
    if not rows:
        return False
    if {r['TABLE_NAME'] for r in rows} != set(TABLES):
        raise ValueError('citations_schema_mismatch')
    for row in rows:
        name = row['TABLE_NAME']
        if row['TABLE_COMMENT'] != COMMENT or row['ENGINE'] != 'InnoDB' or row['TABLE_COLLATION'] != 'utf8mb4_bin':
            raise ValueError('citations_schema_mismatch')
        definitions = list(re.finditer(r'(?:^|,)([a-z_]+) ((?:VARCHAR|CHAR|DATETIME)\(\d+\)|INT(?: UNSIGNED)?|BIGINT|LONGTEXT|TIMESTAMP)([^,]*)', TABLES[name]))
        columns = store.execute('SHOW FULL COLUMNS FROM `' + name + '`')
        if [c['Field'] for c in columns] != [d[1] for d in definitions]:
            raise ValueError('citations_schema_mismatch')
        for column, definition in zip(columns, definitions):
            kind = re.sub(r'\b(int|bigint)\(\d+\)', r'\1', column['Type'].lower())
            nullable = 'NOT NULL' not in definition[3] and 'PRIMARY KEY' not in definition[3]
            if (kind != definition[2].lower() or
                (column['Field'] != 'applied_at' and (column['Null'] == 'YES') != nullable) or
                (column.get('Collation') and column['Collation'] != 'utf8mb4_bin')):
                raise ValueError('citations_schema_mismatch')
            if column['Field']=='applied_at' and str(column['Default']).lower().replace('()','')!='current_timestamp':
                raise ValueError('citations_schema_mismatch')
            if column['Field']!='applied_at' and column['Default'] is not None:
                raise ValueError('citations_schema_mismatch')
        indexes = {}
        for key in sorted(store.execute('SHOW INDEX FROM `' + name + '`'), key=lambda r: r['Seq_in_index']):
            if bool(key['Non_unique']) != (key['Key_name']!='PRIMARY') or key['Sub_part'] is not None:
                raise ValueError('citations_schema_mismatch')
            indexes.setdefault(key['Key_name'], []).append(key['Column_name'])
        primary = re.search(r'PRIMARY KEY\(([^)]+)\)', TABLES[name])
        expected = {'PRIMARY': primary[1].split(',') if primary else ['version' if name == 'citation_schema_migrations' else 'number']}
        if name == 'paper_citation_state':
            expected['citation_queue'] = ['state', 'number']
        if indexes != expected:
            raise ValueError('citations_schema_mismatch')
    if [r['version'] for r in store.execute('SELECT version FROM citation_schema_migrations')] != [1]:
        raise ValueError('citations_schema_mismatch')
    return True


def require(store):
    store.require_schema()
    if not check(store):
        raise ValueError('citations_not_initialized')


def initialize(store):
    store.require_schema(force=True)
    with store.lock('citations-schema'):
        if not check(store):
            for name, fields in TABLES.items():
                store.execute('CREATE TABLE `' + name + '` (' + fields + ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='" + COMMENT + "'")
            store.execute('INSERT INTO citation_schema_migrations(version) VALUES (1)')
            store.db.commit()
        check(store)
    return {'status': 'ready', 'citation_schema_version': 1}


def available(store):
    rows = store.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', ('citation_schema_migrations',))
    return bool(rows) and check(store)


def save_availability(store, number, direction, result):
    if not available(store):
        return
    presence = result.get('source_presence', 'present' if result.get('items') else 'unknown')
    reason = result.get('empty_reason')
    if presence == 'unknown' and result.get('state') == 'no_data':
        presence, reason = 'present', 'zero_count'
    detector = 1 if 'source_presence' in result else 0
    store.execute('INSERT INTO paper_relationship_availability(number,direction,source_presence,empty_reason,checked_at,detector_version,version,evidence) '
                  'VALUES (%s,%s,%s,%s,UTC_TIMESTAMP(6),%s,%s,%s) ON DUPLICATE KEY UPDATE '
                  'source_presence=VALUES(source_presence),empty_reason=VALUES(empty_reason),checked_at=VALUES(checked_at),'
                  'detector_version=VALUES(detector_version),version=VALUES(version),evidence=VALUES(evidence)',
                  (number, direction, presence, reason, detector, result.get('version'), json.dumps(result.get('evidence') or {}, ensure_ascii=False)))


def reference_availability(store, number, view):
    view.update(source_presence='present' if view.get('total') else 'unknown', empty_reason=None,
                availability_checked_at=None, needs_availability_check=False)
    if view.get('state') == 'no_data':
        view.update(source_presence='present', empty_reason='zero_count')
    if not available(store):
        return view
    rows = store.execute('SELECT * FROM paper_relationship_availability WHERE number=%s AND direction=%s', (number, 'references'))
    if rows:
        row = rows[0]
        view['needs_availability_check'] = view.get('state') == 'unavailable' and row['detector_version'] < 1
        if row['version'] == view.get('version') or not view.get('version'):
            view.update(source_presence=row['source_presence'], empty_reason=row['empty_reason'],
                        availability_checked_at=row['checked_at'].isoformat() + 'Z')
    elif view.get('state') == 'unavailable':
        view['needs_availability_check'] = True
    return view


def enqueue(store, numbers, retry=False):
    numbers = list(dict.fromkeys(article_id(n) for n in numbers))
    if not 1 <= len(numbers) <= 20:
        raise ValueError('Pass between 1 and 20 explicit article numbers')
    require(store)
    queued, reused, run_id = [], [], None
    with store.lock('citations-enqueue'):
        store.db.commit()
        for number in numbers:
            if not store.execute('SELECT number FROM papers WHERE number=%s', (number,)):
                raise ValueError('paper_not_found')
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for number in numbers:
            old = store.execute('SELECT * FROM paper_citation_state WHERE number=%s', (number,))
            if old and (old[0]['state'] in ('queued', 'fetching') or not retry and old[0]['next_check_at'] and old[0]['next_check_at'] > now):
                reused.append(number);continue
            if run_id is None:
                run_id = uuid.uuid4().hex
                store.execute('INSERT INTO runs(id,status,params,stats) VALUES (%s,%s,%s,%s)',
                              (run_id, 'citations_pending', json.dumps({'stage': 'citations', 'mode': 'paper_relationships', 'explicit_ids': True, 'selection': numbers}), '{}'))
            payload = {'number': number, 'required_capability': 'paper_relationships_v1', 'priority': 0}
            store.execute('INSERT INTO tasks(run_id,kind,task_key,payload) VALUES (%s,%s,%s,%s)', (run_id, 'citations', number, json.dumps(payload)))
            task_id = store.execute('SELECT LAST_INSERT_ID() id')[0]['id']
            store.execute('INSERT INTO paper_citation_state(number,state,run_id,task_id) VALUES (%s,%s,%s,%s) '
                          "ON DUPLICATE KEY UPDATE state='queued',error=NULL,run_id=VALUES(run_id),task_id=VALUES(task_id)",
                          (number, 'queued', run_id, task_id));queued.append(number)
        store.db.commit()
    return {'status': 'queued' if queued else 'reused', 'run_id': run_id, 'queued': queued, 'reused': reused}


def publish_exports(store):
    from .model import digest
    from .storage import Dataset
    from .engine import atomic_write
    from pathlib import Path
    rows = store.execute("SELECT e.* FROM exports e JOIN runs r ON r.id=e.run_id WHERE JSON_UNQUOTE(JSON_EXTRACT(r.params,'$.stage'))='citations' AND e.status='pending' ORDER BY e.id")
    for row in rows:
        storage = Dataset(store.config)
        if storage.remote:
            storage.publish(row)
        else:
            content = Path(row['staged_path']).read_bytes()
            if digest(content) != row['digest']:
                raise ValueError('Citation snapshot staging digest differs')
            atomic_write(store.config.destination(row['path']), content)
        store.execute("UPDATE exports SET status='done',error=NULL WHERE id=%s", (row['id'],));store.db.commit()


def apply_result(store, task, value):
    number = article_id(task['task_key'])
    current = store.execute('SELECT * FROM paper_citation_state WHERE number=%s FOR UPDATE', (number,))[0]
    applied = store.execute('SELECT status,error FROM tasks WHERE id=%s AND run_id=%s AND kind=%s AND task_key=%s',
                            (task['id'],task['run_id'],'citations',number))
    if not applied:raise ValueError('Citation task identity differs')
    if applied[0]['status'] in ('done','blocked','failed'):
        previous_result=value.get('records')
        if isinstance(previous_result,dict):
            saved=store.execute('SELECT digest FROM paper_citation_snapshots WHERE number=%s AND version=%s',
                                (number,previous_result.get('version')))
            sha=hashlib.sha256(json.dumps(previous_result,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            if not saved or saved[0]['digest']!=sha:raise ValueError('Citation snapshot replay differs')
        elif value.get('error') != applied[0]['error']:
            raise ValueError('Citation failure replay differs')
        store.db.commit();publish_exports(store)
        return {'already_applied':True}
    if current['task_id'] != task['id']:
        raise ValueError('Superseded citation task')
    if value.get('error') == 'paused':
        store.execute("UPDATE paper_citation_state SET state='queued' WHERE number=%s", (number,))
        store.execute("UPDATE tasks SET status='pending' WHERE id=%s", (task['id'],));store.db.commit()
        return {'state': 'queued'}
    result = value.get('records')
    state = 'blocked' if value.get('error') in ('access_restricted', 'access_denied') else 'failed'
    error = value.get('error') or 'worker_error'
    if isinstance(result, dict):
        if result.get('number') != number or not re.fullmatch('[a-f0-9]{32}', result.get('version', '')):
            raise ValueError('Citation snapshot identity differs')
        state, error, version = result['state'], result.get('error'), result['version']
        if state not in ('complete', 'no_data', 'unavailable', 'partial', 'blocked', 'failed'):
            raise ValueError('Invalid citation state')
        sha = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        previous = store.execute('SELECT digest FROM paper_citation_snapshots WHERE number=%s AND version=%s', (number, version))
        if previous and previous[0]['digest'] != sha:
            raise ValueError('Citation snapshot replay differs')
        if not previous:
            metadata = {k: v for k, v in result.items() if k not in ('items', 'raw')}
            metadata['task_id'] = task['id']
            metadata['stored_counts'] = {g: sum(item['group'] == g for item in result['items']) for g in GROUPS}
            fetched = datetime.fromisoformat(result['fetched_at']).astimezone(timezone.utc).replace(tzinfo=None)
            store.execute('INSERT INTO paper_citation_snapshots(number,version,fetched_at,digest,data) VALUES (%s,%s,%s,%s,%s)',
                          (number, version, fetched, sha, json.dumps(metadata, ensure_ascii=False)))
            store.many('INSERT INTO paper_citations(number,version,group_name,ordinal,data) VALUES (%s,%s,%s,%s,%s)',
                       [(number, version, item['group'], item['order'], json.dumps(item, ensure_ascii=False)) for item in result['items']])
            store.stage_export(task['run_id'], f'citationInfo/{number}/{version}.json', result)
        if state in ('complete', 'no_data') or state == 'partial' and result['items'] and not current['version']:
            store.execute('UPDATE paper_citation_state SET version=%s,checked_at=%s WHERE number=%s',
                          (version, datetime.fromisoformat(result['fetched_at']).astimezone(timezone.utc).replace(tzinfo=None), number))
        save_availability(store, number, 'citations', result)
    store.execute('UPDATE paper_citation_state SET state=%s,error=%s,last_attempt_at=UTC_TIMESTAMP(6),next_check_at=UTC_TIMESTAMP(6)+INTERVAL 7 DAY WHERE number=%s', (state, error, number))
    terminal = 'done' if state in ('complete', 'no_data', 'unavailable') else 'blocked' if state == 'blocked' else 'failed'
    store.execute('UPDATE tasks SET status=%s,error=%s WHERE id=%s', (terminal, error, task['id']));store.db.commit()
    counts = store.counts(task['run_id'])
    store.set_run(task['run_id'], status='citations_running' if counts.get('pending') or counts.get('running') else 'needs_attention' if counts.get('blocked') or counts.get('failed') else 'completed', stats=counts)
    publish_exports(store)
    return {'number': number, 'state': state}


class CitationBridge:
    def __init__(self, cfg):
        self.store = Store(Config.load(cfg['jobs']['citations'].get('profile', cfg['target_profile'])))
        self.stack, self.active = ExitStack(), False
    def inspect(self):
        self.store.db.commit();require(self.store)
        states = {r['state']: r['n'] for r in self.store.execute('SELECT state,COUNT(*) n FROM paper_citation_state GROUP BY state')}
        counts = {'pending': states.get('queued', 0), 'running': states.get('fetching', 0), 'done': sum(states.get(s, 0) for s in ('complete', 'no_data', 'unavailable')), 'failed': states.get('failed', 0)+states.get('partial', 0), 'blocked': states.get('blocked', 0), 'total': sum(states.values())}
        counts['exports_pending'] = self.store.execute("SELECT COUNT(*) n FROM exports WHERE path LIKE 'citationInfo/%%' AND status='pending'")[0]['n']
        return {'compatible': True, 'run_id': 'citations', 'status': 'running' if counts['running'] else 'idle', 'states': states, 'counts': counts,
                'locks': [self.store.execute('SELECT IS_USED_LOCK(%s) owner', (n,))[0]['owner'] for n in self.store.lock_names('citations')]}
    def acquire(self):
        if not self.active:
            self.stack.enter_context(self.store.lock('citations'));self.active = True
            self.connection = self.store.execute('SELECT CONNECTION_ID() id')[0]['id']
            # Active distributed leases are recovered by the dispatcher, not reset here.
            publish_exports(self.store)
        return self.inspect()
    def check(self):
        if not self.active or any(self.store.execute('SELECT IS_USED_LOCK(%s) owner', (n,))[0]['owner'] != self.connection for n in self.store.lock_names('citations')):
            raise RuntimeError('Citation adapter lease lost')
    def peek(self):
        self.check();self.store.db.commit()
        rows = self.store.execute("SELECT t.id FROM tasks t JOIN paper_citation_state s ON s.task_id=t.id WHERE s.state='queued' AND t.status='pending' AND t.kind='citations' ORDER BY t.id LIMIT 1")
        return {'priority': 0 if rows else None, 'required_capability': 'paper_relationships_v1'}
    def claim(self, allow_retry=False):
        self.check();self.store.db.commit()
        rows = self.store.execute("SELECT t.* FROM tasks t JOIN paper_citation_state s ON s.task_id=t.id WHERE s.state='queued' AND t.status='pending' AND t.kind='citations' ORDER BY t.id LIMIT 1")
        if not rows:return None
        task = rows[0];task['payload'] = json.loads(task['payload'])
        self.store.execute("UPDATE tasks SET status='running',attempts=attempts+1 WHERE id=%s", (task['id'],))
        self.store.execute("UPDATE paper_citation_state SET state='fetching' WHERE number=%s", (task['task_key'],));self.store.db.commit()
        return {**task, 'role': 'citations'}
    def apply(self, task, value):
        from .basic_worker import scope_digest
        self.check()
        if task.get('role') != 'citations' or task.get('kind') != 'citations' or value.get('scope_digest') != scope_digest(task):
            raise ValueError('Citation result scope differs')
        return apply_result(self.store, task, value)
    def heartbeat(self):self.check();return self.inspect()
    def pause(self):return self.inspect()
    def close(self):self.stack.close();self.store.close()


def read(store, number, group='ieee', offset=0, limit=50, version=None):
    from .references import ReferenceReadError
    article_id(number)
    if group not in GROUPS or not 0 <= offset <= 10000000 or not 1 <= limit <= 100:
        raise ReferenceReadError('invalid_citation_page')
    if version is not None and not re.fullmatch('[a-f0-9]{32}', version):
        raise ReferenceReadError('invalid_citation_version')
    if not store.execute('SELECT number FROM papers WHERE number=%s', (number,)):
        raise ReferenceReadError('not_found')
    out = {'number': number, 'state': 'missing', 'version': None, 'group': group, 'total': 0, 'expected_total': None,
           'counts': {'ieee': None, 'nonIeee': None, 'total': None}, 'stored_counts': {'ieee': 0, 'nonIeee': 0, 'total': 0},
           'group_states': {g: 'missing' for g in GROUPS}, 'source_presence': 'unknown', 'empty_reason': None,
           'checked_at': None, 'last_attempt_at': None, 'next_check_at': None, 'stale': False, 'error': None,
           'offset': offset, 'limit': limit, 'next_offset': None, 'items': []}
    rows = store.execute('SELECT * FROM paper_citation_state WHERE number=%s', (number,))
    if rows:
        state = rows[0]
        out.update({k: state[k] for k in ('state', 'version', 'error')})
        for key in ('last_attempt_at', 'next_check_at'):
            out[key] = state[key].isoformat()+'Z' if state[key] else None
        if not out['version']:
            # Failed/unknown first attempts still carry independently verified
            # group facts; expose their immutable metadata without promoting them
            # to the SQL pointer for a good result.
            attempts=store.execute("SELECT version FROM paper_citation_snapshots WHERE number=%s ORDER BY CAST(JSON_UNQUOTE(JSON_EXTRACT(data,'$.task_id')) AS UNSIGNED) DESC,fetched_at DESC LIMIT 1",(number,))
            if attempts:out['version']=attempts[0]['version']
    selected = version or out['version']
    if selected:
        rows = store.execute('SELECT * FROM paper_citation_snapshots WHERE number=%s AND version=%s', (number, selected))
        if not rows:raise ReferenceReadError('citation_version_not_found')
        snapshot = rows[0];metadata = json.loads(snapshot['data'])
        if selected != out['version']:
            out.update(state=metadata['state'], error=metadata.get('error'))
        out.update(version=selected, checked_at=snapshot['fetched_at'].isoformat()+'Z',
                   source_presence=metadata['source_presence'], empty_reason=metadata.get('empty_reason'),
                   group_states=metadata['group_states'])
        out['counts'].update(metadata['counts']);out['stored_counts'].update(metadata['stored_counts'])
        out['counts']['total'] = sum(metadata['counts'].values()) if all(v is not None for v in metadata['counts'].values()) else None
        out['stored_counts']['total'] = sum(metadata['stored_counts'].values())
        out.update(total=metadata['stored_counts'][group], expected_total=metadata['counts'][group])
        out['stale'] = snapshot['fetched_at'] < datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=7) or out['state'] in ('partial','blocked','failed','unavailable')
        out['items'] = [json.loads(r['data']) for r in store.execute('SELECT data FROM paper_citations WHERE number=%s AND version=%s AND group_name=%s ORDER BY ordinal LIMIT %s OFFSET %s', (number, selected, group, limit, offset))]
        end = offset + len(out['items']);out['next_offset'] = end if end < out['total'] else None
    return out


def cli(config, action, numbers=(), retry=False, offset=0, limit=50, version=None, group='ieee'):
    store = Store(config)
    try:
        if action == 'init':return initialize(store)
        if action == 'enqueue':return enqueue(store, numbers, retry)
        if action == 'read':
            if len(numbers) != 1:raise ValueError('Read exactly one article number')
            with store.db.cursor() as cursor:cursor.execute('START TRANSACTION READ ONLY')
            require(store);return read(store, numbers[0], group, offset, limit, version)
        require(store)
        if action == 'publish':
            with store.lock('citations'):publish_exports(store)
            return {'status': 'ready'}
        clause = ' WHERE number IN ('+','.join(['%s']*len(numbers))+')' if numbers else ''
        rows = store.execute('SELECT * FROM paper_citation_state'+clause, tuple(article_id(n) for n in numbers))
        for row in rows:
            for k in ('checked_at','last_attempt_at','next_check_at'):
                row[k] = row[k].isoformat()+'Z' if row[k] else None
        return {'items': rows}
    finally:store.close()
