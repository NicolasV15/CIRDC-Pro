"""Signed-in reader features: synced preferences, favorites and favorite PDF archives.

Every operation takes the user from the session; clients never name another user. Favorites store only
the verified paper identity plus a title for display, never full text or files. Archives copy cached PDFs
through this application's own read-only routes and never contact a source.
"""
import asyncio
import json
import re
import secrets
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse
from starlette.routing import Route

from .settings import state_dir

THEMES = frozenset(('system', 'classic-green', 'plain-white', 'graphite', 'paper', 'midnight', 'lavender'))
LANGUAGES = frozenset(('zh', 'en'))
SOURCES = ('ieee', 'arxiv')
ARCHIVE_LIMIT = 100
ARCHIVE_SECONDS = 3600
ARCHIVES_PER_USER = 3
FILE_LIMIT = 512 * 1024 * 1024
SKIP_REASONS = ('missing', 'restricted', 'not_packaged', 'unreadable', 'paper_missing')


class ArchiveError(Exception):
    """An unexpected failure while packaging; the whole archive is abandoned."""


class Directory:
    """Paper identities the deployment can verify; subclasses supply the actual catalogs."""

    def ieee(self, numbers):
        """{number: {'title', 'year'}} for papers that exist."""
        raise NotImplementedError

    def arxiv(self, paper_id):
        """The arXiv paper with its observed versions, or None."""
        raise NotImplementedError

    def pdf_route(self, source, paper_id, version):
        """This application's read-only route for the cached PDF, or None when none is linked."""
        raise NotImplementedError


def arxiv_year(identifier):
    match = re.search(r'/(\d\d)', identifier) or re.match(r'(\d\d)\d\d\.', identifier)
    if not match:
        return None
    value = int(match[1])
    return (1900 if '/' in identifier and value >= 91 else 2000) + value


class Personal:
    def __init__(self, accounts, directory):
        self.accounts = accounts
        self.directory = directory

    # Preferences -------------------------------------------------------------------------------
    def settings(self, username):
        with self.accounts.db() as db:
            row = db.execute('SELECT theme,language,updated FROM user_settings WHERE username=?', (username,)).fetchone()
        return {'theme': row['theme'], 'language': row['language'], 'updated': row['updated']} if row else \
            {'theme': None, 'language': None, 'updated': None}

    def save_settings(self, username, values):
        theme, language = values.get('theme'), values.get('language')
        if theme is not None and theme not in THEMES or language is not None and language not in LANGUAGES:
            raise ValueError('invalid_settings')
        if theme is None and language is None:
            raise ValueError('invalid_settings')
        with self.accounts.db() as db:
            db.execute('INSERT INTO user_settings(username,theme,language,updated) VALUES(?,?,?,?) '
                       'ON CONFLICT(username) DO UPDATE SET theme=coalesce(excluded.theme,theme),'
                       'language=coalesce(excluded.language,language),updated=excluded.updated',
                       (username, theme, language, time.time()))
        return self.settings(username)

    # Favorites ---------------------------------------------------------------------------------
    @staticmethod
    def identity(item):
        if not isinstance(item, dict):
            raise ValueError('invalid_favorite')
        source, paper_id = item.get('source'), str(item.get('paper_id', ''))
        if source not in SOURCES or not re.fullmatch(r'[0-9]{1,64}', paper_id):
            raise ValueError('invalid_favorite')
        version = item.get('version', 0)
        if source == 'arxiv':
            if type(version) is not int or not 1 <= version <= 10000:
                raise ValueError('invalid_favorite')
        elif version not in (0, None):
            raise ValueError('invalid_favorite')
        return source, paper_id, version if source == 'arxiv' else 0

    def verify(self, identities):
        """Server-side identity check; the stored title and identifier come from the catalogs."""
        numbers = [paper_id for source, paper_id, _ in identities if source == 'ieee']
        found = self.directory.ieee(numbers) if numbers else {}
        result = []
        for source, paper_id, version in identities:
            if source == 'ieee':
                paper = found.get(paper_id)
                if not paper:
                    raise LookupError('paper_not_found')
                result.append((source, paper_id, 0, paper_id, paper.get('title') or '', paper.get('year')))
            else:
                paper = self.directory.arxiv(paper_id)
                if not paper or version not in [v['version'] for v in paper.get('versions') or []]:
                    raise LookupError('paper_not_found')
                result.append((source, paper_id, version, paper['arxiv_id'], paper.get('title') or '',
                               arxiv_year(paper['arxiv_id'])))
        return result

    def add(self, username, items):
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise ValueError('invalid_favorite')
        identities = list(dict.fromkeys(self.identity(item) for item in items))
        rows = self.verify(identities)
        with self.accounts.db() as db:
            now = time.time()
            for row in rows:
                db.execute('INSERT OR IGNORE INTO favorites(username,source,paper_id,version,identifier,title,year,created) '
                           'VALUES(?,?,?,?,?,?,?,?)', (username, *row, now))
        return self.state(username, identities)

    def remove(self, username, ids):
        if not isinstance(ids, list) or not 1 <= len(ids) <= 1000 or not all(type(i) is int for i in ids):
            raise ValueError('invalid_favorite')
        with self.accounts.db() as db:
            removed = db.execute('DELETE FROM favorites WHERE username=? AND id IN (' + ','.join('?' * len(ids)) + ')',
                                 (username, *ids)).rowcount
        return {'removed': removed}

    def state(self, username, identities):
        identities = list(identities)[:200]
        result = {}
        with self.accounts.db() as db:
            for source, paper_id, version in identities:
                if source == 'arxiv' and not version:
                    rows = db.execute('SELECT id,version FROM favorites WHERE username=? AND source=? AND paper_id=?',
                                      (username, source, paper_id)).fetchall()
                    result[f'{source}:{paper_id}'] = {'versions': {str(r['version']): r['id'] for r in rows}}
                    continue
                row = db.execute('SELECT id FROM favorites WHERE username=? AND source=? AND paper_id=? AND version=?',
                                 (username, source, paper_id, version)).fetchone()
                key = f'{source}:{paper_id}' + (f':{version}' if source == 'arxiv' else '')
                result[key] = row['id'] if row else None
        return {'items': result}

    @staticmethod
    def parse_keys(value):
        identities = []
        for key in (value or '').split(','):
            if not key:
                continue
            parts = key.split(':')
            if len(parts) not in (2, 3) or parts[0] not in SOURCES or not re.fullmatch(r'[0-9]{1,64}', parts[1]):
                raise ValueError('invalid_favorite')
            if len(parts) == 3 and (parts[0] != 'arxiv' or not re.fullmatch(r'[1-9][0-9]{0,4}', parts[2])):
                raise ValueError('invalid_favorite')
            identities.append((parts[0], parts[1], int(parts[2]) if len(parts) == 3 else 0))
        if len(identities) > 200:
            raise ValueError('invalid_favorite')
        return identities

    def list(self, username, source=None, cursor=None, limit=25):
        if source not in (None, '', *SOURCES) or not 1 <= limit <= 100:
            raise ValueError('invalid_favorite_query')
        clauses, values = ['username=?'], [username]
        if source:
            clauses.append('source=?')
            values.append(source)
        if cursor is not None:
            clauses.append('id<?')
            values.append(cursor)
        with self.accounts.db() as db:
            rows = [dict(r) for r in db.execute('SELECT id,source,paper_id,version,identifier,title,year,created FROM favorites '
                                                'WHERE ' + ' AND '.join(clauses) + ' ORDER BY id DESC LIMIT ?',
                                                (*values, limit + 1))]
            counts = {r['source']: r['n'] for r in db.execute('SELECT source,COUNT(*) n FROM favorites WHERE username=? '
                                                              'GROUP BY source', (username,))}
        more = len(rows) > limit
        rows = rows[:limit]
        self.annotate(rows)
        return {'items': rows, 'next_cursor': rows[-1]['id'] if more else None,
                'counts': {name: counts.get(name, 0) for name in SOURCES}, 'total': sum(counts.values())}

    def annotate(self, rows):
        """Current readability of each favorite; a missing paper or version keeps the saved entry."""
        numbers = [r['paper_id'] for r in rows if r['source'] == 'ieee']
        try:
            found = self.directory.ieee(numbers) if numbers else {}
        except Exception:
            found = None
        for row in rows:
            if row['source'] == 'ieee':
                if found is None:
                    row['status'] = 'unavailable'
                elif row['paper_id'] in found:
                    row['status'] = 'ok'
                    row['title'] = found[row['paper_id']].get('title') or row['title']
                else:
                    row['status'] = 'paper_missing'
                continue
            try:
                paper = self.directory.arxiv(row['paper_id'])
            except Exception:
                row['status'] = 'unavailable'
                continue
            if not paper:
                row['status'] = 'paper_missing'
            elif row['version'] not in [v['version'] for v in paper.get('versions') or []]:
                row['status'] = 'version_missing'
            else:
                row['status'] = 'ok'
                row['title'] = paper.get('title') or row['title']
                row['latest_version'] = max(v['version'] for v in paper['versions'])

    def owned(self, username, ids):
        with self.accounts.db() as db:
            rows = {r['id']: dict(r) for r in db.execute(
                'SELECT id,source,paper_id,version,identifier,title,year FROM favorites WHERE username=? AND id IN ('
                + ','.join('?' * len(ids)) + ')', (username, *ids))}
        if len(rows) != len(set(ids)):
            raise LookupError('favorite_not_found')
        return [rows[i] for i in dict.fromkeys(ids)]


def safe_filename(value, fallback, used):
    """A single path component ending in .pdf; names already used get a numbered suffix."""
    name = unicodedata.normalize('NFC', value if isinstance(value, str) else '')
    if (not name.lower().endswith('.pdf') or '/' in name or '\\' in name or name.startswith('.')
            or re.search(r'[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069:*?"<>|]', name)
            or len(name.encode()) > 240):
        name = fallback
    stem = name[:-4]
    candidate, attempt = name, 1
    while candidate.lower() in used:
        attempt += 1
        candidate = f'{stem} ({attempt}).pdf'
    used.add(candidate.lower())
    return candidate


def default_filename(row):
    identifier = row['identifier'].replace('/', '-') + (f"v{row['version']}" if row['source'] == 'arxiv' else '')
    return f"{row['source']}_{identifier}.pdf"


async def read_route(app, path, destination):
    """GET one of this application's own read-only routes in-process and save the body.

    The middleware stack is skipped: the route comes from a verified paper identity, never from the client.
    Returns (status, content_type, error_code).
    """
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'GET', 'scheme': 'http',
             'path': path, 'raw_path': path.encode(), 'query_string': b'', 'root_path': '', 'app': app,
             'headers': [(b'host', b'localhost')], 'client': ('127.0.0.1', 0), 'server': ('localhost', 80)}
    state = {'status': 0, 'type': '', 'size': 0, 'json': bytearray()}

    requested, finished = [], asyncio.Event()

    async def receive():
        # The request body once, then wait: streaming responses listen for a disconnect until they finish.
        if not requested:
            requested.append(True)
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        await finished.wait()
        return {'type': 'http.disconnect'}

    output = await run_in_threadpool(open, destination, 'wb')
    try:
        async def send(message):
            if message['type'] == 'http.response.start':
                state['status'] = message['status']
                headers = {k.decode().lower(): v.decode() for k, v in message.get('headers', [])}
                state['type'] = headers.get('content-type', '')
            elif message['type'] == 'http.response.body':
                chunk = message.get('body', b'')
                if state['status'] == 200:
                    state['size'] += len(chunk)
                    if state['size'] > FILE_LIMIT:
                        raise ArchiveError('file_too_large')
                    await run_in_threadpool(output.write, chunk)
                elif len(state['json']) < 4096:
                    state['json'].extend(chunk[:4096])

        await app.router(scope, receive, send)
    finally:
        finished.set()
        await run_in_threadpool(output.close)
    code = ''
    if state['status'] != 200:
        try:
            code = str(json.loads(bytes(state['json'])).get('error', ''))
        except (ValueError, AttributeError):
            code = ''
    return state['status'], state['type'], code


def has_pdf_signature(path):
    with open(path, 'rb') as stream:
        return stream.read(5) == b'%PDF-'


def skip_reason(status, code):
    if 'not_packaged' in code:
        return 'not_packaged'
    if status in (401, 403, 451) or 'restricted' in code or 'licensed' in code:
        return 'restricted'
    if status == 404:
        return 'missing'
    return 'unreadable'


class Archives:
    def __init__(self, personal, app_ref):
        self.personal = personal
        self.app_ref = app_ref

    @property
    def folder(self):
        path = state_dir() / 'archives'
        path.mkdir(mode=0o700, exist_ok=True)
        return path

    def cleanup(self, now=None):
        now = time.time() if now is None else now
        with self.personal.accounts.db() as db:
            expired = db.execute('SELECT id,path FROM archives WHERE expires<=?', (now,)).fetchall()
            db.execute('DELETE FROM archives WHERE expires<=?', (now,))
            known = {r['path'] for r in db.execute('SELECT path FROM archives')}
        for row in expired:
            Path(row['path']).unlink(missing_ok=True)
        for path in self.folder.iterdir():
            # Unregistered leftovers from an interrupted preparation are removed after the archive lifetime.
            if str(path) not in known and path.stat().st_mtime < now - ARCHIVE_SECONDS:
                path.unlink(missing_ok=True)

    async def prepare(self, username, ids, filenames):
        if not isinstance(ids, list) or not ids or not all(type(i) is int for i in ids):
            raise ValueError('invalid_archive_request')
        if len(set(ids)) > ARCHIVE_LIMIT:
            raise OverflowError('too_many_archive_items')
        if not isinstance(filenames, dict):
            filenames = {}
        await run_in_threadpool(self.cleanup)
        rows = await run_in_threadpool(self.personal.owned, username, ids)
        app = self.app_ref()
        work = Path(tempfile.mkdtemp(prefix='prepare-', dir=self.folder))
        archive_id = secrets.token_hex(16)
        target = self.folder / (archive_id + '.zip')
        used, entries, skipped = set(), [], []
        try:
            for row in rows:
                route = self.personal.directory.pdf_route(row['source'], row['paper_id'], row['version'])
                if not route:
                    skipped.append({'id': row['id'], 'reason': 'missing'})
                    continue
                partial = work / f"{row['id']}.part"
                status, _kind, code = await read_route(app, route, partial)
                if status == 200:
                    if not await run_in_threadpool(has_pdf_signature, partial):
                        skipped.append({'id': row['id'], 'reason': 'unreadable'})
                        partial.unlink()
                        continue
                    name = safe_filename(filenames.get(str(row['id'])), default_filename(row), used)
                    entries.append((partial, name, row))
                else:
                    partial.unlink(missing_ok=True)
                    skipped.append({'id': row['id'], 'reason': skip_reason(status, code)})
            if entries:
                def write():
                    with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED, allowZip64=True) as archive:
                        for path, name, _ in entries:
                            archive.write(path, name)
                await run_in_threadpool(write)
                target.chmod(0o600)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        finally:
            for path in work.iterdir():
                path.unlink(missing_ok=True)
            work.rmdir()
        result = {'files': [{'id': row['id'], 'filename': name} for _, name, row in entries], 'skipped': skipped,
                  'requested': len(rows)}
        if not entries:
            return {**result, 'archive': None}
        now = time.time()
        with self.personal.accounts.db() as db:
            stale = db.execute('SELECT id,path FROM archives WHERE username=? ORDER BY created DESC LIMIT -1 OFFSET ?',
                               (username, ARCHIVES_PER_USER - 1)).fetchall()
            for row in stale:
                db.execute('DELETE FROM archives WHERE id=?', (row['id'],))
                Path(row['path']).unlink(missing_ok=True)
            filename = time.strftime('cirdc-favorites-%Y%m%d-%H%M%S.zip', time.gmtime(now))
            db.execute('INSERT INTO archives VALUES(?,?,?,?,?,?)',
                       (archive_id, username, str(target), filename, now, now + ARCHIVE_SECONDS))
        return {**result, 'archive': {'id': archive_id, 'href': '/api/me/archives/' + archive_id,
                                      'expires': now + ARCHIVE_SECONDS}}

    def find(self, username, archive_id):
        if not re.fullmatch(r'[0-9a-f]{32}', archive_id):
            return None
        self.cleanup()
        with self.personal.accounts.db() as db:
            row = db.execute('SELECT * FROM archives WHERE id=? AND username=? AND expires>?',
                             (archive_id, username, time.time())).fetchone()
        return dict(row) if row and Path(row['path']).is_file() else None

    def discard(self, username, archive_id):
        row = self.find(username, archive_id)
        if not row:
            return False
        with self.personal.accounts.db() as db:
            db.execute('DELETE FROM archives WHERE id=?', (archive_id,))
        Path(row['path']).unlink(missing_ok=True)
        return True


def routes(personal, archives, response, body):
    """Routes under /api/me; the guard has already required a session, Origin and CSRF."""
    def user(request):
        return request.state.user['username']

    def settings(request):
        return response({'settings': personal.settings(user(request))})

    async def save_settings(request):
        try:
            value = await run_in_threadpool(personal.save_settings, user(request), await body(request))
        except (ValueError, TypeError):
            return response({'error': 'invalid_settings'}, 422)
        return response({'settings': value})

    async def favorites(request):
        if request.method == 'POST':
            try:
                data = await body(request)
                value = await run_in_threadpool(personal.add, user(request), data.get('items'))
            except LookupError:
                return response({'error': 'paper_not_found'}, 404)
            except (ValueError, TypeError):
                return response({'error': 'invalid_favorite'}, 422)
            return response(value)
        params = request.query_params
        try:
            cursor = int(params['cursor']) if params.get('cursor') else None
            value = await run_in_threadpool(personal.list, user(request), params.get('source') or None, cursor,
                                            int(params.get('limit', 25)))
        except (ValueError, TypeError):
            return response({'error': 'invalid_favorite_query'}, 422)
        return response(value)

    async def remove(request):
        try:
            data = await body(request)
            value = await run_in_threadpool(personal.remove, user(request), data.get('ids'))
        except (ValueError, TypeError):
            return response({'error': 'invalid_favorite'}, 422)
        return response(value)

    async def state(request):
        try:
            identities = personal.parse_keys(request.query_params.get('keys'))
        except ValueError:
            return response({'error': 'invalid_favorite'}, 422)
        return response(await run_in_threadpool(personal.state, user(request), identities))

    async def prepare(request):
        try:
            data = await body(request)
            value = await archives.prepare(user(request), data.get('ids'), data.get('filenames'))
        except OverflowError:
            return response({'error': 'too_many_archive_items', 'limit': ARCHIVE_LIMIT}, 422)
        except LookupError:
            return response({'error': 'favorite_not_found'}, 404)
        except (ValueError, TypeError):
            return response({'error': 'invalid_archive_request'}, 422)
        except Exception:
            return response({'error': 'archive_failed'}, 500)
        return response(value, 201 if value['archive'] else 200)

    async def archive(request):
        archive_id = request.path_params['archive_id']
        if request.method == 'DELETE':
            removed = await run_in_threadpool(archives.discard, user(request), archive_id)
            return response({'status': 'removed'} if removed else {'error': 'archive_expired'}, 200 if removed else 404)
        row = await run_in_threadpool(archives.find, user(request), archive_id)
        if not row:
            return response({'error': 'archive_expired'}, 404)
        return FileResponse(row['path'], media_type='application/zip', filename=row['filename'],
                            headers={'Cache-Control': 'private, no-store'})

    return [Route('/api/me/settings', settings, methods=['GET']),
            Route('/api/me/settings', save_settings, methods=['PUT']),
            Route('/api/me/favorites', favorites, methods=['GET', 'POST']),
            Route('/api/me/favorites/remove', remove, methods=['POST']),
            Route('/api/me/favorites/state', state, methods=['GET']),
            Route('/api/me/archives', prepare, methods=['POST']),
            Route('/api/me/archives/{archive_id}', archive, methods=['GET', 'DELETE'])]
