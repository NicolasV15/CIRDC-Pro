"""Durable resource requests; this is a receipt store, never a worker queue."""
import fcntl
import json
import logging
import time
import uuid
from contextlib import closing

from .agent_runtime import BusyError
from .settings import connect, state_dir


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
        directory = state_dir() / 'agent-submit-locks'
        directory.mkdir(mode=0o700, exist_ok=True)
        with (directory / (number + '.lock')).open('a') as lock:
            start = time.monotonic()
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BusyError() from None
            logging.getLogger('cirdc.agent').info('agent_submit_lock seconds=%.3f', time.monotonic()-start)
            with closing(self.db()) as db:
                row = db.execute('SELECT * FROM requests WHERE number=? AND resources=?', (number, key)).fetchone()
            reference = json.loads(row['references_json']) if row else {}
            history = json.loads(row['history']) if row else []
            request_id = row['id'] if row else uuid.uuid4().hex
            values, new_reference = submit(reference)
            if reference and reference != new_reference:
                history.append({'at': row['updated'], 'references': reference})
            now = time.time()
            with closing(self.db()) as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?) '
                           'ON CONFLICT(id) DO UPDATE SET references_json=excluded.references_json, '
                           'history=excluded.history, updated=excluded.updated',
                           (request_id, number, key, json.dumps(new_reference), json.dumps(history),
                            row['created'] if row else now, now))
                db.commit()
            logging.getLogger('cirdc.agent').info('agent_receipt_saved request_id=%s seconds=%.3f', request_id, time.time()-now)
        import os

        from .task_origins import CURRENT, response_jobs
        from .visits import VisitStore
        context = CURRENT.get()
        path = os.environ.get('CIRDC_WEB_VISITS_FILE')
        if context and path:
            try:
                links = response_jobs({'number': number, 'resources': values}, number)
                if links:
                    VisitStore(path).record_task({**context, 'status': context.get('response_status', 202), 'outcome': 'associated'}, links)
            except Exception:
                logging.getLogger('cirdc.agent').exception('agent_task_origin_failed')
        return request_id, values

    def find(self, number, resources):
        with closing(self.db()) as db:
            row = db.execute('SELECT id FROM requests WHERE number=? AND resources=?',
                             (number, json.dumps(sorted(resources)))).fetchone()
        return row['id'] if row else None

    def find_resource(self, number, resource):
        with closing(self.db()) as db:
            rows = db.execute('SELECT id,resources FROM requests WHERE number=? ORDER BY updated DESC', (number,)).fetchall()
        return next((row['id'] for row in rows if resource in json.loads(row['resources'])), None)

    def get(self, request_id):
        with closing(self.db()) as db:
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
        if not row:
            return None
        return {'id': row['id'], 'number': row['number'], 'resources': json.loads(row['resources']),
                'references': json.loads(row['references_json']), 'attempt_history': json.loads(row['history']),
                'created_at': row['created'], 'updated_at': row['updated']}
