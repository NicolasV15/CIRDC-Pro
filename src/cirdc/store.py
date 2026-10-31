import json
import os
import uuid
from contextlib import contextmanager
from .model import digest, encoded, field_states, merge, normalize

from .schema import MIGRATION_VERSION as MIGRATION_VERSION, SCHEMA as SCHEMA, SchemaError, inspect, initialize


class BusyError(RuntimeError):
    code = 'worker_busy'


class Store:
    def __init__(self, config):
        import pymysql
        self.config = config
        self._schema_report = None
        self._initializing = False
        if not config.mysql.get('user'):
            raise RuntimeError('Database is not configured; run the local database initialization tool')
        options = {k: v for k, v in config.mysql.items()
                   if k in ('host', 'port', 'user', 'password', 'database', 'unix_socket')}
        if config.ssh_tunnel:
            from .ssh import SSH
            SSH(config.ssh_tunnel['host'], config.ssh_tunnel).ensure()
            options.pop('unix_socket', None)
            options.update(host='127.0.0.1', port=int(config.ssh_tunnel['local_port']))
        self.db = pymysql.connect(**options, charset='utf8mb4', autocommit=False,
                                  connect_timeout=5, read_timeout=60, write_timeout=60,
                                  cursorclass=pymysql.cursors.DictCursor)

    def close(self):
        self.db.close()

    def execute(self, sql, params=()):
        command = sql.lstrip().split(None, 1)[0].upper()
        if not self._initializing and command not in ('SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN'):
            self.require_schema()
        if command in ('CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME'):
            self._schema_report = None
        with self.db.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def many(self, sql, params):
        if params:
            if not self._initializing:
                self.require_schema()
            with self.db.cursor() as cursor:
                cursor.executemany(sql, params)

    def inspect_schema(self):
        return inspect(self)

    def require_schema(self, force=False):
        if force or self._schema_report is None:
            self._schema_report = inspect(self)
        if not self._schema_report['compatible']:
            raise SchemaError(self._schema_report)
        return self._schema_report

    def migrate(self, adopt=False):
        return initialize(self, adopt)

    def lock_names(self, role='worker'):
        # The database lock is independent of the client's path or SSH forwarding port.
        # Retain the legacy name as well so an existing server worker cannot compete.
        database = self.config.mysql['database']
        roots = {str(self.config.data_root)}
        if self.config.storage.get('legacy_lock_root'):
            roots.add(str(self.config.storage['legacy_lock_root']))
        return ['cirdc:db:' + digest(database.encode())[:32] + ':' + role,
                *['cirdc:' + digest((database + root).encode())[:32] + ':' + role for root in sorted(roots)]]

    def worker_active(self):
        return any(self.execute('SELECT IS_USED_LOCK(%s) AS owner', (name,))[0]['owner'] is not None
                   for name in self.lock_names())

    @contextmanager
    def lock(self, role='worker'):
        held = []
        try:
            for name in self.lock_names(role):
                result = self.execute('SELECT GET_LOCK(%s,0) AS acquired', (name,))[0]
                if result['acquired'] != 1:
                    raise BusyError('Another metadata worker owns this database; query its status instead')
                held.append(name)
            yield
        finally:
            for name in reversed(held):
                self.execute('SELECT RELEASE_LOCK(%s)', (name,))

    def upsert_records(self, records, path=None, basic_only=False, source_records=None):
        if source_records is not None and not basic_only:
            raise ValueError('Source record selection is only for bibliographic updates')
        count = 0
        self.last_upsert_stats = {'new': 0, 'updated': 0, 'unchanged': 0}
        self.last_basic_records = {}
        for start in range(0, len(records), 500):
            group = {}
            order = {}
            for index, raw in enumerate(records[start:start + 500], start):
                record = normalize(raw, basic_only=basic_only)
                number = record['articleNumber']
                group[number] = merge(group.get(number, {}), record)
                order[number] = index
            if not group:
                continue
            projection = "JSON_REMOVE(data,'$.abstract','$.keywords') AS data" if basic_only else 'data'
            existing = self.execute('SELECT number,' + projection + ',abstract_state,keywords_state FROM papers WHERE number IN ('
                                    + ','.join(['%s'] * len(group)) + ')', tuple(group))
            existing = {r['number']: r for r in existing}
            values = []
            changed = []
            for number, record in group.items():
                old = existing.get(number)
                old_data = json.loads(old['data']) if old else {}
                base, incoming = old_data, record
                if source_records is not None:
                    # Retained archive rows only establish file membership.
                    # Existing canonical values can change only from the
                    # validated response, rather than a stale local snapshot.
                    base = old_data if old else record
                    incoming = (normalize(source_records[number], basic_only=True)
                                if number in source_records else {})
                combined = merge(base, incoming)
                if basic_only and old:
                    from .early_access import publication_stage
                    if publication_stage(old_data) == 'final' and publication_stage(incoming) == 'early_access':
                        combined = old_data
                if source_records is not None and number in source_records:
                    self.last_basic_records[number] = normalize(combined, basic_only=True)
                if basic_only:
                    # A bibliographic refresh never promotes cached enrichment
                    # to complete or replaces a prior document-stage decision.
                    a, k = ((old['abstract_state'], old['keywords_state']) if old else ('pending', 'pending'))
                else:
                    a, k = field_states(combined)
                if old and not basic_only:
                    if a == 'pending' and old['abstract_state'] == 'no_data':
                        a = 'no_data'
                    if k == 'pending' and old['keywords_state'] == 'no_data':
                        k = 'no_data'
                identical = bool(old) and combined == old_data and (a, k) == (old['abstract_state'], old['keywords_state'])
                self.last_upsert_stats['unchanged' if identical else 'updated' if old else 'new'] += 1
                if not basic_only or not identical:
                    # Send only changed basic keys for existing rows. Keeping
                    # null-valued and enrichment fields out of the patch also
                    # preserves data owned by other maintenance stages.
                    saved = ({key: value for key, value in combined.items()
                              if key not in old_data or value != old_data[key]}
                             if basic_only and old else combined)
                    values.append((number, json.dumps(saved, ensure_ascii=False), a, k))
                    changed.append(number)
            update = ('data=JSON_MERGE_PATCH(data,VALUES(data))' if basic_only else
                      'data=VALUES(data),abstract_state=VALUES(abstract_state),keywords_state=VALUES(keywords_state)')
            self.many('INSERT INTO papers(number,data,abstract_state,keywords_state) VALUES (%s,%s,%s,%s) '
                      'ON DUPLICATE KEY UPDATE ' + update, values)
            if changed:
                self.index_changed(changed)
            if path:
                self.many('INSERT INTO paper_files(path,number,ordinal) VALUES (%s,%s,%s) '
                          'ON DUPLICATE KEY UPDATE ordinal=VALUES(ordinal)',
                          [(path, n, order[n]) for n in group])
            count += len(group)
        return count

    def index_changed(self, numbers):
        if not self.require_schema()['features']['web_index']:
            return
        enabled = self.execute("SELECT value FROM web_settings WHERE name='index_enabled'")
        if enabled and enabled[0]['value'] == '1':
            self.many('INSERT INTO web_index_queue(number,token) VALUES (%s,%s) '
                      'ON DUPLICATE KEY UPDATE token=VALUES(token),changed_at=CURRENT_TIMESTAMP(6)',
                      [(str(n), uuid.uuid4().hex) for n in numbers])

    def paper(self, number):
        rows = self.execute('SELECT * FROM papers WHERE number=%s', (str(number),))
        if not rows:
            return None
        out = rows[0]
        out['record'] = json.loads(out.pop('data'))
        out.pop('updated_at', None)
        return out

    def update_document(self, record, states):
        self.upsert_records([record])
        current = self.paper(record['articleNumber'])['record']
        a, k = field_states(current)
        self.execute('UPDATE papers SET abstract_state=%s,keywords_state=%s WHERE number=%s',
                     (a if a == 'complete' else states['abstract'],
                      k if k == 'complete' else states['keywords'], record['articleNumber']))
        self.index_changed([record['articleNumber']])

    def create_run(self, params):
        run_id = uuid.uuid4().hex
        self.execute('INSERT INTO runs(id,status,params,stats) VALUES (%s,%s,%s,%s)',
                     (run_id, 'queued', json.dumps(params), '{}'))
        self.db.commit()
        return run_id

    def run(self, run_id):
        rows = self.execute('SELECT * FROM runs WHERE id=%s', (run_id,))
        if not rows:
            raise ValueError('Unknown run identifier')
        result = rows[0]
        result['params'] = json.loads(result['params'])
        result['stats'] = json.loads(result['stats'])
        for key in ('heartbeat', 'created_at'):
            result[key] = result[key].isoformat()
        return result

    def set_run(self, run_id, status=None, stats=None, error=None, pid=None):
        columns = ['heartbeat=CURRENT_TIMESTAMP']
        values = []
        for key, value in [('status', status), ('stats', json.dumps(stats) if stats is not None else None),
                           ('error', error), ('pid', pid)]:
            if value is not None:
                columns.append(key + '=%s')
                values.append(value)
        self.execute('UPDATE runs SET ' + ','.join(columns) + ' WHERE id=%s', (*values, run_id))
        self.db.commit()

    def add_tasks(self, run_id, kind, tasks):
        batch = []
        for key, payload in tasks:
            batch.append((run_id, kind, str(key), json.dumps(payload)))
            if len(batch) == 500:
                self.many('INSERT IGNORE INTO tasks(run_id,kind,task_key,payload) VALUES (%s,%s,%s,%s)', batch)
                self.db.commit()
                batch = []
        self.many('INSERT IGNORE INTO tasks(run_id,kind,task_key,payload) VALUES (%s,%s,%s,%s)', batch)
        self.db.commit()

    def next_task(self, run_id, kinds=None):
        clause = ''
        params = [run_id]
        if kinds:
            clause = ' AND kind IN (' + ','.join(['%s'] * len(kinds)) + ')'
            params.extend(kinds)
        rows = self.execute("SELECT * FROM tasks WHERE run_id=%s AND status='pending'" + clause + ' ORDER BY id LIMIT 1', params)
        if not rows:
            return None
        result = rows[0]
        result['payload'] = json.loads(result['payload'])
        return result

    def task_state(self, task_id, status, error=None):
        self.execute('UPDATE tasks SET status=%s,error=%s,attempts=attempts+%s WHERE id=%s',
                     (status, error, int(status == 'running'), task_id))
        self.db.commit()

    def counts(self, run_id):
        rows = self.execute('SELECT status,COUNT(*) AS n FROM tasks WHERE run_id=%s GROUP BY status', (run_id,))
        result = {row['status']: row['n'] for row in rows}
        result['total'] = sum(result.values())
        result['exports_pending'] = self.execute("SELECT COUNT(*) AS n FROM exports WHERE run_id=%s "
                                                "AND status IN ('dirty','pending')", (run_id,))[0]['n']
        return result

    def mark_export_dirty(self, run_id, relative):
        """Commit a JSON synchronization obligation together with a document update."""
        self.config.destination(relative)
        self.execute('INSERT INTO exports(run_id,path,staged_path,digest,status) VALUES (%s,%s,%s,%s,%s) '
                     "ON DUPLICATE KEY UPDATE status='dirty',error=NULL",
                     (run_id, relative, '', '', 'dirty'))

    def stage_export(self, run_id, relative, value):
        self.config.destination(relative)
        content = encoded(value)
        if self.config.storage.get('ssh_host'):
            from .storage import Dataset
            path = Dataset(self.config).stage(run_id, relative, content)
            self.execute('INSERT INTO exports(run_id,path,staged_path,digest) VALUES (%s,%s,%s,%s) '
                         "ON DUPLICATE KEY UPDATE staged_path=VALUES(staged_path),digest=VALUES(digest),status='pending'",
                         (run_id, relative, path, digest(content)))
            return
        folder = self.config.state_dir / 'staging' / run_id
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = folder / (digest(relative.encode()) + '.json')
        temporary = path.with_suffix('.tmp')
        with temporary.open('wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        self.execute('INSERT INTO exports(run_id,path,staged_path,digest) VALUES (%s,%s,%s,%s) '
                     "ON DUPLICATE KEY UPDATE staged_path=VALUES(staged_path),digest=VALUES(digest),status='pending'",
                     (run_id, relative, str(path), digest(content)))

    def stage_document_patch(self, run_id, relative, updates):
        from .storage import Dataset
        staged = Dataset(self.config).stage_patch(run_id, relative, updates)
        self.execute('INSERT INTO exports(run_id,path,staged_path,digest) VALUES (%s,%s,%s,%s) '
                     "ON DUPLICATE KEY UPDATE staged_path=VALUES(staged_path),digest=VALUES(digest),status='pending'",
                     (run_id, relative, staged['staged_path'], staged['digest']))

    def errors(self, run_id):
        return self.execute("SELECT kind,task_key,status,attempts,error FROM tasks WHERE run_id=%s "
                            "AND status IN ('failed','blocked') ORDER BY id LIMIT 100", (run_id,))

    def deferred_tasks(self, run_id):
        rows = list(self.execute("SELECT kind,task_key,status,attempts,error FROM tasks WHERE run_id=%s "
                                 "AND status='deferred' ORDER BY id", (run_id,)))
        for row in rows:
            row['detail'] = json.loads(row.pop('error'))
        return rows
