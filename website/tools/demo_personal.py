"""Offline demo extensions: isolated accounts, favorites and archives, and an administrator test adapter.

Everything here is test scaffolding for the offline demo. Accounts live in the demo's own state folder; PDFs
generated below are labelled test material and are never presented as the papers themselves; the
administrator adapter answers from fixtures and cannot start, resume or retry real jobs.
"""
import json
import os
import secrets
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from cirdc.web.account_api import admin_account_routes, auth_routes
from cirdc.web.auth import Accounts
from cirdc.web.personal import Archives, Directory, Personal
from cirdc.web.personal import routes as personal_routes

# Which favorites the local test cache can package: IEEE numbers and (arXiv paper ID, version).
TEST_IEEE = ('11741266', '11126195')
TEST_ARXIV = (('1', 1), ('1', 2), ('3112709', 2))
REAL_PDF = ('3300802', 1)
WRITES = ('POST', 'PUT', 'PATCH', 'DELETE')


def response(value, status=200):
    return JSONResponse(value, status_code=status, headers={'Cache-Control': 'no-store'})


async def body(request):
    raw = await request.body()
    if len(raw) > 32768:
        raise ValueError('Request too large')
    data = json.loads(raw or b'{}')
    if not isinstance(data, dict):
        raise ValueError('Expected an object')
    return data


def test_pdf(label):
    """A minimal one-page PDF whose only text says it is demo test material."""
    text = f'CIRDC offline demo TEST MATERIAL - not the paper. {label}'.replace('(', '[').replace(')', ']')
    stream = f'BT /F1 12 Tf 48 760 Td ({text}) Tj ET'.encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
               b'/Resources << /Font << /F1 5 0 R >> >> >>',
               b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    output, offsets = bytearray(b'%PDF-1.4\n'), []
    for number, value in enumerate(objects, 1):
        offsets.append(len(output))
        output += f'{number} 0 obj\n'.encode() + value + b'\nendobj\n'
    start = len(output)
    output += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    output += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    output += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()
    return bytes(output)


def prepare_test_pdfs(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for number in TEST_IEEE:
        (folder / f'ieee-{number}.pdf').write_bytes(test_pdf(f'IEEE {number}'))
    for paper_id, version in TEST_ARXIV:
        (folder / f'arxiv-{paper_id}-v{version}.pdf').write_bytes(test_pdf(f'arXiv internal {paper_id} v{version}'))
    return folder


class DemoDirectory(Directory):
    def __init__(self, ieee, catalog):
        self.ieee_papers, self.catalog = ieee, catalog

    def ieee(self, numbers):
        result = {}
        for number in numbers:
            paper = self.ieee_papers.get(number)
            if paper:
                year = str(paper['record'].get('publicationYear', ''))
                result[number] = {'title': paper['record'].get('articleTitle', ''), 'year': int(year) if year.isdigit() else None}
        return result

    def arxiv(self, paper_id):
        return self.catalog.paper(paper_id=paper_id)

    def pdf_route(self, source, paper_id, version):
        if (source, paper_id, version) == ('arxiv', *REAL_PDF):
            return f'/api/arxiv/papers/{paper_id}/versions/{version}/files/pdf'
        if source == 'arxiv':
            return f'/api/demo-test-cache/arxiv/{paper_id}/v{version}.pdf'
        return f'/api/demo-test-cache/ieee/{paper_id}.pdf'


def test_cache_routes(folder):
    def missing():
        return response({'error': 'demo_resource_not_packaged', 'demo': True}, 404)

    def ieee(request):
        number = str(request.path_params['number'])
        return FileResponse(folder / f'ieee-{number}.pdf', media_type='application/pdf') if number in TEST_IEEE else missing()

    def arxiv(request):
        key = (str(request.path_params['paper_id']), request.path_params['version'])
        path = folder / f'arxiv-{key[0]}-v{key[1]}.pdf'
        return FileResponse(path, media_type='application/pdf') if key in TEST_ARXIV else missing()

    return [Route('/api/demo-test-cache/ieee/{number:int}.pdf', ieee),
            Route('/api/demo-test-cache/arxiv/{paper_id:int}/v{version:int}.pdf', arxiv)]


class PersonalGuard(BaseHTTPMiddleware):
    """The site's session rules for personal routes: Origin and CSRF on writes, sign-in for /api/me."""

    def __init__(self, app, accounts, interface):
        super().__init__(app)
        self.accounts, self.interface = accounts, interface

    async def dispatch(self, request, call_next):
        path = request.url.path
        token = request.cookies.get('cirdc_' + self.interface)
        user = self.accounts.session(token, self.interface) if token else None
        request.state.user = user
        personal = path.startswith(('/api/me/', '/api/auth/', '/api/admin/'))
        if request.method in WRITES and personal:
            if (request.headers.get('origin') or '').rstrip('/') != str(request.base_url).rstrip('/'):
                return response({'error': 'origin_rejected'}, 403)
            exempt = path in ('/api/auth/login', '/api/auth/register', '/api/auth/logout')
            if user and not exempt and not secrets.compare_digest(request.headers.get('x-csrf-token', ''), user['csrf']):
                return response({'error': 'csrf_rejected'}, 403)
        if path.startswith(('/api/me/', '/api/admin/')) and not user:
            return response({'error': 'authentication_required'}, 401)
        if user and user['must_change'] and path.startswith(('/api/me/', '/api/admin/')):
            return response({'error': 'password_change_required'}, 403)
        if self.interface == 'admin' and path.startswith('/api/admin/') and user['role'] != 'admin':
            return response({'error': 'administrator_required'}, 403)
        return await call_next(request)


def personal_extension(state, seed, catalog):
    """Accounts (isolated state folder), favorites, archives and the test cache for the reader demo."""
    os.environ['CIRDC_WEB_STATE'] = str(state)
    accounts = Accounts()
    folder = prepare_test_pdfs(Path(state) / 'test-pdfs')
    personal = Personal(accounts, DemoDirectory({p['number']: p for p in seed['ieee']}, catalog))
    holder = {}
    routes = [*auth_routes(accounts, 'reader', True, True, response, body),
              *personal_routes(personal, Archives(personal, lambda: holder['app']), response, body),
              *test_cache_routes(folder)]
    return accounts, routes, holder


# Administrator test adapter ------------------------------------------------------------------------
def admin_fixtures(scenario):
    now = time.time()
    if scenario == 'empty':
        return {'runs': [], 'details': {}, 'maintenance': {'service': None, 'pending_results': None, 'jobs': {}, 'workers': [], 'exits': []},
                'resources': [], 'overview': {'phase': 'ready', 'indexed': 0, 'overview': {'papers': 0, 'field_states': [], 'venues': []}}}
    runs = [('9' * 32, 'running', 'metadata', None), ('8' * 32, 'failed', 'enrich', 'catalog_unavailable'),
            ('7' * 32, 'completed', 'catalog', None)]
    details = {}
    for index, (run_id, status, stage, error) in enumerate(runs):
        details[run_id] = {
            'id': run_id, 'status': status, 'observed_status': status, 'params': {'stage': stage},
            'heartbeat': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now - 30 - index * 3600)),
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now - 7200 - index * 86400)),
            'counts': {'done': 1200 - index * 300, 'pending': 0 if status == 'completed' else 180, 'failed': 3 if status == 'failed' else 0,
                       'blocked': 2 if status == 'failed' else 0, 'deferred': 1},
            'stats': {'imported': 1200 - index * 300, 'fetched': 1180 - index * 300},
            'errors': [{'kind': stage, 'task_key': 'demo-task-41', 'status': 'failed', 'error': 'temporary_http_error'},
                       {'kind': stage, 'task_key': 'demo-task-57', 'status': 'blocked', 'error': 'access_challenge'}] if status == 'failed' else [],
            'deferred': [{'task_key': 'demo-future-year', 'reason': 'future_catalog_year'}],
            'error': error,
        }
    return {
        'runs': [{'id': d['id'], 'status': d['status'], 'params': d['params'], 'error': d['error'],
                  'heartbeat': d['heartbeat'], 'created_at': d['created_at']} for d in details.values()],
        'details': details,
        'maintenance': {'service': 'isolated test adapter', 'pending_results': 4,
                        'jobs': {'metadata': {'counts': {'done': 960, 'pending': 180, 'failed': 3, 'blocked': 2, 'exports_pending': 4}}},
                        'workers': [{'id': 'demo-worker-a', 'last_seen': now - 40}], 'exits': [{'requests': 12}]},
        'resources': [{'id': 'demo-test-cache', 'title': 'Demo test cache', 'description': 'Isolated test adapter; saving changes only this process.',
                       'root_dir': '/srv/cirdc-demo-test-cache',
                       'diagnostics': {'nodes': [], 'jobs': [], 'counts': {'ready': 6, 'missing': 2},
                                       'pdf_acquisition_counts': {'ready': 6, 'blocked': 1},
                                       'pdf_todos': [{'number': '11717827', 'reason': 'institution_not_licensed', 'updated': now - 600, 'attempts': 1}],
                                       'pdf_todo_counts': {'blocked': 1}}}],
        'overview': {'phase': 'ready', 'indexed': 3, 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
                     'overview': {'papers': 3, 'sampled_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
                                  'field_states': [{'abstract_state': 'complete', 'keywords_state': 'complete', 'n': 3}],
                                  'venues': [{'kind': 'Journals', 'n': 2}, {'kind': 'Conferences', 'n': 1}]}},
    }


def create_admin_demo(state, scenario='mixed', static=None):
    """Administrator workspace over fixtures; accounts and audit are the real implementation on the demo store."""
    os.environ['CIRDC_WEB_STATE'] = str(state)
    accounts = Accounts()
    data = admin_fixtures(scenario)
    actions = []

    def adapter(value, status=200):
        return response({**value, 'demo_adapter': True}, status)

    def runs(request):
        return adapter({'items': data['runs']})

    def run(request):
        value = data['details'].get(request.path_params['run_id'])
        return adapter(value) if value else adapter({'error': 'not_found'}, 404)

    def logs(request):
        if request.path_params['run_id'] not in data['details']:
            return adapter({'error': 'not_found'}, 404)
        return adapter({'log': 'isolated test adapter: no worker process is running\n'})

    async def operation(request):
        action = request.path_params['action']
        if action not in ('doctor', 'plan', 'update', 'resume', 'retry'):
            return adapter({'error': 'not_found'}, 404)
        params = await body(request)
        actions.append({'action': action, 'params': params, 'at': time.time()})
        accounts.audit(request.state.user['username'], action, params.get('run_id', ''), 'isolated test adapter')
        if action == 'doctor':
            return adapter({'status': 'ready', 'checks': {'database': 'test adapter', 'metadata_directory': 'test adapter'}})
        if action == 'plan':
            return adapter({'journals': 0 if scenario == 'empty' else 12, 'conference_series': 0 if scenario == 'empty' else 5,
                            'existing_article_files': 0 if scenario == 'empty' else 1200})
        return adapter({'status': 'accepted', 'run_id': params.get('run_id') or secrets.token_hex(16),
                        'note': 'recorded by the isolated test adapter; no job was started'}, 202)

    async def configure(request):
        values = await body(request)
        item = next((r for r in data['resources'] if r['id'] == request.path_params['identifier']), None)
        if not item or not str(values.get('root_dir', '')).startswith('/'):
            return adapter({'error': 'invalid_resource_configuration'}, 422)
        item['root_dir'] = values['root_dir']
        return adapter({'status': 'saved', 'item': item})

    def shell(request):
        return HTMLResponse((static / 'index.html').read_text().replace(
            '<body>', '<body><aside class="hint" role="status">Offline demo · administrator test adapter '
                      f'({scenario}) · no jobs are started</aside>'))

    routes = [*auth_routes(accounts, 'admin', False, False, response, body),
              *admin_account_routes(accounts, response, body),
              Route('/api/admin/runs', runs), Route('/api/admin/runs/{run_id}', run), Route('/api/admin/runs/{run_id}/logs', logs),
              Route('/api/admin/actions/{action}', operation, methods=['POST']),
              Route('/api/admin/overview', lambda request: adapter({'index': data['overview'], 'overview': data['overview']['overview'], 'interface': 'admin'})),
              Route('/api/admin/maintenance', lambda request: adapter(data['maintenance'])),
              Route('/api/admin/resources', lambda request: adapter({'items': data['resources']})),
              Route('/api/admin/resources/{identifier}', configure, methods=['POST']),
              Route('/api/admin/resource-requests', lambda request: adapter({'requests': [], 'counts': {}})),
              Route('/api/demo/admin-actions', lambda request: adapter({'items': actions})),
              Mount('/assets', StaticFiles(directory=static / 'assets')),
              Route('/admin/', shell), Route('/login', shell), Route('/', shell)]
    app = Starlette(routes=routes)
    app.add_middleware(PersonalGuard, accounts=accounts, interface='admin')
    password = secrets.token_urlsafe(12)
    if accounts.create('demo-admin', password, 'admin'):
        accounts.reset('demo-admin', password, must_change=False, actor='demo-bootstrap')
        credentials = Path(state) / 'admin-credentials.txt'
        credentials.write_text(f'username: demo-admin\npassword: {password}\n')
        credentials.chmod(0o600)
    app.state.accounts = accounts
    return app
