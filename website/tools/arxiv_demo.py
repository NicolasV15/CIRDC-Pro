"""Offline real-data demo. Never imports configuration or connects to source services."""
import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE / 'src'))
from cirdc.web.arxiv import Catalog
from cirdc.web.arxiv import routes as catalog_routes

# Load the existing index implementation under a demo-only module identity, so its
# local connection adapter cannot alter other applications or test modules.
_index_spec = importlib.util.spec_from_file_location('cirdc.web._offline_demo_index',
                                                     SITE / 'src/cirdc/web/index.py')
index = importlib.util.module_from_spec(_index_spec)
_index_spec.loader.exec_module(index)
from starlette.applications import Starlette
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

DATA = SITE / 'demo' / 'arxiv'
IDENTITY = 'cirdc-arxiv-offline-demo-v1'


def connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def verified_inputs(data=DATA):
    manifest = json.loads((data / 'manifest.json').read_text())
    content = (data / 'metadata.json').read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest['metadata_sha256']:
        raise ValueError('demo_metadata_digest_mismatch')
    for entry in manifest['files']:
        path = (data / entry['file']).resolve()
        if not path.is_relative_to(data.resolve()):
            raise ValueError('demo_file_outside_bundle')
        raw = path.read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('demo_file_digest_mismatch: ' + entry['file'])
    return json.loads(content), manifest


def prepare(database, data=DATA, rebuild=False):
    """Atomically seed a small local SQLite DB; refuse replacement of unrelated files."""
    seed, _manifest = verified_inputs(data)
    fingerprint = hashlib.sha256((data / 'manifest.json').read_bytes()).hexdigest()
    database = Path(database).resolve()
    if database.exists():
        with closing(connect(database)) as db:
            identity = db.execute('SELECT database_id,seed_digest FROM demo_identity').fetchone()
        if not identity or identity['database_id'] != IDENTITY:
            raise ValueError('not_a_demo_database')
        if not rebuild:
            if identity['seed_digest'] != fingerprint:
                raise ValueError('demo_seed_changed: restart with --rebuild')
            return database
    database.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.arxiv-demo-', suffix='.sqlite', dir=database.parent)
    os.close(fd)
    try:
        with closing(sqlite3.connect(temporary)) as db:
            db.row_factory = sqlite3.Row
            db.executescript('''
                CREATE TABLE demo_identity(database_id TEXT,seed_digest TEXT);
                CREATE TABLE identity(database_id TEXT);
                CREATE TABLE papers(id INTEGER PRIMARY KEY,arxiv_id TEXT UNIQUE,payload TEXT);
                CREATE TABLE ieee(number TEXT PRIMARY KEY,payload TEXT);
                CREATE VIRTUAL TABLE metadata USING fts5(arxiv_id UNINDEXED,title,authors,abstract,categories);
            ''')
            db.execute('INSERT INTO demo_identity VALUES (?,?)', (IDENTITY, fingerprint))
            db.execute('INSERT INTO identity VALUES (?)', (IDENTITY,))
            for paper in seed['arxiv']:
                pid = int(paper['paper_id'])
                db.execute('INSERT INTO papers VALUES (?,?,?)', (pid, paper['arxiv_id'], json.dumps(paper)))
                db.execute('INSERT INTO metadata(rowid,arxiv_id,title,authors,abstract,categories) VALUES (?,?,?,?,?,?)',
                           (pid, paper['arxiv_id'], paper['title'], paper['authors_raw'], paper['abstract'],
                            ' '.join(paper['metadata'].get('categories', []))))
            for paper in seed['ieee']:
                db.execute('INSERT INTO ieee VALUES (?,?)', (paper['number'], json.dumps(paper)))
            index.initialize(db)
            index.put_rows(db, [{**paper, 'data': paper['record']} for paper in seed['ieee']])
            index.save_meta(db, phase='ready', authors_phase='ready', indexed=len(seed['ieee']),
                            checked_at=datetime.now(timezone.utc).isoformat())
            db.commit()
        os.replace(temporary, database)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return database


class DemoCatalog(Catalog):
    def __init__(self, database):
        self.database = database
        self.config = {'database_id': IDENTITY, 'index_path': str(database)}

    def paper(self, paper_id=None, arxiv_id=None):
        column, key = ('id', paper_id) if paper_id is not None else ('arxiv_id', arxiv_id)
        with closing(connect(self.database)) as db:
            row = db.execute('SELECT payload FROM papers WHERE ' + column + '=?', (key,)).fetchone()
        return json.loads(row['payload']) if row else None

    def overview(self):
        with closing(connect(self.database)) as db:
            years = [int(item['year']) for item in self.search('', limit=100)['items']]
            count = db.execute('SELECT count(*) FROM papers').fetchone()[0]
        return {'scope': 'metadata', 'indexed': count, 'year_range': {'min': min(years), 'max': max(years)},
                'demo': True}


def file_key(url):
    parsed = urlsplit(url)
    return parsed.path + ('?' + urlencode(sorted((k, v) for k, v in parse_qsl(parsed.query)
                                                if k != 'asset_revision')) if parsed.query else '')


def create_demo(database, data=DATA, state=None):
    seed, manifest = verified_inputs(data)
    catalog = DemoCatalog(database)
    # Accounts, favorites and archives use the real implementation on a store inside the demo work folder.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from demo_personal import PersonalGuard, personal_extension
    accounts, personal_routes, holder = personal_extension(state or Path(database).parent / 'state', seed, catalog)
    files = {file_key(entry['url']): entry for entry in manifest['files']}
    sample = manifest['reading_sample']
    sample_base = f"/api/arxiv/papers/{sample['paper_id']}/versions/{sample['version']}"
    # Only this standalone process uses the subset index. No application configuration is loaded.
    index.connect = lambda name: connect(database)
    ieee = {p['number']: p for p in seed['ieee']}

    def missing(code='demo_resource_not_packaged', status=404):
        return JSONResponse({'error': code, 'demo': True,
                             'message': 'Offline demo: not included in this bundle; not evidence of source absence.'},
                            status_code=status)

    async def api(request):
        path = request.url.path
        if request.method not in ('GET', 'HEAD'):
            return missing('demo_acquisition_disabled', 409)
        if path == '/api/demo':
            return JSONResponse({'offline': True, 'arxiv': len(seed['arxiv']), 'ieee': len(ieee),
                                 'reading': sample, 'missing_assets': manifest.get('missing_assets', []),
                                 'source_commit': seed['base_commit']})
        entry = files.get(file_key(str(request.url)))
        if entry:
            return FileResponse(data / entry['file'], media_type=entry['media_type'],
                                filename=Path(entry['file']).name if entry.get('attachment') else None)
        if path in (sample_base + '/resources', sample_base + '/document'):
            return JSONResponse(manifest['resources' if path.endswith('/resources') else 'document'])
        import re
        match = re.fullmatch(r'/api/arxiv/papers/(\d+)/versions/(\d+)/(resources|document)', path)
        if match:
            paper = catalog.paper(paper_id=match[1])
            if not paper or int(match[2]) not in [v['version'] for v in paper['versions']]:
                return missing('paper_or_version_not_found')
            if match[3] == 'document':
                return missing()
            return JSONResponse({'state': 'demo_snapshot', 'paper_version': int(match[2]),
                                 'resources': {k: {'state': 'not_packaged'} for k in ('html', 'pdf', 'source')},
                                 'reading_state': 'not_packaged', 'reading_ready': False,
                                 'acquisition_complete': False, 'demo': True})
        if path == '/api/papers':
            if request.query_params.get('field') == 'body':
                return missing('demo_ieee_body_index_not_packaged', 409)
            try:
                result = index._search_uncached(dict(request.query_params))
            except ValueError:
                return JSONResponse({'error': 'invalid_query'}, status_code=422)
            result.update(demo=True, partial=False)
            return JSONResponse(result)
        if path == '/api/overview':
            kinds = Counter(p['record'].get('articleContentType') for p in ieee.values())
            # Actual sample sizes, never production counts or invented resource coverage.
            return JSONResponse({'index': {'indexed': len(ieee), 'phase': 'ready',
                'overview': {'papers': len(ieee), 'field_states': [], 'sampled_at': seed['captured_at'],
                             'venues': [{'kind': kind, 'n': len({p['record'].get('publicationNumber')
                                         for p in ieee.values() if p['record'].get('articleContentType') == kind})}
                                        for kind in kinds]}}})
        if path == '/api/venues':
            venues = {(str(p['record'].get('publicationNumber', '')), p['record'].get('publicationTitle', ''),
                       p['record'].get('articleContentType', '')) for p in ieee.values()}
            return JSONResponse({'items': [{'number': n, 'title': t, 'kind': k} for n, t, k in sorted(venues)]})
        if path.startswith('/api/papers/') and path.rsplit('/', 1)[-1] in ieee:
            return JSONResponse({'paper': {**ieee[path.rsplit('/', 1)[-1]], 'resources': [],
                                          'demo': {'fulltext': 'not_packaged'}}})
        return missing('demo_route_not_packaged')

    async def page(request):
        raw = (SITE / 'src/cirdc/web/static/index.html').read_text()
        banner = f'<aside class="hint" role="status">Offline real-data Demo · arXiv {len(seed["arxiv"])} / IEEE {len(ieee)} · No acquisition · '
        banner += '<a href="/?source=arxiv">arXiv</a> · <a href="/api/demo">Dataset / limitations</a></aside>'
        return HTMLResponse(raw.replace('<body>', '<body>' + banner))

    app = Starlette(routes=[*catalog_routes(catalog), *personal_routes, Route('/api/{path:path}', api,
                      methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE']),
                      Route('/healthz', lambda request: JSONResponse({'status': 'ok', 'demo': True})),
                      # StaticFiles must precede the SPA fallback so missing assets return 404.
                      ])
    from starlette.routing import Mount
    app.routes.append(Mount('/assets', StaticFiles(directory=SITE / 'src/cirdc/web/static/assets')))
    app.routes.append(Route('/{path:path}', page))
    app.add_middleware(PersonalGuard, accounts=accounts, interface='reader')
    holder['app'] = app
    app.state.accounts = accounts
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18090)
    parser.add_argument('--rebuild', action='store_true', help='replace only this demo database from the checked seed')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--state', type=Path, default=SITE.parent / 'work/arxiv-demo/state',
                        help='isolated accounts, favorites and archives for this demo only')
    parser.add_argument('--admin-port', type=int, help='also serve the administrator workspace over a test adapter')
    parser.add_argument('--admin-scenario', choices=['mixed', 'empty'], default='mixed')
    args = parser.parse_args()
    database = prepare(SITE.parent / 'work/arxiv-demo/demo.sqlite', rebuild=args.rebuild)
    state = args.state.resolve()
    if state.is_relative_to(Path.home() / '.local/state'):
        raise SystemExit('Choose a demo state folder outside the website state directory')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = {'database': str(database), 'state': str(state), 'url': f'http://127.0.0.1:{args.port}/?source=arxiv', 'offline': True}
    if args.admin_port:
        info['admin'] = f'http://127.0.0.1:{args.admin_port}/admin/'
        info['admin_credentials'] = str(state / 'admin-credentials.txt')
    print(json.dumps(info), flush=True)
    if not args.prepare_only:
        import asyncio
        import uvicorn
        reader = create_demo(database, state=state)
        servers = [uvicorn.Server(uvicorn.Config(reader, host='127.0.0.1', port=args.port))]
        if args.admin_port:
            from demo_personal import create_admin_demo
            admin = create_admin_demo(state, args.admin_scenario, SITE / 'src/cirdc/web/static')
            servers.append(uvicorn.Server(uvicorn.Config(admin, host='127.0.0.1', port=args.admin_port)))

        async def serve():
            await asyncio.gather(*(server.serve() for server in servers))
        asyncio.run(serve())


if __name__ == '__main__':
    main()
