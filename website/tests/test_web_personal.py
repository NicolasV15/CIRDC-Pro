"""Self-registration, synced preferences, favorites and favorite archives."""
import hashlib
import io
import sqlite3
import time
import zipfile

import pytest

pytest.importorskip('argon2', reason='Install the web extra')
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import cirdc.web.app as web_app
from cirdc.web.app import create_app
from cirdc.web.auth import Accounts
from cirdc.web.personal import ARCHIVE_SECONDS, Directory
from cirdc.web.settings import connect
from test_web import website as website  # noqa: F401 - shared fixture

ORIGIN = 'http://testserver'


def pdf(label):
    return b'%PDF-1.7\n% test material, not a paper: ' + label.encode() + b'\n%%EOF\n'


IEEE = {'100': 'RF study', '101': 'Same title', '102': 'Restricted copy', '103': 'Same title', '104': 'No file',
        '105': 'Not a PDF', '106': 'Broken stream'}
ARXIV = {'7': {'arxiv_id': '2402.08954', 'title': 'Two versions', 'versions': [{'version': 1}, {'version': 2}]},
         '8': {'arxiv_id': 'hep-th/9901001', 'title': 'Old identifier', 'versions': [{'version': 1}]}}


class Catalogs(Directory):
    calls = []

    def ieee(self, numbers):
        return {n: {'title': IEEE[n], 'year': 2025} for n in numbers if n in IEEE}

    def arxiv(self, paper_id):
        paper = ARXIV.get(paper_id)
        return {'paper_id': paper_id, **paper} if paper else None

    def pdf_route(self, source, paper_id, version):
        if source == 'ieee':
            return None if paper_id == '104' else f'/api/resources/test/{paper_id}.pdf'
        return f'/api/arxiv/papers/{paper_id}/versions/{version}/files/pdf'


class Provider:
    """Read-only cache routes standing in for a registered provider; every byte here is test material."""
    ensure_calls = 0

    def routes(self):
        async def ieee(request):
            number = request.path_params['number']
            if number == '102':
                return JSONResponse({'error': 'restricted'}, 403)
            if number == '105':
                return Response(b'<html>not a pdf</html>', media_type='text/html')
            if number == '106':
                async def broken():
                    yield b'%PDF-1.7 partial'
                    raise OSError('read interrupted')
                return StreamingResponse(broken(), media_type='application/pdf')
            return Response(pdf('ieee ' + number), media_type='application/pdf')

        async def arxiv(request):
            pid, version = request.path_params['paper_id'], int(request.path_params['version'])
            if pid == '8':
                return JSONResponse({'error': 'demo_resource_not_packaged'}, 404)
            return Response(pdf(f'arxiv {pid} v{version}'), media_type='application/pdf')

        def ensure(request):
            Provider.ensure_calls += 1
            return JSONResponse({'state': 'queued'}, 202)

        return [Route('/api/resources/test/{number}.pdf', ieee),
                Route('/api/arxiv/papers/{paper_id}/versions/{version}/files/pdf', arxiv),
                Route('/api/arxiv/papers/{paper_id}/versions/{version}/ensure', ensure, methods=['POST'])]

    def attach(self, items):
        pass


@pytest.fixture
def site(website, monkeypatch):
    monkeypatch.setattr(web_app, 'SiteDirectory', lambda *args: Catalogs())
    Provider.ensure_calls = 0
    return create_app(website, resource_providers=Provider(), reader_auth='public')


def register(client, name, password='fixture-password-1'):
    """Register as a new visitor: any earlier session cookie is dropped first."""
    client.cookies.clear()
    csrf = client.get('/api/auth/session?prepare=1').json()['csrf']
    r = client.post('/api/auth/register', json={'username': name, 'password': password},
                    headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf})
    return r, {'Origin': ORIGIN, 'X-CSRF-Token': r.json().get('csrf', '')}


def test_registration_creates_a_signed_in_reader_without_forced_password_change(site):
    with TestClient(site) as client:
        r, headers = register(client, 'reader-one')
        assert r.status_code == 200
        assert r.json()['user'] == {**r.json()['user'], 'username': 'reader-one', 'role': 'reader', 'must_change': False}
        assert client.get('/api/auth/session').json()['user']['username'] == 'reader-one'
        assert client.get('/api/me/settings').status_code == 200
        assert client.post('/api/auth/logout', headers=headers).status_code == 200
        assert client.get('/api/me/settings').status_code == 401
        assert register(client, 'reader-one')[0].json()['error'] == 'username_taken'
        assert register(client, 'Bad Name')[0].status_code == 422
        assert register(client, 'shortpw', 'short')[0].status_code == 422
    rows = {r['username']: r for r in site.state.accounts.list()}
    assert rows['reader-one']['origin'] == 'self' and rows['reader-one']['role'] == 'reader'


def test_registration_is_rate_limited_per_address_and_closed_for_private_readers(site, website):
    with TestClient(site) as client:
        statuses = [register(client, f'user-{i}')[0].status_code for i in range(6)]
    assert statuses == [200, 200, 200, 200, 200, 429]
    required = create_app(website, reader_auth='required')
    with TestClient(required) as client:
        assert client.get('/api/auth/session').json()['registration'] is False
        assert client.post('/api/auth/register', json={}, headers={'Origin': ORIGIN}).status_code in (401, 404)


def test_existing_account_store_migrates_repeatably_and_keeps_accounts(website):
    with sqlite3.connect(connect('accounts.sqlite').execute('PRAGMA database_list').fetchone()[2]) as db:
        db.executescript('''
            CREATE TABLE users(username TEXT PRIMARY KEY,password_hash TEXT NOT NULL,role TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,must_change INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL);
            INSERT INTO users VALUES('legacy','hash-kept','admin',1,0,1.0);''')
    for _ in range(2):
        accounts = Accounts()
    with accounts.db() as db:
        row = dict(db.execute('SELECT * FROM users WHERE username=?', ('legacy',)).fetchone())
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert row['password_hash'] == 'hash-kept' and row['role'] == 'admin' and row['origin'] == 'admin'
    assert {'user_settings', 'favorites', 'archives', 'signups', 'sessions', 'audit'} <= tables


def test_settings_are_per_account_validated_and_merged(site):
    with TestClient(site) as alice, TestClient(site) as bob:
        _, a = register(alice, 'alice')
        _, b = register(bob, 'bob')
        assert alice.get('/api/me/settings').json()['settings'] == {'theme': None, 'language': None, 'updated': None}
        assert alice.put('/api/me/settings', json={'theme': 'midnight', 'language': 'en'}, headers=a).status_code == 200
        assert alice.put('/api/me/settings', json={'language': 'zh'}, headers=a).json()['settings']['theme'] == 'midnight'
        assert alice.put('/api/me/settings', json={'theme': 'neon'}, headers=a).status_code == 422
        assert alice.put('/api/me/settings', json={}, headers=a).status_code == 422
        assert alice.put('/api/me/settings', json={'theme': 'paper'}, headers={'Origin': ORIGIN}).status_code == 403
        assert alice.put('/api/me/settings', json={'theme': 'paper'},
                         headers={'X-CSRF-Token': a['X-CSRF-Token']}).status_code == 403
        assert bob.get('/api/me/settings').json()['settings']['theme'] is None
        assert alice.get('/api/me/settings').json()['settings']['language'] == 'zh'


def test_theme_ids_match_the_frontend_catalog():
    import re
    from pathlib import Path
    from cirdc.web.personal import THEMES
    source = (Path(__file__).parents[1] / 'web/src/themeCatalog.ts').read_text()
    assert THEMES == {'system', *re.findall(r"id:'([a-z-]+)'", source)}


def test_favorites_are_verified_versioned_idempotent_and_private(site):
    with TestClient(site) as alice, TestClient(site) as bob:
        _, a = register(alice, 'alice')
        _, b = register(bob, 'bob')
        items = [{'source': 'ieee', 'paper_id': '100'}, {'source': 'arxiv', 'paper_id': '7', 'version': 1},
                 {'source': 'arxiv', 'paper_id': '7', 'version': 2}]
        state = alice.post('/api/me/favorites', json={'items': items}, headers=a).json()['items']
        assert set(state) == {'ieee:100', 'arxiv:7:1', 'arxiv:7:2'} and all(state.values())
        assert alice.post('/api/me/favorites', json={'items': items[:1]}, headers=a).json()['items'] == {'ieee:100': state['ieee:100']}
        assert alice.post('/api/me/favorites', json={'items': [{'source': 'ieee', 'paper_id': '999'}]}, headers=a).status_code == 404
        assert alice.post('/api/me/favorites', json={'items': [{'source': 'arxiv', 'paper_id': '7', 'version': 9}]}, headers=a).status_code == 404
        assert alice.post('/api/me/favorites', json={'items': [{'source': 'arxiv', 'paper_id': '7'}]}, headers=a).status_code == 422
        assert alice.post('/api/me/favorites', json={'items': [{'source': 'ieee', 'paper_id': '100', 'user': 'bob'}]},
                          headers={'Origin': ORIGIN}).status_code == 403
        listed = alice.get('/api/me/favorites?limit=2').json()
        assert [i['version'] for i in listed['items']] == [2, 1] and listed['next_cursor']
        assert listed['counts'] == {'ieee': 1, 'arxiv': 2} and listed['total'] == 3
        rest = alice.get('/api/me/favorites?limit=2&cursor=' + str(listed['next_cursor'])).json()
        assert [i['identifier'] for i in rest['items']] == ['100'] and rest['next_cursor'] is None
        assert [i['source'] for i in alice.get('/api/me/favorites?source=ieee').json()['items']] == ['ieee']
        versions = alice.get('/api/me/favorites/state?keys=arxiv:7,ieee:101').json()['items']
        assert versions['arxiv:7']['versions'] == {'1': state['arxiv:7:1'], '2': state['arxiv:7:2']} and versions['ieee:101'] is None
        # Another user sees nothing and cannot remove or read someone else's favorites.
        assert bob.get('/api/me/favorites').json()['total'] == 0
        assert bob.post('/api/me/favorites/remove', json={'ids': list(state.values())}, headers=b).json()['removed'] == 0
        assert bob.post('/api/me/archives', json={'ids': [state['ieee:100']]}, headers=b).status_code == 404
        assert alice.post('/api/me/favorites/remove', json={'ids': [state['arxiv:7:1']]}, headers=a).json()['removed'] == 1
        assert alice.get('/api/me/favorites').json()['counts'] == {'ieee': 1, 'arxiv': 1}


def test_unreadable_favorites_are_kept_with_their_status(site):
    with TestClient(site) as client:
        _, headers = register(client, 'keeper')
        client.post('/api/me/favorites', json={'items': [{'source': 'arxiv', 'paper_id': '7', 'version': 2},
                                                         {'source': 'ieee', 'paper_id': '101'}]}, headers=headers)
        ARXIV['7']['versions'] = [{'version': 1}]
        IEEE.pop('101')
        try:
            items = {i['identifier']: i for i in client.get('/api/me/favorites').json()['items']}
        finally:
            ARXIV['7']['versions'] = [{'version': 1}, {'version': 2}]
            IEEE['101'] = 'Same title'
        assert items['2402.08954']['status'] == 'version_missing' and items['2402.08954']['version'] == 2
        assert items['101']['status'] == 'paper_missing' and items['101']['title'] == 'Same title'


def favorites(client, headers, entries):
    state = client.post('/api/me/favorites', json={'items': entries}, headers=headers).json()['items']
    return list(state.values())


def test_archive_combines_sources_and_versions_with_exact_bytes_and_explicit_skips(site):
    with TestClient(site) as client:
        _, headers = register(client, 'zipper')
        ids = favorites(client, headers, [{'source': 'ieee', 'paper_id': n} for n in ('100', '101', '102', '103', '104', '105')]
                        + [{'source': 'arxiv', 'paper_id': '7', 'version': v} for v in (1, 2)]
                        + [{'source': 'arxiv', 'paper_id': '8', 'version': 1}])
        names = {str(i): 'Same title.pdf' for i in ids}
        names[str(ids[0])] = '../escape.pdf'
        r = client.post('/api/me/archives', json={'ids': ids, 'filenames': names}, headers=headers)
        assert r.status_code == 201
        value = r.json()
        reasons = {s['id']: s['reason'] for s in value['skipped']}
        assert reasons == {ids[2]: 'restricted', ids[4]: 'missing', ids[5]: 'unreadable', ids[8]: 'not_packaged'}
        archive = client.get(value['archive']['href'])
        assert archive.status_code == 200 and archive.headers['cache-control'] == 'private, no-store'
        with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
            files = {name: package.read(name) for name in package.namelist()}
        assert sorted(files) == ['Same title (2).pdf', 'Same title (3).pdf', 'Same title (4).pdf', 'Same title.pdf',
                                 'ieee_100.pdf']
        expected = {pdf(label) for label in ('ieee 100', 'ieee 101', 'ieee 103', 'arxiv 7 v1', 'arxiv 7 v2')}
        assert {hashlib.sha256(v).hexdigest() for v in files.values()} == {hashlib.sha256(v).hexdigest() for v in expected}
        assert Provider.ensure_calls == 0
        # A signed-out or different session cannot fetch the archive.
        client.post('/api/auth/logout', headers=headers)
        assert client.get(value['archive']['href']).status_code == 401
        _, other = register(client, 'someone')
        assert client.get(value['archive']['href']).status_code == 404


def test_archive_limits_empty_results_and_interrupted_reads(site):
    with TestClient(site) as client:
        _, headers = register(client, 'limits')
        missing = favorites(client, headers, [{'source': 'ieee', 'paper_id': '104'}])
        r = client.post('/api/me/archives', json={'ids': missing}, headers=headers)
        assert r.status_code == 200 and r.json()['archive'] is None and r.json()['skipped'][0]['reason'] == 'missing'
        assert client.post('/api/me/archives', json={'ids': list(range(1, 102))}, headers=headers).json()['error'] == 'too_many_archive_items'
        assert client.post('/api/me/archives', json={'ids': missing * 101}, headers=headers).status_code == 200
        broken = favorites(client, headers, [{'source': 'ieee', 'paper_id': '106'}, {'source': 'ieee', 'paper_id': '100'}])
        r = client.post('/api/me/archives', json={'ids': broken}, headers=headers)
        assert r.status_code == 500 and r.json()['error'] == 'archive_failed'
    folder = connect('accounts.sqlite').execute('PRAGMA database_list').fetchone()[2].rsplit('/', 1)[0] + '/archives'
    import os
    assert os.listdir(folder) == []


def test_archives_expire_and_are_removed(site):
    with TestClient(site) as client:
        _, headers = register(client, 'expiry')
        ids = favorites(client, headers, [{'source': 'ieee', 'paper_id': '100'}])
        first = client.post('/api/me/archives', json={'ids': ids}, headers=headers).json()['archive']
        assert client.delete(first['href'], headers=headers).status_code == 200
        assert client.get(first['href']).status_code == 404
        second = client.post('/api/me/archives', json={'ids': ids}, headers=headers).json()['archive']
        with site.state.accounts.db() as db:
            path = db.execute('SELECT path FROM archives WHERE id=?', (second['id'],)).fetchone()['path']
            db.execute('UPDATE archives SET expires=?', (time.time() - 1,))
        assert client.get(second['href']).status_code == 404
        import os
        assert not os.path.exists(path)
        assert ARCHIVE_SECONDS == 3600
