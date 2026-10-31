import json
import re
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from .auth import Accounts
from .access import authentication_required, SearchRateLimiter
from .index import metadata, publication_year_range, search, validate_year_range
from .settings import connect
from .resources import ResourceProviders
from .authors import author_references, find_authors, get_author, attach_author_references
from .venues import parse_venue_any, attach_series
from .. import __version__
from ..api import invoke
from ..store import Store


def response(value, status=200):
    return JSONResponse({'schema_version': 1, 'version': __version__, **value}, status_code=status,
                        headers={'Cache-Control': 'no-store'})


def create_app(config, interface='reader', resource_providers=None, reader_auth=None):
    if interface not in ('reader', 'admin'):
        raise ValueError('Invalid interface')
    requires_auth = authentication_required(interface, reader_auth)
    public_reader = interface == 'reader' and not requires_auth
    accounts = Accounts()
    resources = resource_providers if resource_providers is not None else ResourceProviders(config, interface)
    cookie = 'cirdc_' + interface
    pre_cookie = 'cirdc_pre_' + interface
    static = Path(__file__).parent / 'static'
    search_limit = SearchRateLimiter()

    class Guard(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            path = request.url.path
            if interface == 'reader' and (path.startswith('/admin') or path.startswith('/api/admin')):
                return response({'error': 'not_found'}, 404)
            if interface == 'admin' and request.url.hostname not in ('localhost', '127.0.0.1', '::1'):
                return response({'error': 'invalid_host'}, 400)
            try:
                method = getattr(resources, 'request_policy', None)
                policy = await run_in_threadpool(method, request) if method else None
            except Exception as error:
                status = getattr(error, 'status', 503)
                return response({'error': getattr(error, 'code', 'resource_unavailable')}, status)
            policy = policy or {}
            machine = policy.get('machine', False)
            if public_reader and path.startswith('/api/'):
                if path.startswith('/api/auth/') and path != '/api/auth/session':
                    return response({'error': 'not_found'}, 404)
                if request.method not in ('GET', 'HEAD') and not policy.get('write'):
                    result = response({'error': 'read_only'}, 405)
                    result.headers['Allow'] = 'GET, HEAD'
                    return result
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                origin = request.headers.get('origin')
                expected = str(request.base_url).rstrip('/')
                if not machine and (not origin or origin.rstrip('/') != expected):
                    return response({'error': 'origin_rejected'}, 403)
                length = request.headers.get('content-length', '0')
                if not length.isdigit() or int(length) > policy.get('body_limit', 32768):
                    return response({'error': 'request_too_large'}, 413)
            user = None if public_reader else await run_in_threadpool(accounts.session, request.cookies.get(cookie), interface)
            request.state.user = user
            request.state.public_reader = public_reader
            if path.startswith('/api/') and path not in ('/api/auth/session', '/api/auth/login'):
                if not user and not public_reader and not machine:
                    return response({'error': 'authentication_required'}, 401)
                if user and user['must_change'] and path not in ('/api/auth/password', '/api/auth/logout'):
                    return response({'error': 'password_change_required'}, 403)
                if interface == 'admin' and user['role'] != 'admin':
                    return response({'error': 'administrator_required'}, 403)
                if not public_reader and not machine and request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and not secrets.compare_digest(request.headers.get('x-csrf-token', ''), user['csrf']):
                    return response({'error': 'csrf_rejected'}, 403)
                if path == '/api/papers':
                    key = ('ip', request.client.host if request.client else 'unknown') if public_reader else ('account', user['username'])
                    if not search_limit.allow(key):
                        return response({'error': 'rate_limited'}, 429)
            try:
                result = await call_next(request)
            except Exception:
                return response({'error': 'service_unavailable', 'message': '服务暂时不可用，请稍后重试。'}, 503)
            if path in ('/assets/theme-init.js', '/assets/themes.css'):
                result.headers['Cache-Control'] = 'no-cache'
            result.headers['X-Content-Type-Options'] = 'nosniff'
            result.headers['Referrer-Policy'] = 'same-origin'
            result.headers.setdefault('X-Frame-Options', 'DENY')
            result.headers.setdefault('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
            return result

    async def session(request):
        if public_reader:
            return response({'user': None, 'csrf': '', 'interface': interface,
                             'authentication_required': False, 'access_mode': 'public'})
        user = request.state.user
        csrf = user['csrf'] if user else secrets.token_urlsafe(32)
        result = response({'user': user, 'csrf': csrf, 'interface': interface,
                           'authentication_required': True, 'access_mode': 'required'})
        if not user:
            result.set_cookie(pre_cookie, csrf, httponly=True, samesite='strict', max_age=3600)
        return result

    async def body(request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 32768:
                raise ValueError('Request too large')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('Expected an object')
        return data

    async def login(request):
        if not secrets.compare_digest(request.cookies.get(pre_cookie, ''), request.headers.get('x-csrf-token', '')) or not request.cookies.get(pre_cookie):
            return response({'error': 'csrf_rejected'}, 403)
        try:
            data = await body(request)
            token, user = await run_in_threadpool(accounts.login, data.get('username'), data.get('password'),
                                                  interface, request.client.host if request.client else '')
        except PermissionError:
            return response({'error': 'login_throttled', 'message': '尝试过多，请 15 分钟后重试。'}, 429)
        except (ValueError, KeyError, TypeError):
            return response({'error': 'invalid_credentials', 'message': '用户名或密码不正确。'}, 401)
        result = response({'user': user, 'csrf': user['csrf']})
        result.set_cookie(cookie, token, httponly=True, samesite='strict', max_age=3600 if interface == 'admin' else 28800)
        result.delete_cookie(pre_cookie)
        return result

    def logout(request):
        accounts.logout(request.cookies.get(cookie, ''))
        result = response({'status': 'signed_out'})
        result.delete_cookie(cookie)
        return result

    async def password(request):
        try:
            data = await body(request)
            await run_in_threadpool(accounts.change, request.state.user['username'], data.get('current_password'), data.get('new_password'))
        except (ValueError, TypeError):
            return response({'error': 'invalid_password', 'message': '请核对当前密码，新密码至少 8 个字符且不能与原密码相同。'}, 422)
        result = response({'status': 'password_changed'})
        result.delete_cookie(cookie)
        return result

    def papers(request):
        try:
            years = validate_year_range(request.query_params)
        except (ValueError, TypeError):
            return response({'error': 'invalid_query', 'message': '年份范围无效，请确保起始年份不晚于结束年份。'}, 422)
        try:
            venue_any = parse_venue_any(request.query_params.get('venue_any'))
        except ValueError:
            return response({'error': 'invalid_query', 'message': '刊会编号参数无效，最多支持 32 个编号。'}, 422)
        query = request.query_params.get('q', '').strip()
        if len(query) > 200:
            return response({'error': 'invalid_query', 'message': '搜索词最多 200 个字符。'}, 422)
        if query.isdigit() and request.query_params.get('field') != 'authors' and not request.query_params.get('author_id'):
            with closing(Store(config)) as store:
                rows = store.execute('SELECT * FROM papers WHERE number=%s', (query,))
            if rows:
                from .index import project
                p = project(rows[0])
                keys = ['number', 'doi', 'title', 'authors', 'keywords', 'abstract', 'year', 'kind', 'venue',
                        'publication', 'abstract_state', 'keywords_state', 'updated', 'order_number']
                item = dict(zip(keys, p))
                item['snippet'] = item.pop('abstract')[:400]
                attach_series([item])
                if venue_any and not set(venue_any).intersection([item['venue'], *item['venue_series']]):
                    return response({'items': [], 'next_cursor': None, 'direct': True, 'partial': False})
                for name in ['kind', 'venue', 'abstract_state', 'keywords_state']:
                    value = request.query_params.get(name)
                    if name == 'kind' and value == 'Journals' and item[name] in ('Early Access Articles', 'Magazines'):
                        continue
                    if name == 'venue' and value and value != str(item[name]):
                        with closing(connect('search.sqlite')) as index_db:
                            matches = index_db.execute('SELECT 1 FROM venue_members WHERE series=? AND member=? AND kind=?',
                                                       (value, str(item[name]), item['kind'])).fetchone()
                        if matches:
                            continue
                    if value and value != str(item[name]):
                        return response({'items': [], 'next_cursor': None, 'direct': True, 'partial': False})
                for name, before in [('year_from', True), ('year_to', False)]:
                    if name in years:
                        if (before and item['year'] < years[name]) or (not before and item['year'] > years[name]):
                            return response({'items': [], 'next_cursor': None, 'direct': True, 'partial': False})
                raw = rows[0]['data']
                item['author_refs'] = author_references(json.loads(raw) if isinstance(raw, str) else raw)
                resources.attach([item])
                return response({'items': [item], 'next_cursor': None, 'direct': True, 'partial': False})
        try:
            value = search(dict(request.query_params))
            attach_series(value['items'])
            attach_author_references(value['items'])
            resources.attach(value['items'])
            return response(value)
        except (ValueError, TypeError):
            return response({'error': 'invalid_query', 'message': '查询参数无效，请检查搜索词、年份或翻页链接。'}, 422)
        except sqlite3.OperationalError:
            return response({'error': 'search_busy', 'message': '检索超时或索引繁忙，请缩小范围后重试。'}, 503)

    def paper(request):
        number = request.path_params['number']
        if not re.fullmatch(r'[0-9]{1,64}', number):
            return response({'error': 'invalid_number'}, 422)
        with closing(Store(config)) as store:
            rows = store.execute('SELECT * FROM papers WHERE number=%s', (number,))
        if not rows:
            return response({'error': 'not_found'}, 404)
        item = rows[0]
        item['record'] = json.loads(item.pop('data'))
        item.pop('pdf_path', None)  # Filesystem locations stay on the server.
        item['updated_at'] = str(item['updated_at'])
        item['author_refs'] = author_references(item['record'])
        attach_series([item])
        resources.attach([item])
        return response({'paper': item, 'read_at': datetime.now(timezone.utc).isoformat()})

    venues_cache = {'at': 0, 'value': []}

    def venues(request):
        if time.monotonic() - venues_cache['at'] > 60:
            with closing(Store(config)) as store:
                rows = store.execute('SELECT kind,number,data FROM venues ORDER BY kind,number')
            values = []
            for row in rows:
                data = json.loads(row['data'])
                values.append({'kind': row['kind'], 'number': row['number'], 'title': str(data.get('title') or data.get('parentTitle') or data.get('publicationTitle') or row['number'])})
            venues_cache.update(at=time.monotonic(), value=values)
        return response({'items': venues_cache['value']})

    def overview(request):
        with closing(connect('search.sqlite')) as db:
            value = {**metadata(db), 'year_range': publication_year_range(db)}
        summary = value.get('overview')
        method = getattr(resources, 'coverage', None)
        coverage = method() if callable(method) else []
        if isinstance(summary, dict) and coverage:
            value = {**value, 'overview': {**summary, 'resource_coverage': coverage}}
        return response({'index': value, 'overview': value.get('overview'), 'interface': interface})

    def authors(request):
        try:
            return response(find_authors(dict(request.query_params)))
        except (ValueError, TypeError):
            return response({'error': 'invalid_author_query', 'message': '请输入作者姓名或 IEEE 作者 ID。'}, 422)
        except sqlite3.OperationalError:
            return response({'error': 'author_index_busy', 'message': '作者索引准备中或查询繁忙，请稍后重试。'}, 503)

    def author(request):
        try:
            value = get_author(request.path_params['source'], request.path_params['author_id'])
        except ValueError:
            return response({'error': 'invalid_author_reference'}, 422)
        return response({'author': value}, 200 if value else 404)

    def author_profile(request):
        from ..author_profiles import AuthorError, AuthorRepository, identity
        source, aid = request.path_params['source'], request.path_params['author_id']
        try:
            identity(aid, source)
        except AuthorError:
            return response({'error': 'invalid_author_reference'}, 422)
        with closing(Store(config)) as store:
            value = AuthorRepository(store, config.state_dir).show(aid, public=True)
        return response({'status': 'ready' if value else 'not_fetched', 'author': value})

    def shell(request):
        if not (static / 'index.html').exists():
            return response({'error': 'frontend_not_built'}, 503)
        return FileResponse(static / 'index.html', headers={'Cache-Control': 'no-store'})

    def health(request):
        return response({'status': 'ok', 'interface': interface})

    routes = [Route('/healthz', health), Route('/api/auth/session', session),
              Route('/api/auth/login', login, methods=['POST']),
              Route('/api/auth/logout', logout, methods=['POST']),
              Route('/api/auth/password', password, methods=['POST'])]
    if interface == 'reader':
        routes += [Route('/api/papers', papers), Route('/api/papers/{number}', paper),
                   Route('/api/venues', venues), Route('/api/overview', overview),
                   Route('/api/author-profiles/{source}/{author_id}', author_profile),
                   Route('/api/authors', authors), Route('/api/authors/{source}/{author_id}', author)]
        routes += resources.routes()
    else:
        def runs(request):
            with closing(Store(config)) as store:
                values = store.execute('SELECT id,status,params,error,heartbeat,created_at FROM runs ORDER BY created_at DESC,id DESC LIMIT 50')
            for value in values:
                value['params'] = json.loads(value['params'])
                for name in ['heartbeat', 'created_at']:
                    value[name] = str(value[name])
            return response({'items': values})

        def run_status(request):
            value = invoke('status', config, run_id=request.path_params['run_id'])
            return response(value)

        def logs(request):
            run_id = request.path_params['run_id']
            if not re.fullmatch(r'[0-9a-f]{32}', run_id):
                return response({'error': 'invalid_job'}, 422)
            path = config.state_dir / 'logs' / (run_id + '.log')
            content = ''
            if path.is_file():
                with path.open('rb') as stream:
                    stream.seek(max(0, path.stat().st_size - 65536))
                    content = stream.read(65536).decode('utf-8', errors='replace')
            for key in ['password', 'user']:
                secret = config.mysql.get(key)
                if secret:
                    content = content.replace(str(secret), '[redacted]')
            return response({'log': content})

        async def operation(request):
            action = request.path_params['action']
            if action not in ('doctor', 'plan', 'update', 'resume', 'retry'):
                return response({'error': 'not_found'}, 404)
            try:
                data = await body(request)
                params = {}
                if action in ('plan', 'update'):
                    params['stage'] = data.get('stage', 'all')
                    if params['stage'] not in ('all', 'catalog', 'metadata', 'enrich'):
                        raise ValueError()
                    if data.get('publication'):
                        if not re.fullmatch(r'[0-9]{1,64}', str(data['publication'])):
                            raise ValueError()
                        params['publication'] = str(data['publication'])
                    if data.get('year'):
                        params['year'] = int(data['year'])
                        if not 1800 <= params['year'] <= 2200:
                            raise ValueError()
                if action in ('resume', 'retry'):
                    if not re.fullmatch(r'[0-9a-f]{32}', str(data.get('run_id', ''))):
                        raise ValueError()
                    params['run_id'] = data['run_id']
                if action in ('update', 'resume', 'retry'):
                    preflight = await run_in_threadpool(invoke, 'doctor', config)
                    if preflight.get('status') != 'ready':
                        return response({'error': 'preflight_failed', 'message': '数据库或元数据目录尚未就绪，请先检查服务预检。'}, 503)
                value = await run_in_threadpool(invoke, action, config, **params)
            except (ValueError, TypeError):
                return response({'error': 'invalid_parameters'}, 422)
            await run_in_threadpool(accounts.audit, request.state.user['username'], action,
                                    value.get('run_id', params.get('run_id', '')), json.dumps(params))
            return response(value, 409 if value.get('status') == 'error' else 202 if action in ('update', 'resume', 'retry') else 200)

        def resource_settings(request):
            return response({'items': resources.settings()})

        async def configure_resource(request):
            try:
                values = await body(request)
                value = await run_in_threadpool(resources.configure, request.path_params['identifier'], values)
            except (ValueError, OSError, RuntimeError):
                return response({'error': 'invalid_resource_configuration',
                                 'message': '存储根目录不可用或扫描正在运行，请检查路径和挂载状态。'}, 422)
            await run_in_threadpool(accounts.audit, request.state.user['username'], 'resource_configure',
                                    request.path_params['identifier'], 'storage configuration updated')
            return response({'status': 'saved', 'item': value})

        def users(request):
            return response({'items': accounts.list()})

        def audit(request):
            return response({'items': accounts.events()})

        async def user_action(request):
            try:
                data = await body(request)
                name = data.get('username')
                actor = request.state.user['username']
                action = request.path_params['action']
                if action == 'create':
                    await run_in_threadpool(accounts.create, name, data.get('password', ''), 'reader', actor)
                elif action == 'reset':
                    await run_in_threadpool(accounts.reset, name, data.get('password', ''), True, actor)
                elif action == 'active':
                    if not isinstance(data.get('active'), bool):
                        raise ValueError()
                    await run_in_threadpool(accounts.disable, name, data['active'], actor)
                else:
                    return response({'error': 'not_found'}, 404)
            except (ValueError, TypeError):
                return response({'error': 'invalid_account_action', 'message': '账户操作无效，请检查用户名或密码。'}, 422)
            return response({'status': 'ok'})

        routes += [Route('/api/admin/runs', runs), Route('/api/admin/runs/{run_id}/logs', logs),
                   Route('/api/admin/runs/{run_id}', run_status), Route('/api/admin/actions/{action}', operation, methods=['POST']),
                   Route('/api/admin/users', users), Route('/api/admin/users/{action}', user_action, methods=['POST']),
                   Route('/api/admin/audit', audit), Route('/api/admin/overview', overview),
                   Route('/api/admin/resources', resource_settings),
                   Route('/api/admin/resources/{identifier}', configure_resource, methods=['POST'])]
    if static.exists():
        routes.append(Mount('/assets', StaticFiles(directory=static / 'assets'), name='assets'))
    routes += [Route('/', shell), Route('/login', shell), Route('/papers/{number}', shell)]
    if interface == 'reader':
        routes.append(Route('/authors/{source}/{author_id}', shell))
    if interface == 'admin':
        routes.append(Route('/admin/', shell))
    app = Starlette(routes=routes)
    app.add_middleware(Guard)
    app.state.accounts = accounts
    app.state.resources = resources
    return app
