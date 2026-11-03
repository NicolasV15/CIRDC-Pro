"""Durable resource requests; this is a receipt store, never a worker queue."""
from contextlib import closing
import json
import time
import uuid

from .settings import connect


class RequestStore:
    def db(self):
        db = connect('agent-requests.sqlite')
        db.execute('CREATE TABLE IF NOT EXISTS requests ('
                   'id TEXT PRIMARY KEY, number TEXT NOT NULL, resources TEXT NOT NULL, '
                   'references_json TEXT NOT NULL, history TEXT NOT NULL, created REAL NOT NULL, '
                   'updated REAL NOT NULL, UNIQUE(number, resources))')
        db.commit()
        return db

    def ensure(self, number, resources, submit):
        """Serialize submissions across processes, preserving every changed reference.

        Provider submission must itself reuse active jobs and retain failed jobs.
        If this transaction is interrupted after submission, the next submission
        reattaches to those jobs; it must not implicitly retry them.
        """
        key = json.dumps(sorted(resources))
        with closing(self.db()) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM requests WHERE number=? AND resources=?', (number, key)).fetchone()
            reference = json.loads(row['references_json']) if row else {}
            history = json.loads(row['history']) if row else []
            request_id = row['id'] if row else uuid.uuid4().hex
            values, new_reference = submit(reference)
            if reference and reference != new_reference:
                history.append({'at': row['updated'], 'references': reference})
            now = time.time()
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?) '
                       'ON CONFLICT(id) DO UPDATE SET references_json=excluded.references_json, '
                       'history=excluded.history, updated=excluded.updated',
                       (request_id, number, key, json.dumps(new_reference), json.dumps(history),
                        row['created'] if row else now, now))
            db.commit()
        return request_id, values

    def get(self, request_id):
        with closing(self.db()) as db:
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
        if not row:
            return None
        return {'id': row['id'], 'number': row['number'], 'resources': json.loads(row['resources']),
                'references': json.loads(row['references_json']), 'attempt_history': json.loads(row['history']),
                'created_at': row['created'], 'updated_at': row['updated']}
