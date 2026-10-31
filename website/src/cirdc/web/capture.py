"""Versioned queue capture for every database writer, including older clients."""
import json
import uuid
from datetime import datetime
from .index import save_meta


def install(store):
    store.execute('CREATE TABLE IF NOT EXISTS web_schema_migrations ('
                  'version INT PRIMARY KEY,applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    existing = {r['TRIGGER_NAME'] for r in store.execute(
        'SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE()')}
    versions = {r['version'] for r in store.execute('SELECT version FROM web_schema_migrations')}
    def enqueue(number):
        return (f"INSERT INTO web_index_queue(number,token) VALUES ({number},REPLACE(UUID(),'-','')) "
                'ON DUPLICATE KEY UPDATE token=VALUES(token),changed_at=CURRENT_TIMESTAMP(6); ')
    def definition(name, event):
        value = 'OLD.number' if event == 'DELETE' else 'NEW.number'
        changed = (" AND (NOT (OLD.number <=> NEW.number) OR NOT (OLD.data <=> NEW.data) "
                   "OR NOT (OLD.abstract_state <=> NEW.abstract_state) "
                   "OR NOT (OLD.keywords_state <=> NEW.keywords_state) "
                   "OR NOT (OLD.updated_at <=> NEW.updated_at))") if event == 'UPDATE' else ''
        extra = ('IF OLD.number<>NEW.number THEN ' + enqueue('OLD.number') + 'END IF; ') if event == 'UPDATE' else ''
        return ('CREATE TRIGGER ' + name + ' AFTER ' + event + ' ON papers FOR EACH ROW BEGIN '
                "IF (SELECT value FROM web_settings WHERE name='index_enabled')='1'" + changed + ' THEN '
                + extra + enqueue(value) + 'END IF; END')
    for event in ['INSERT', 'UPDATE', 'DELETE']:
        name = 'cirdc_web_papers_' + event.lower()
        if event == 'UPDATE' and name in existing and 2 not in versions:
            # A bridge trigger captures concurrent metadata writes across replacement.
            bridge = name + '_bridge_v2'
            if bridge not in existing:
                store.execute(definition(bridge, event))
            store.execute('DROP TRIGGER ' + name)
            store.execute(definition(name, event))
            store.execute('DROP TRIGGER ' + bridge)
        elif name not in existing:
            store.execute(definition(name, event))
        if event == 'UPDATE' and name + '_bridge_v2' in existing:
            store.execute('DROP TRIGGER IF EXISTS ' + name + '_bridge_v2')
    store.execute('INSERT IGNORE INTO web_schema_migrations(version) VALUES (%s)', (2,))
    store.db.commit()


def seed_missed(config, store, db, meta):
    if meta.get('capture_seeded_version') == 1:
        return
    if not meta.get('indexed'):
        save_meta(db, capture_seeded_version=1)
        db.commit()
        return
    # Only a one-time non-locking catch-up is needed when installing capture on an
    # existing index. Capture is installed before this read, so concurrent changes
    # are already queued in the canonical database transaction.
    import pymysql
    value = meta.get('started_at') or meta.get('synced_at') or meta.get('checked_at')
    cutoff = datetime.fromisoformat(value).timestamp() if value else 0
    options = {k: v for k, v in config.mysql.items() if k in ('host', 'port', 'user', 'password', 'database', 'unix_socket')}
    save_meta(db, phase='catching_up')
    db.commit()
    count = 0
    with pymysql.connect(**options, charset='utf8mb4', cursorclass=pymysql.cursors.SSCursor,
                         read_timeout=120) as source:
        with source.cursor() as cursor:
            cursor.execute('SELECT number FROM papers WHERE UNIX_TIMESTAMP(updated_at)>=%s', (cutoff,))
            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break
                store.many('INSERT INTO web_index_queue(number,token) VALUES (%s,%s) '
                           'ON DUPLICATE KEY UPDATE token=VALUES(token),changed_at=CURRENT_TIMESTAMP(6)',
                           [(str(r[0]), uuid.uuid4().hex) for r in rows])
                store.db.commit()
                count += len(rows)
    save_meta(db, capture_seeded_version=1, capture_reconciled=count)
    db.commit()
    print(json.dumps({'capture_schema': 1, 'reconciled_records': count}), flush=True)
