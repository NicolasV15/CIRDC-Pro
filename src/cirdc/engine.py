import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from .model import digest, merge
from .provider import IEEE, UpstreamError, RequestLimiter
from .store import Store, BusyError
from .storage import Dataset


class FutureYearPending(UpstreamError):
    def __init__(self, kind, year):
        super().__init__('future_year_pending', 'The future publication year currently has no indexed records')
        self.detail = {'code': self.code, 'kind': kind, 'year': year,
                       'reason': 'confirmed_zero_records', 'recheck': 'next_explicit_update_or_retry'}


def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text())


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Service:
    def __init__(self, config, store=None, provider=None):
        self.config = config
        self.store = store or Store(config)
        self.provider = provider or IEEE(config)
        self.storage = Dataset(config)
        self.request_limiter = RequestLimiter(config.interval)
        if isinstance(self.provider, IEEE):
            self.provider.limiter = self.request_limiter

    def indexes(self):
        return {kind: self.storage.read_json('publicationInfo/' + name)
                for kind, name in [('Journals', 'all_journals.json'),
                                   ('Conferences', 'all_conferences.json')]}

    def plan(self, params=None):
        indexes = self.indexes()
        files = len(self.storage.article_paths())
        return {'scope': 'all_journals_and_conferences',
                'journals': len(indexes['Journals']), 'conference_series': len(indexes['Conferences']),
                'existing_article_files': files, 'fields': ['bibliographic', 'abstract', 'keywords'],
                'analysis_default': False, 'parameters': params or {},
                'database': self.summary()}

    def summary(self):
        rows = self.store.execute('SELECT abstract_state,keywords_state,COUNT(*) AS n FROM papers '
                                  'GROUP BY abstract_state,keywords_state')
        return {'papers': sum(r['n'] for r in rows), 'field_states': rows}

    def status(self, run_id=None):
        if not run_id:
            rows = self.store.execute('SELECT id FROM runs ORDER BY created_at DESC,id DESC LIMIT 1')
            if not rows:
                return {'status': 'no_runs', 'counts': {}, 'errors': [], 'database': self.summary()}
            run_id = rows[0]['id']
        run = self.store.run(run_id)
        run['counts'] = self.store.counts(run_id)
        run['errors'] = self.store.errors(run_id)
        run['deferred'] = self.store.deferred_tasks(run_id)
        if run['status'] == 'running' and not self.store.worker_active():
            run['observed_status'] = 'interrupted'
        return run

    def start(self, params=None, foreground=False):
        self.store.require_schema(force=True)
        params = {'stage': 'all', **{k: v for k, v in (params or {}).items() if v is not None and v is not False}}
        params['workers'] = int(params.get('workers', self.config.workers))
        if not 1 <= params['workers'] <= 8:
            raise ValueError('workers must be between 1 and 8')
        if params.get('max_tasks') is not None and params['max_tasks'] <= 0:
            raise ValueError('Task budget must be positive')
        if params.get('publication') and not str(params['publication']).isdigit():
            raise ValueError('Publication identifier must be numeric')
        if params.get('stage') == 'enrich' and params.get('publication'):
            indexes = self.indexes()
            number = str(params['publication'])
            if not any(number in index for index in indexes.values()):
                raise ValueError('Publication is not indexed; complete a catalog update before enrichment')
        with self.store.lock('submit'):
            active = self.store.execute("SELECT id,pid,status FROM runs WHERE status IN ('queued','running') "
                                        'ORDER BY created_at DESC LIMIT 1')
            if active:
                run = active[0]
                if run['status'] == 'queued' or self.store.worker_active():
                    if self.store.run(run['id'])['params'] != params:
                        raise BusyError('A different update scope is active; finish or resume that job first')
                    return {'run_id': run['id'], 'status': run['status'], 'reused': True}
            run_id = self.store.create_run(params)
            if not foreground:
                self._spawn(run_id)
        if foreground:
            self.work(run_id)
        return {'run_id': run_id, 'status': self.store.run(run_id)['status']}

    @staticmethod
    def _alive(pid):
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def _spawn(self, run_id):
        folder = self.config.state_dir / 'logs'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (folder / (run_id + '.log')).open('ab') as log:
            process = subprocess.Popen([sys.executable, '-m', 'cirdc.cli', '_worker', run_id],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True, close_fds=True, cwd=Path.home())
        self.store.set_run(run_id, pid=process.pid)

    def resume(self, run_id, retry=False, foreground=False, workers=None):
        self.store.require_schema(force=True)
        if workers is not None and not 1 <= workers <= 8:
            raise ValueError('workers must be between 1 and 8')
        with self.store.lock('submit'):
            with self.store.lock('worker'):
                run = self.store.run(run_id)
                if workers is not None:
                    run['params']['workers'] = workers
                    self.store.execute('UPDATE runs SET params=%s WHERE id=%s', (json.dumps(run['params']), run_id))
                self.store.execute("UPDATE tasks SET status='pending' WHERE run_id=%s AND status='running'", (run_id,))
                if retry:
                    self.store.execute("UPDATE tasks SET status='pending' WHERE run_id=%s "
                                       "AND ((status IN ('failed','blocked') AND attempts<3) OR status='deferred')", (run_id,))
                    run['stats']['fetch_seeded'] = False
                    run['stats']['enrich_seeded'] = False
                    self.store.execute('UPDATE runs SET stats=%s WHERE id=%s', (json.dumps(run['stats']), run_id))
                self.store.db.commit()
                self.store.set_run(run_id, status='queued', error='')
            if not foreground:
                self._spawn(run_id)
        if foreground:
            self.work(run_id)
        return {'run_id': run_id, 'status': self.store.run(run_id)['status'], 'previous_status': run['status']}

    def flush_exports(self, run_id):
        from pathlib import Path
        for export in self.store.execute("SELECT * FROM exports WHERE run_id=%s AND status='pending' ORDER BY id", (run_id,)):
            if self.storage.remote:
                self.storage.publish(export)
                self.store.execute("UPDATE exports SET status='done',error=NULL WHERE id=%s", (export['id'],))
                self.store.execute('INSERT INTO manifests(path,digest) VALUES (%s,%s) '
                                   'ON DUPLICATE KEY UPDATE digest=VALUES(digest)', (export['path'], export['digest']))
                self.store.db.commit()
                continue
            content = Path(export['staged_path']).read_bytes()
            if digest(content) != export['digest']:
                raise RuntimeError('Staged export digest does not match')
            target = self.config.destination(export['path'])
            old = target.read_bytes() if target.exists() else None
            if old != content:
                if old is not None:
                    backup = self.config.state_dir / 'backups' / run_id / export['path']
                    if not backup.exists():
                        atomic_write(backup, old)
                atomic_write(target, content)
            self.store.execute("UPDATE exports SET status='done',error=NULL WHERE id=%s", (export['id'],))
            self.store.execute('INSERT INTO manifests(path,digest) VALUES (%s,%s) '
                               'ON DUPLICATE KEY UPDATE digest=VALUES(digest)',
                               (export['path'], export['digest']))
            self.store.db.commit()

    def _seed(self, run_id, params, stats):
        if not stats.get('import_seeded'):
            if not params.get('skip_import') and params.get('stage') != 'catalog':
                self.store.add_tasks(run_id, 'import', ((p, {'path': p}) for p in self.storage.article_paths()))
            stats['import_seeded'] = True
            self.store.set_run(run_id, stats=stats)
        if not stats.get('catalog_seeded'):
            if not params.get('skip_catalog') and params.get('stage') != 'enrich':
                current = datetime.now().year
                for kind, earliest in [('Journals', 1884), ('Conferences', 1936)]:
                    years = self.storage.years(kind)
                    # Future snapshots must not push the current-year refresh window forward.
                    start = max(earliest, min(max(years), current) - 1) if years else earliest
                    selected_years = ([int(params['year'])] if params.get('year') is not None
                                      else range(start, current + 2))
                    self.store.add_tasks(run_id, 'catalog', ((f'{kind}/{year}', {'kind': kind, 'year': year})
                                                            for year in selected_years))
            stats['catalog_seeded'] = True
            self.store.set_run(run_id, stats=stats)

    def _seed_fetch(self, run_id, params, stats):
        if stats.get('fetch_seeded'):
            return
        if params.get('stage') in ('catalog', 'enrich'):
            stats['fetch_seeded'] = True
            self.store.set_run(run_id, stats=stats)
            return
        now = datetime.now().year
        for kind, index in self.indexes().items():
            items = []
            for number, venue in index.items():
                if params.get('publication') and str(number) != str(params['publication']):
                    continue
                self.store.execute('INSERT INTO venues(kind,number,data) VALUES (%s,%s,%s) '
                                   'ON DUPLICATE KEY UPDATE data=VALUES(data)',
                                   (kind, str(number), json.dumps(venue, ensure_ascii=False)))
                if kind == 'Journals':
                    start = int(venue.get('start_year') or now)
                    end = venue.get('end_year', 'Present')
                    end = now if str(end).lower() == 'present' else int(end or now)
                    years = [int(params['year'])] if params.get('year') is not None else range(start, min(end, now) + 1)
                    for year in years:
                        path = f'articleInfo/Journals/{number}/{year}.json'
                        # Historic complete snapshots are retained; missing snapshots and recent years are refreshed.
                        checked = self.store.execute('SELECT path FROM sync_cursors WHERE path=%s '
                                                     'AND checked_at > CURRENT_TIMESTAMP - INTERVAL 30 DAY', (path,))
                        if not params.get('year') and year < now - 1 and checked:
                            continue
                        items.append((path, {'kind': kind, 'number': str(number), 'year': year, 'path': path}))
                else:
                    for edition in venue.get('titleHistory', []):
                        child = str(edition.get('publicationNumber') or '')
                        year = str(edition.get('year') or '')
                        if not child or (params.get('year') is not None and year != str(params['year'])):
                            continue
                        path = f'articleInfo/Conferences/{number}/{child}.json'
                        checked = self.store.execute('SELECT path FROM sync_cursors WHERE path=%s '
                                                     'AND checked_at > CURRENT_TIMESTAMP - INTERVAL 30 DAY', (path,))
                        if not params.get('year') and year.isdigit() and int(year) < now - 1 and checked:
                            continue
                        items.append((path, {'kind': kind, 'number': child, 'year': None, 'path': path}))
            self.store.db.commit()
            self.store.add_tasks(run_id, 'fetch', items)
        stats['fetch_seeded'] = True
        self.store.set_run(run_id, stats=stats)

    def _seed_enrich(self, run_id, params, stats):
        if stats.get('enrich_seeded'):
            return
        if params.get('stage') in ('catalog', 'metadata'):
            stats['enrich_seeded'] = True
            self.store.set_run(run_id, stats=stats)
            return
        last = ''
        indexes = self.indexes() if params.get('publication') else None
        while True:
            clause = ''
            values = [last]
            if params.get('publication'):
                clause = ' AND number IN (SELECT number FROM paper_files WHERE path LIKE %s)'
                kind = 'Journals' if str(params['publication']) in indexes['Journals'] else 'Conferences'
                pattern = f'articleInfo/{kind}/{params["publication"]}/%'
                if params.get('year') is not None:
                    if kind == 'Journals':
                        pattern = f'articleInfo/Journals/{params["publication"]}/{params["year"]}.json'
                    else:
                        editions = [str(h['publicationNumber']) for h in indexes['Conferences'][str(params['publication'])].get('titleHistory', [])
                                    if str(h.get('year')) == str(params['year']) and h.get('publicationNumber')]
                        if not editions:
                            stats['enrich_seeded'] = True
                            self.store.set_run(run_id, stats=stats)
                            return
                        clause = ' AND number IN (SELECT number FROM paper_files WHERE path IN (' + ','.join(['%s'] * len(editions)) + '))'
                        values.extend(f'articleInfo/Conferences/{params["publication"]}/{edition}.json' for edition in editions)
                if len(values) == 1:
                    values.append(pattern)
            rows = self.store.execute("SELECT number FROM papers WHERE number>%s AND "
                                      "(abstract_state IN ('pending','failed') OR keywords_state IN ('pending','failed'))"
                                      + clause + ' ORDER BY number LIMIT 1000', values)
            if not rows:
                break
            self.store.add_tasks(run_id, 'enrich', ((r['number'], {'number': r['number']}) for r in rows))
            last = rows[-1]['number']
            self.store.set_run(run_id, stats=stats)
        stats['enrich_seeded'] = True
        self.store.set_run(run_id, stats=stats)

    def _import(self, payload, stats):
        path = payload['path']
        data = self.storage.read_bytes(path)
        if data is None:
            raise ValueError('Article snapshot is missing')
        sha = digest(data)
        old = self.store.execute('SELECT digest FROM manifests WHERE path=%s', (path,))
        if old and old[0]['digest'] == sha:
            stats['files_skipped'] = stats.get('files_skipped', 0) + 1
            return
        records = json.loads(data)
        if not isinstance(records, list):
            raise ValueError('Article snapshot must contain a list')
        count = self.store.upsert_records(records, path)
        self.store.execute('INSERT INTO manifests(path,digest) VALUES (%s,%s) '
                           'ON DUPLICATE KEY UPDATE digest=VALUES(digest)', (path, sha))
        self.store.db.commit()
        stats['files_imported'] = stats.get('files_imported', 0) + 1
        stats['records_imported'] = stats.get('records_imported', 0) + count

    def _catalog(self, run_id, payload):
        kind, year = payload['kind'], payload['year']
        records = self.provider.publication_year(kind, year)
        if int(year) > datetime.now().year and not records:
            # Do not replace an existing future snapshot or merged index with an empty forecast.
            raise FutureYearPending(kind, int(year))
        name = 'all_journals.json' if kind == 'Journals' else 'all_conferences.json'
        relative = 'publicationInfo/' + name
        index = self.storage.read_json(relative)
        for r in records:
            if kind == 'Journals':
                all_years = str(r.get('allYears') or '')
                parts = all_years.split(' - ')
                number = str(r.get('publicationNumber') or '')
                if number:
                    old = index.get(number, {})
                    index[number] = merge(old, {'publicationNumber': number, 'title': r.get('title'),
                                               'start_year': parts[0].strip() or str(year),
                                               'end_year': parts[1].strip() if len(parts) > 1 else 'Present'})
                for h in r.get('titleHistory', []):
                    n = str(h.get('publicationNumber') or '')
                    if n:
                        index[n] = merge(index.get(n, {}), {'publicationNumber': n, 'title': h.get('displayTitle'),
                                                           'start_year': h.get('startYear'), 'end_year': h.get('endYear')})
            else:
                n = str(r.get('parentPublicationNumber') or '')
                if not n:
                    continue
                old = index.setdefault(n, {'parentPublicationNumber': n, 'titleHistory': []})
                old['parentTitle'] = r.get('parentTitle') or r.get('displayTitle') or old.get('parentTitle', '')
                history = {str(h['publicationNumber']): h for h in old.get('titleHistory', []) if h.get('publicationNumber')}
                for h in r.get('titleHistory', []) or [r]:
                    child = str(h.get('publicationNumber') or '')
                    if child:
                        history[child] = merge(history.get(child, {}), {'publicationNumber': child,
                                              'displayTitle': h.get('displayTitle'),
                                              'year': str(h.get('startYear') or h.get('year') or year)})
                old['titleHistory'] = list(history.values())
        self.store.stage_export(run_id, f'publicationInfo/{kind}/{year}/cirdc.json',
                                {'records': records, 'totalRecords': len(records), 'totalPages': 1})
        self.store.stage_export(run_id, relative, index)
        self.store.db.commit()

    def _fetch(self, run_id, payload, stats, rows=None):
        if rows is None:
            rows = self.provider.search_all(payload['number'], payload['year'])
        old = self.storage.read_json(payload['path'], [])
        if not isinstance(old, list):
            raise ValueError('Existing article snapshot is not a list')
        merged = {str(r['articleNumber']): r for r in old if r.get('articleNumber') is not None}
        for row in rows:
            key = row['articleNumber']
            merged[key] = merge(merged.get(key, {}), row)
        values = list(merged.values())
        self.store.upsert_records(values, payload['path'])
        self.store.stage_export(run_id, payload['path'], values)
        self.store.execute('INSERT INTO sync_cursors(path,source_count) VALUES (%s,%s) '
                           'ON DUPLICATE KEY UPDATE source_count=VALUES(source_count),checked_at=CURRENT_TIMESTAMP',
                           (payload['path'], len(rows)))
        self.store.db.commit()
        stats['records_fetched'] = stats.get('records_fetched', 0) + len(rows)

    def _enrich(self, run_id, payload, stats, document=None):
        paper = self.store.paper(payload['number'])
        if paper['abstract_state'] in ('complete', 'no_data') and paper['keywords_state'] in ('complete', 'no_data'):
            return
        update, states = document if document is not None else self.provider.document(payload['number'])
        self.store.update_document(update, states)
        files = self.store.execute('SELECT path FROM paper_files WHERE number=%s', (payload['number'],))
        for file in files:
            values = self.storage.read_json(file['path'], [])
            for i, row in enumerate(values):
                if str(row.get('articleNumber')) == payload['number']:
                    values[i] = merge(row, update)
            self.store.stage_export(run_id, file['path'], values)
        self.store.db.commit()
        stats['documents_checked'] = stats.get('documents_checked', 0) + 1
        stats['source_no_data_fields'] = stats.get('source_no_data_fields', 0) + sum(v == 'no_data' for v in states.values())

    def _parallel_work(self, run_id, params, stats, stopping, workers):
        """Only HTTP runs in threads; this coordinator owns SQL and all exports."""
        processed = 0
        budget = params.get('max_tasks')
        thread_state = threading.local()
        providers = []

        def network(task, skip=False):
            if skip:
                return None
            if not hasattr(thread_state, 'provider'):
                provider = (IEEE(self.config, limiter=self.request_limiter)
                            if isinstance(self.provider, IEEE) else self.provider)
                thread_state.provider = provider
                providers.append(provider)
            provider = thread_state.provider
            payload = task['payload']
            if task['kind'] == 'fetch':
                return provider.search_all(payload['number'], payload['year'])
            return provider.document(payload['number'])

        def apply(task, value=None, error=None):
            blocked = None
            try:
                if error is not None:
                    raise error
                kind, payload = task['kind'], task['payload']
                if kind == 'import':
                    self._import(payload, stats)
                elif kind == 'catalog':
                    self._catalog(run_id, payload)
                elif kind == 'fetch':
                    self._fetch(run_id, payload, stats, rows=value)
                else:
                    self._enrich(run_id, payload, stats, document=value)
                self.flush_exports(run_id)
                self.store.task_state(task['id'], 'done')
            except FutureYearPending as problem:
                self.store.db.rollback()
                self.store.task_state(task['id'], 'deferred', json.dumps(problem.detail))
                stats['future_year_deferrals'] = stats.get('future_year_deferrals', 0) + 1
            except UpstreamError as problem:
                self.store.db.rollback()
                blocked = problem.code if problem.code in ('access_restricted', 'network_error') else None
                if task['kind'] == 'enrich':
                    self.store.execute("UPDATE papers SET abstract_state=CASE WHEN abstract_state='pending' "
                                       "THEN 'failed' ELSE abstract_state END,keywords_state=CASE WHEN "
                                       "keywords_state='pending' THEN 'failed' ELSE keywords_state END WHERE number=%s",
                                       (task['payload']['number'],))
                self.store.task_state(task['id'], 'blocked' if blocked else 'failed', problem.code + ': ' + str(problem))
            except (ValueError, json.JSONDecodeError) as problem:
                self.store.db.rollback()
                self.store.task_state(task['id'], 'failed', type(problem).__name__ + ': ' + str(problem)[:300])
            self.store.set_run(run_id, stats=stats)
            return blocked

        def finish(status, error=''):
            self.store.set_run(run_id, status=status, stats=stats, error=error)

        try:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='cirdc-fetch') as pool:
                while not stopping[0]:
                    self.flush_exports(run_id)
                    task = self.store.next_task(run_id, ['import', 'catalog'])
                    if task is None:
                        break
                    self.store.task_state(task['id'], 'running')
                    blocked = apply(task)
                    processed += 1
                    if blocked:
                        return finish('blocked', blocked)
                    if budget and processed >= budget:
                        return finish('paused')
                for kind, seed in [('fetch', self._seed_fetch), ('enrich', self._seed_enrich)]:
                    if stopping[0]:
                        return finish('paused')
                    seed(run_id, params, stats)
                    active = {}
                    blocked = None
                    heartbeat = time.monotonic()
                    while True:
                        while (not stopping[0] and not blocked and len(active) < workers
                               and (not budget or processed + len(active) < budget)):
                            task = self.store.next_task(run_id, [kind])
                            if task is None:
                                break
                            skip = False
                            if kind == 'enrich':
                                paper = self.store.paper(task['payload']['number'])
                                skip = (paper['abstract_state'] in ('complete', 'no_data')
                                        and paper['keywords_state'] in ('complete', 'no_data'))
                            self.store.task_state(task['id'], 'running')
                            active[pool.submit(network, task, skip)] = task
                            stats['inflight_tasks_peak'] = max(stats.get('inflight_tasks_peak', 0), len(active))
                        if not active:
                            break
                        completed, _ = wait(active, timeout=1, return_when=FIRST_COMPLETED)
                        for future in completed:
                            task = active.pop(future)
                            try:
                                value = future.result()
                                error = None
                            except Exception as problem:
                                value, error = None, problem
                            blocked = apply(task, value, error) or blocked
                            processed += 1
                        if time.monotonic() - heartbeat >= 10:
                            self.store.set_run(run_id, stats=stats)
                            heartbeat = time.monotonic()
                    if blocked:
                        return finish('blocked', blocked)
                    if stopping[0] or (budget and processed >= budget):
                        return finish('paused')
                counts = self.store.counts(run_id)
                return finish('partial' if any(counts.get(s) for s in ('failed', 'blocked', 'deferred')) else 'completed')
        finally:
            for provider in providers:
                if isinstance(provider, IEEE):
                    provider.session.close()

    def work(self, run_id):
        self.store.require_schema(force=True)
        stopping = [False]
        previous = {}
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda *_: stopping.__setitem__(0, True))
        try:
            with self.store.lock():
                run = self.store.run(run_id)
                params, stats = run['params'], run['stats']
                workers = int(params.get('workers', self.config.workers))
                if not 1 <= workers <= 8:
                    raise ValueError('workers must be between 1 and 8')
                stats.update(executor_host=socket.gethostname(), fetch_workers=workers)
                self.store.set_run(run_id, status='running', pid=os.getpid(), stats=stats, error='')
                self.store.execute("UPDATE tasks SET status='pending' WHERE run_id=%s AND status='running'", (run_id,))
                self.store.db.commit()
                self._seed(run_id, params, stats)
                if workers > 1:
                    return self._parallel_work(run_id, params, stats, stopping, workers)
                processed = 0
                while not stopping[0]:
                    self.flush_exports(run_id)
                    task = self.store.next_task(run_id, ['import', 'catalog'])
                    if task is None:
                        self._seed_fetch(run_id, params, stats)
                        task = self.store.next_task(run_id, ['fetch'])
                    if task is None:
                        self._seed_enrich(run_id, params, stats)
                        task = self.store.next_task(run_id, ['enrich'])
                    if task is None:
                        counts = self.store.counts(run_id)
                        status = 'partial' if any(counts.get(s) for s in ('failed', 'blocked', 'deferred')) else 'completed'
                        self.store.set_run(run_id, status=status, stats=stats)
                        return
                    self.store.task_state(task['id'], 'running')
                    try:
                        if task['kind'] == 'import':
                            self._import(task['payload'], stats)
                        elif task['kind'] == 'catalog':
                            self._catalog(run_id, task['payload'])
                        elif task['kind'] == 'fetch':
                            self._fetch(run_id, task['payload'], stats)
                        else:
                            self._enrich(run_id, task['payload'], stats)
                        self.flush_exports(run_id)
                        self.store.task_state(task['id'], 'done')
                    except FutureYearPending as error:
                        self.store.db.rollback()
                        self.store.task_state(task['id'], 'deferred', json.dumps(error.detail))
                        stats['future_year_deferrals'] = stats.get('future_year_deferrals', 0) + 1
                    except UpstreamError as error:
                        self.store.db.rollback()
                        blocked = error.code in ('access_restricted', 'network_error')
                        if task['kind'] == 'enrich':
                            self.store.execute("UPDATE papers SET abstract_state=CASE WHEN abstract_state='pending' "
                                               "THEN 'failed' ELSE abstract_state END,keywords_state=CASE WHEN "
                                               "keywords_state='pending' THEN 'failed' ELSE keywords_state END WHERE number=%s",
                                               (task['payload']['number'],))
                        self.store.task_state(task['id'], 'blocked' if blocked else 'failed', error.code + ': ' + str(error))
                        if blocked:
                            self.store.set_run(run_id, status='blocked', stats=stats, error=error.code)
                            return
                    except (ValueError, json.JSONDecodeError) as error:
                        self.store.db.rollback()
                        self.store.task_state(task['id'], 'failed', type(error).__name__ + ': ' + str(error)[:300])
                    processed += 1
                    self.store.set_run(run_id, stats=stats)
                    if params.get('max_tasks') and processed >= params['max_tasks']:
                        self.store.set_run(run_id, status='paused', stats=stats)
                        return
                self.store.set_run(run_id, status='paused', stats=stats)
        except Exception as error:
            self.store.db.rollback()
            self.store.set_run(run_id, status='blocked', error=type(error).__name__ + ': operation interrupted; inspect local logs')
            raise
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
