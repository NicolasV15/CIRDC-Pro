import json
import os
import uuid
from contextlib import contextmanager
from .model import digest, encoded, field_states, merge, normalize

MIGRATION_VERSION = 2


class BusyError(RuntimeError):
    code = 'worker_busy'

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS schema_migrations (
        version INT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS venues (
        kind VARCHAR(20) NOT NULL, number VARCHAR(64) NOT NULL, data LONGTEXT NOT NULL,
        PRIMARY KEY(kind,number))""",
    """CREATE TABLE IF NOT EXISTS papers (
        number VARCHAR(64) PRIMARY KEY, data LONGTEXT NOT NULL,
        abstract_state VARCHAR(24) NOT NULL, keywords_state VARCHAR(24) NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX field_coverage(abstract_state,keywords_state,number))""",
    """CREATE TABLE IF NOT EXISTS paper_files (
        path VARCHAR(512) NOT NULL, number VARCHAR(64) NOT NULL, ordinal INT NOT NULL,
        PRIMARY KEY(path,number), INDEX by_number(number))""",
    """CREATE TABLE IF NOT EXISTS manifests (
        path VARCHAR(512) PRIMARY KEY, digest CHAR(64) NOT NULL,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS sync_cursors (
        path VARCHAR(512) PRIMARY KEY, source_count INT NOT NULL,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS runs (
        id CHAR(32) PRIMARY KEY, status VARCHAR(24) NOT NULL, params LONGTEXT NOT NULL,
        stats LONGTEXT NOT NULL, error LONGTEXT, pid INT,
        heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id BIGINT AUTO_INCREMENT PRIMARY KEY, run_id CHAR(32) NOT NULL,
        kind VARCHAR(24) NOT NULL, task_key VARCHAR(512) NOT NULL,
        payload LONGTEXT NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'pending',
        attempts INT NOT NULL DEFAULT 0, error LONGTEXT,
        UNIQUE KEY unique_task(run_id,kind,task_key), INDEX task_queue(run_id,status,id))""",
    """CREATE TABLE IF NOT EXISTS exports (
        id BIGINT AUTO_INCREMENT PRIMARY KEY, run_id CHAR(32) NOT NULL,
        path VARCHAR(512) NOT NULL, staged_path TEXT NOT NULL, digest CHAR(64) NOT NULL,
        status VARCHAR(24) NOT NULL DEFAULT 'pending', error LONGTEXT,
        UNIQUE KEY unique_export(run_id,path))""",
]


class Store:
    def __init__(self, config):
        import pymysql
        self.config = config
        if not config.mysql.get('user'):
            raise RuntimeError('Database is not configured; run the local database initialization tool')
        options = {k: v for k, v in config.mysql.items()
                   if k in ('host', 'port', 'user', 'password', 'database', 'unix_socket')}
        self.db = pymysql.connect(**options, charset='utf8mb4', autocommit=False,
                                  connect_timeout=5, read_timeout=60, write_timeout=60,
                                  cursorclass=pymysql.cursors.DictCursor)

    def close(self):
        self.db.close()

    def execute(self, sql, params=()):
        with self.db.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def many(self, sql, params):
        if params:
            with self.db.cursor() as cursor:
                cursor.executemany(sql, params)

    def migrate(self):
        for sql in SCHEMA:
            self.execute(sql)
        self.execute('INSERT IGNORE INTO schema_migrations(version) VALUES (%s)', (1,))
        indexes = self.execute('SELECT INDEX_NAME FROM information_schema.statistics '
                               'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s',
                               ('papers', 'field_coverage'))
        if not indexes:
            self.execute('ALTER TABLE papers ADD INDEX field_coverage(abstract_state,keywords_state,number)')
        self.execute('INSERT IGNORE INTO schema_migrations(version) VALUES (%s)', (MIGRATION_VERSION,))
        self.db.commit()

    @contextmanager
    def lock(self, role='worker'):
        name = 'cirdc:' + digest((self.config.mysql['database'] + str(self.config.data_root)).encode())[:32] + ':' + role
        result = self.execute('SELECT GET_LOCK(%s,0) AS acquired', (name,))[0]
        if result['acquired'] != 1:
            raise BusyError('Another metadata worker owns this data root; query its status instead')
        try:
            yield
        finally:
            self.execute('SELECT RELEASE_LOCK(%s)', (name,))

    def upsert_records(self, records, path=None):
        count = 0
        for start in range(0, len(records), 500):
            group = {}
            order = {}
            for index, raw in enumerate(records[start:start + 500], start):
                record = normalize(raw)
                number = record['articleNumber']
                group[number] = merge(group.get(number, {}), record)
                order[number] = index
            if not group:
                continue
            existing = self.execute('SELECT number,data,abstract_state,keywords_state FROM papers WHERE number IN ('
                                    + ','.join(['%s'] * len(group)) + ')', tuple(group))
            existing = {r['number']: r for r in existing}
            values = []
            for number, record in group.items():
                old = existing.get(number)
                combined = merge(json.loads(old['data']) if old else {}, record)
                a, k = field_states(combined)
                if old:
                    if a == 'pending' and old['abstract_state'] == 'no_data':
                        a = 'no_data'
                    if k == 'pending' and old['keywords_state'] == 'no_data':
                        k = 'no_data'
                values.append((number, json.dumps(combined, ensure_ascii=False), a, k))
            self.many('INSERT INTO papers(number,data,abstract_state,keywords_state) VALUES (%s,%s,%s,%s) '
                      'ON DUPLICATE KEY UPDATE data=VALUES(data),abstract_state=VALUES(abstract_state),'
                      'keywords_state=VALUES(keywords_state)', values)
            if path:
                self.many('INSERT INTO paper_files(path,number,ordinal) VALUES (%s,%s,%s) '
                          'ON DUPLICATE KEY UPDATE ordinal=VALUES(ordinal)',
                          [(path, n, order[n]) for n in group])
            count += len(group)
        return count

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
        result['exports_pending'] = self.execute("SELECT COUNT(*) AS n FROM exports WHERE run_id=%s AND status='pending'", (run_id,))[0]['n']
        return result

    def stage_export(self, run_id, relative, value):
        self.config.destination(relative)
        content = encoded(value)
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

    def errors(self, run_id):
        return self.execute("SELECT kind,task_key,status,attempts,error FROM tasks WHERE run_id=%s "
                            "AND status IN ('failed','blocked') ORDER BY id LIMIT 100", (run_id,))
