"""Optional anonymous reader-origin records, independent of account sessions."""
import ipaddress
import logging
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from contextlib import closing

from starlette.concurrency import run_in_threadpool


def client_address(scope):
    client=scope.get('client')
    if not client:return None
    try:
        value=ipaddress.ip_address(client[0])
        return str(value.ipv4_mapped if isinstance(value,ipaddress.IPv6Address) and value.ipv4_mapped else value)
    except (ValueError,TypeError):return None


def tracked_request(scope):
    if scope.get('type')!='http' or scope.get('method')!='GET':return False
    path=scope.get('path','')
    if not (path=='/' or re.fullmatch(r'/papers/[0-9]{1,64}',path)
            or path.startswith('/authors/')
            or re.match(r'^/api/(papers|authors|overview|publications|venues|catalog)(?:/|$)',path)):
        return False
    # Directory probes are not reader visits. No cookies, search terms or UA are stored.
    agent=next((v.decode('latin1').lower() for k,v in scope.get('headers',[]) if k.lower()==b'user-agent'),'')
    return '(local service inventory)' not in agent


class VisitStore:
    def __init__(self,path):
        self.path=Path(path).expanduser()
        if not self.path.is_absolute():raise ValueError('An absolute visit-state path is required')
        self.lock=threading.Lock()
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with closing(sqlite3.connect(self.path,timeout=0.25)) as db,db:
            # A separate monitor reads through a filesystem with no write permission.
            # DELETE mode lets that reader work without creating WAL/SHM sidecars.
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('CREATE TABLE IF NOT EXISTS visitors(ip TEXT PRIMARY KEY,first_seen REAL NOT NULL,last_seen REAL NOT NULL,requests INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE INDEX IF NOT EXISTS visitor_recency ON visitors(last_seen)')
            db.execute('CREATE TABLE IF NOT EXISTS task_requests(id TEXT PRIMARY KEY,ip TEXT NOT NULL,at REAL NOT NULL,kind TEXT NOT NULL,paper TEXT NOT NULL,status INTEGER NOT NULL,outcome TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS task_requests_host ON task_requests(ip,at DESC,id)')
            db.execute('CREATE TABLE IF NOT EXISTS task_links(request_id TEXT NOT NULL,queue TEXT NOT NULL,kind TEXT NOT NULL,task_id TEXT NOT NULL,run_id TEXT NOT NULL,binding TEXT NOT NULL,PRIMARY KEY(request_id,queue,kind,task_id,run_id))')
            db.execute('CREATE INDEX IF NOT EXISTS task_links_identity ON task_links(queue,task_id,run_id,request_id)')
            db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO meta VALUES(?,?)',('started_at',str(time.time())))
        self.path.chmod(0o600)

    def record(self,ip,at):
        with self.lock,closing(sqlite3.connect(self.path,timeout=0.25)) as db,db:
            db.execute('INSERT INTO visitors(ip,first_seen,last_seen,requests) VALUES(?,?,?,1) '
                       'ON CONFLICT(ip) DO UPDATE SET first_seen=MIN(first_seen,excluded.first_seen),'
                       'last_seen=MAX(last_seen,excluded.last_seen),requests=requests+1',(ip,at,at))

    def record_task(self,event,links):
        with self.lock,closing(sqlite3.connect(self.path,timeout=0.25)) as db,db:
            inserted = db.execute('INSERT OR IGNORE INTO task_requests VALUES(?,?,?,?,?,?,?)',
                       (event['id'],event['ip'],event['at'],event['kind'],event['paper'],event['status'],event['outcome'])).rowcount
            db.execute("UPDATE task_requests SET status=?,outcome=CASE WHEN outcome='associated' THEN outcome ELSE ? END WHERE id=?",
                       (event['status'], event['outcome'], event['id']))
            db.executemany('INSERT OR IGNORE INTO task_links VALUES(?,?,?,?,?,?)',
                           [(event['id'],v['queue'],v['kind'],v['task_id'],v['run_id'],v['binding']) for v in links])
            if inserted:
                db.execute('INSERT INTO visitors(ip,first_seen,last_seen,requests) VALUES(?,?,?,1) '
                           'ON CONFLICT(ip) DO UPDATE SET first_seen=MIN(first_seen,excluded.first_seen),'
                           'last_seen=MAX(last_seen,excluded.last_seen),requests=requests+1',(event['ip'],event['at'],event['at']))


class ReaderVisitRecords:
    def __init__(self,app,path):
        self.app=app;self.store=None;self.last_warning=0
        try:self.store=VisitStore(path)
        except Exception as error:self.warn(error)

    def warn(self,error):
        now=time.monotonic()
        if now-self.last_warning>=60 or self.last_warning==0:
            self.last_warning=now
            logging.getLogger('cirdc.visits').warning('Reader visit recording unavailable (%s)',type(error).__name__)

    async def __call__(self,scope,receive,send):
        ip=client_address(scope) if tracked_request(scope) else None
        if not ip or self.store is None:return await self.app(scope,receive,send)
        at=time.time();status=None
        async def record_status(message):
            nonlocal status
            if message.get('type')=='http.response.start':status=message.get('status')
            await send(message)
        await self.app(scope,receive,record_status)
        if status is not None and 200<=status<400:
            try:await run_in_threadpool(self.store.record,ip,at)
            except Exception as error:self.warn(error)


def enable_reader_visits(app,interface):
    path=os.environ.get('CIRDC_WEB_VISITS_FILE')
    if interface=='reader' and path:app.add_middleware(ReaderVisitRecords,path=path)
