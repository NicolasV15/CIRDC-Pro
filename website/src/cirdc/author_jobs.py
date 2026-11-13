"""Durable author jobs. Run the writer bridge in the website's isolated environment."""
import json
import logging
import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager
from functools import wraps

import pymysql
from datetime import datetime, timezone
from pathlib import Path

from .author_profiles import AuthorError, AuthorRepository, identity, validate
from .config import Config
from .store import Store


class Queue:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS author_jobs(
          id TEXT PRIMARY KEY, author_id TEXT NOT NULL, state TEXT NOT NULL,
          priority INTEGER NOT NULL, trigger TEXT NOT NULL, created REAL NOT NULL,
          updated REAL NOT NULL, error TEXT, attempt INTEGER NOT NULL DEFAULT 0);
        CREATE UNIQUE INDEX IF NOT EXISTS author_active ON author_jobs(author_id)
          WHERE state IN ('queued','fetching');
        CREATE INDEX IF NOT EXISTS author_history ON author_jobs(author_id,created);
        CREATE TABLE IF NOT EXISTS author_settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS author_origins(
          id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,trigger TEXT NOT NULL,created REAL NOT NULL);
        ''')

    def read(self, aid):
        identity(aid)
        row = self.db.execute('SELECT * FROM author_jobs WHERE author_id=? ORDER BY created DESC LIMIT 1', (aid,)).fetchone()
        return dict(row) if row else {'state': 'missing', 'author_id': aid}

    def enqueue(self, aid, trigger='manual'):
        identity(aid)
        priority = 0 if trigger == 'manual' else 80
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute("SELECT * FROM author_jobs WHERE author_id=? AND state IN ('queued','fetching')", (aid,)).fetchone()
            if row:
                self.db.execute('UPDATE author_jobs SET priority=MIN(priority,?) WHERE id=?', (priority,row['id']))
                key = row['id']
            else:
                key=uuid.uuid4().hex;now=time.time()
                self.db.execute("INSERT INTO author_jobs VALUES(?,?,'queued',?,?,?,?,NULL,0)", (key,aid,priority,trigger,now,now))
            self.db.execute("INSERT INTO author_origins(job_id,subject_type,subject_id,trigger,created) VALUES(?,'author',?,?,?)", (key,aid,trigger,time.time()))
        return self.read(aid)

    def claim(self):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.paused() or self.db.execute("SELECT 1 FROM author_jobs WHERE state='fetching'").fetchone():return None
            row=self.db.execute("SELECT * FROM author_jobs WHERE state='queued' ORDER BY priority,created LIMIT 1").fetchone()
            if not row:return None
            self.db.execute("UPDATE author_jobs SET state='fetching',attempt=attempt+1,updated=? WHERE id=?",(time.time(),row['id']))
            return {'id':row['id'],'run_id':'authors','role':'authors','kind':'author_profile','task_key':row['author_id'],
                    'payload':{'author_id':row['author_id'],'attempt':row['attempt']+1}}

    def paused(self):
        return bool(self.db.execute("SELECT 1 FROM author_settings WHERE key='paused' AND value='true'").fetchone())

    def control(self, op):
        if op not in ('pause','resume'):raise ValueError('invalid_control')
        with self.db:self.db.execute("INSERT OR REPLACE INTO author_settings VALUES('paused',?)",('true' if op=='pause' else 'false',))
        return {'paused':self.paused()}

    def status(self):
        return {'paused':self.paused(),'counts':{r[0]:r[1] for r in self.db.execute('SELECT state,COUNT(*) FROM author_jobs GROUP BY state')}}


def database_operation(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.repository():
            return method(self, *args, **kwargs)
    return call


def connection_failure(error):
    return (isinstance(error, pymysql.err.InterfaceError) or
            isinstance(error, pymysql.err.OperationalError) and error.args and
            error.args[0] in (2002, 2003, 2006, 2013, 2055))


class Bridge:
    def __init__(self, settings):
        self.settings=settings
        self.config=Config.load(settings['config'])
        self.store = self.repo = None
        self.expected_database_id = json.loads(Path(settings['config']).read_text()).get('database_id')
        if not self.expected_database_id:
            raise AuthorError('author_database_identity_not_pinned')
        self.queue=Queue(settings['queue'])
        self._papers=None
        with self.repository():
            pass

    @contextmanager
    def repository(self):
        """One connection per operation, never reconnect inside a write/lock scope."""
        if self.repo is not None:
            yield self.repo
            return
        store = Store(self.config)
        try:
            marker = store.execute('SELECT application,schema_version,instance_id FROM cirdc_identity WHERE singleton=1')
            if (len(marker) != 1 or marker[0]['application'] != 'cirdc-pro'
                    or marker[0]['schema_version'] != 4
                    or marker[0]['instance_id'] != self.expected_database_id):
                raise AuthorError('author_database_identity_mismatch')
            repo = AuthorRepository(store, self.config.state_dir)
            repo.ready()
            self.store, self.repo = store, repo
            yield repo
        finally:
            self.store = self.repo = None
            # Closing discards read transactions; save/failed own their commit boundary.
            if store.db.open:
                store.close()

    def profile(self, aid):
        with self.repository() as repo:
            return repo.show(aid)

    def inspect(self):
        try:
            with self.repository():
                self.store.execute('SELECT 1 AS ready')
        except (pymysql.err.InterfaceError, pymysql.err.OperationalError) as error:
            if not connection_failure(error):
                raise
            return {'compatible': False, 'locks': [], **self.queue.status(),
                    'database': {'state': 'unavailable', 'error': 'author_database_unavailable'}}
        return {'compatible':True,'locks':[],**self.queue.status(), 'database': {'state': 'ready'}}

    def acquire(self):
        retained=set()
        root=Path(self.settings['coordinator_state'])
        for file,query in [('dispatch.sqlite',"SELECT task FROM leases WHERE state IN ('issued','submitted')"),
                           ('journal.sqlite',"SELECT task FROM results WHERE applied=0")]:
            path=root/file
            if path.exists():
                with sqlite3.connect(path.absolute().as_uri()+'?mode=ro',uri=True) as db:
                    retained.update(json.loads(r[0])['id'] for r in db.execute(query) if json.loads(r[0]).get('role')=='authors')
        with self.queue.db:
            for row in self.queue.db.execute("SELECT id FROM author_jobs WHERE state='fetching'").fetchall():
                if row[0] not in retained:self.queue.db.execute("UPDATE author_jobs SET state='queued' WHERE id=?",(row[0],))
        return self.inspect()
    def heartbeat(self):return self.inspect()
    def pause(self):return self.inspect()  # Controller drain must not alter the operator's pause flag.
    def control(self,action):return self.queue.control(action)
    def close(self):self.queue.db.close()

    @database_operation
    def eligible(self,aid):
        identity(aid)
        if self.repo.show(aid):return True
        with sqlite3.connect(Path(self.settings['index']).absolute().as_uri()+'?mode=ro',uri=True) as db:
            return bool(db.execute('SELECT 1 FROM paper_authors WHERE identity_key=? LIMIT 1',('ieee:'+aid,)).fetchone())

    @database_operation
    def read(self,author_id):
        if not self.eligible(author_id):raise AuthorError('author_not_indexed')
        return self.queue.read(author_id)

    @database_operation
    def enqueue(self,author_id,refresh=False,trigger='manual'):
        if not self.eligible(author_id):raise AuthorError('author_not_indexed')
        old=self.repo.show(author_id)
        current=self.queue.read(author_id)
        if current['state'] in ('queued','fetching'):return self.queue.enqueue(author_id,trigger)
        if old and old.get('fetched_at') and not refresh:return {**current,'state':old['fetch_state']}
        if trigger!='manual' and (old or current['state']!='missing'):return current
        return self.queue.enqueue(author_id,trigger)

    def peek(self):
        health = self.inspect()
        if not health['compatible']:
            return {'priority': None, 'required_capability': 'author_profiles_v1', 'database': health['database']}
        self.seed()
        row=self.queue.db.execute("SELECT MIN(priority) FROM author_jobs WHERE state='queued'").fetchone()
        occupied=self.queue.db.execute("SELECT 1 FROM author_jobs WHERE state='fetching'").fetchone()
        return {'priority':None if self.queue.paused() or occupied else row[0], 'required_capability':'author_profiles_v1'}

    def claim(self,allow_retry=False):return self.queue.claim()

    @database_operation
    def apply(self,task,value):
        db=self.queue.db
        row=db.execute('SELECT * FROM author_jobs WHERE id=?',(task['id'],)).fetchone()
        if not row or row['state']!='fetching' or row['attempt']!=task['payload']['attempt']:return {'status':'stale'}
        if value.get('error')=='paused':
            state='queued';error=None
        elif value.get('error'):
            error=value['error'];state='blocked' if error=='access_restricted' else 'failed'
            self.repo.failed(row['author_id'],AuthorError(error),datetime.fromtimestamp(row['updated'],timezone.utc).isoformat())
        else:
            try:
                data=validate(value.get('records'))
                if data['author_id']!=row['author_id']:raise AuthorError('author_identity_mismatch')
            except AuthorError as failure:
                state='failed';error=failure.code
                self.repo.failed(row['author_id'],failure,datetime.fromtimestamp(row['updated'],timezone.utc).isoformat())
            else:
                # Only reuse validation when normalization left the profile
                # unchanged. Otherwise preserve the original second pass and
                # its exception boundary (e.g. nested HTML entity decoding).
                if data['profile'] != value['records'].get('profile'):
                    data=validate(data)
                saved=self.repo._save_validated(data)
                if saved.get('status')=='stale':state='failed';error='stale_author_observation'
                else:state='hidden' if data['profile']['is_hidden'] else 'complete';error=None
        with db:db.execute('UPDATE author_jobs SET state=?,error=?,updated=? WHERE id=?',(state,error,time.time(),row['id']))
        return {'status':state, 'error':error}

    def curated_papers(self):
        # Resolve current index membership daily so newly indexed papers are included.
        scope=json.loads(Path(self.settings['scope_file']).read_text())
        journals=set();conferences=set()
        for family in scope['families']:
            (journals if family['kind']=='Journals' else conferences).update(family['seriesIds'])
        with sqlite3.connect(Path(self.settings['index']).absolute().as_uri()+'?mode=ro',uri=True) as db:
            if conferences:
                placeholders=','.join('?' for _ in conferences)
                conferences.update(row[0] for row in db.execute("SELECT member FROM venue_members WHERE kind='Conferences' AND series IN ("+placeholders+")",sorted(conferences)))
            venues=sorted(journals|conferences)
            if not venues:return []
            return sorted({row[0] for row in db.execute('SELECT number FROM docs WHERE venue IN ('+','.join('?' for _ in venues)+')',venues)})

    def seed(self):
        """Bounded daily discovery. Attempts, including failures, are never auto-retried."""
        if not self.settings.get('background_enabled') or self.queue.paused():return
        from zoneinfo import ZoneInfo
        now=datetime.now(ZoneInfo('Asia/Shanghai'))
        slot=now.strftime('%Y-%m-%d') if now.hour>=3 else None
        if not slot:return
        db=self.queue.db
        old=db.execute("SELECT value FROM author_settings WHERE key='seed_day'").fetchone()
        if old and old[0]==slot:return
        # Resolve current selected scope; close the database operation after this batch.
        if self._papers is None:self._papers=self.curated_papers()
        if db.execute("SELECT COUNT(*) FROM author_jobs WHERE state='queued'").fetchone()[0]>=1000:return
        last=db.execute("SELECT value FROM author_settings WHERE key='seed_offset'").fetchone()
        offset=int(last[0]) if last else 0
        papers=self._papers[offset:offset+100]
        with self.repository():
            with sqlite3.connect(Path(self.settings['index']).absolute().as_uri()+'?mode=ro',uri=True) as index:
                if papers:
                    placeholders=','.join('?' for _ in papers)
                    rows=index.execute("SELECT DISTINCT a.identity_key FROM paper_authors a JOIN docs d ON d.id=a.doc_id WHERE d.number IN ("+placeholders+") AND a.identity_key LIKE 'ieee:%'",papers).fetchall()
                    for (key,) in rows:self.enqueue(key[5:],trigger='background')
        with db:
            db.execute("INSERT OR REPLACE INTO author_settings VALUES('seed_offset',?)",(str(offset+len(papers)) if papers else '0',))
            if not papers:
                db.execute("INSERT OR REPLACE INTO author_settings VALUES('seed_day',?)",(slot,))
                self._papers=None



def main():
    if len(sys.argv)>1 and sys.argv[1]=='parse':
        from .author_profiles import envelope
        try:print(json.dumps(envelope(json.load(sys.stdin),sys.argv[2])))
        except Exception:print(json.dumps({'error':'invalid_author_response'}));sys.exit(1)
        return
    config=json.loads(Path(sys.argv[1]).read_text())
    settings={**config['jobs']['authors'],'coordinator_state':config['state_dir']}
    bridge=Bridge(settings)
    try:
        for line in sys.stdin:
            try:
                request=json.loads(line);op=request.pop('op')
                if op not in ('inspect','acquire','heartbeat','pause','peek','claim','apply','read','enqueue','control'):raise ValueError('unknown_operation')
                reply={'ok':True,'result':getattr(bridge,op)(**request)}
            except Exception as error:
                code = error.args[0] if isinstance(error, pymysql.err.MySQLError) and error.args and isinstance(error.args[0], int) else None
                logging.getLogger(__name__).error('Author operation failed: type=%s database_code=%s', type(error).__name__, code)
                reply={'ok':False,'error':getattr(error,'code',type(error).__name__)}
            print(json.dumps(reply),flush=True)
    finally:bridge.close()

if __name__=='__main__':main()
