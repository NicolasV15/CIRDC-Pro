"""The exported subset must run offline without changing production state."""
import hashlib
import json
import runpy
import shutil
import sqlite3
from pathlib import Path

import pytest
from starlette.testclient import TestClient

TOOLS = Path(__file__).resolve().parents[1] / 'tools'


@pytest.fixture
def demo(tmp_path, monkeypatch):
    def unexpected_network(*args, **kwargs):
        raise AssertionError('demo attempted a source connection')
    monkeypatch.setattr('pymysql.connect', unexpected_network)
    monkeypatch.setattr('requests.sessions.Session.request', unexpected_network)
    monkeypatch.setattr('urllib.request.urlopen', unexpected_network)
    from cirdc.web import index as production_index
    original = production_index.connect
    module = runpy.run_path(str(TOOLS / 'arxiv_demo.py'))
    database = module['prepare'](tmp_path / 'demo.sqlite')
    # Demo accounts live only in the demo's own state folder.
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'state'))
    app = module['create_demo'](database, state=tmp_path / 'state')
    assert production_index.connect is original
    with TestClient(app) as client:
        yield module, database, client


def test_real_subset_search_and_versions(demo):
    module, database, client = demo
    overview = client.get('/api/arxiv/overview').json()
    assert overview['indexed'] == 43
    first = client.get('/api/arxiv/papers?limit=25').json()
    assert len(first['items']) == 25 and first['next_cursor']
    second = client.get('/api/arxiv/papers', params={'limit': 25, 'cursor': first['next_cursor']}).json()
    assert len(second['items']) == 18
    assert not {p['paper_id'] for p in first['items']} & {p['paper_id'] for p in second['items']}
    assert client.get('/api/arxiv/papers?category=eess').json()['total'] > 0
    result = client.get('/api/arxiv/papers?q=0704.0001v1').json()
    assert result['items'][0]['requested_version'] == 1
    assert client.get('/api/arxiv/papers?year_from=2026&year_to=2007').status_code == 422
    paper = client.get('/api/arxiv/resolve?id=0704.0001').json()['paper']
    assert [v['version'] for v in paper['versions']] == [1, 2]
    assert client.get('/api/arxiv/papers/1/versions/999/resources').status_code == 404
    assert client.get('/api/papers').json()['total'] == 3
    assert client.get('/api/papers/11741266').json()['paper']['record']['articleTitle']
    assert module['prepare'](database) == database  # Healthy demo is reused.


def test_immutable_real_body_and_explicit_unbundled_states(demo):
    module, _, client = demo
    manifest = json.loads((module['DATA'] / 'manifest.json').read_text())
    for file in manifest['files']:
        response = client.get(file['url'])
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() == file['sha256']
        assert client.head(file['url']).content == b''
    body = manifest['document']['document']['body_url']
    assert client.get(body.replace('render_id=', 'render_id=invalid')).status_code == 404
    state = client.get('/api/arxiv/papers/1/versions/2/resources').json()
    assert state['reading_state'] == 'not_packaged'
    assert all(r['state'] == 'not_packaged' for r in state['resources'].values())
    assert state['acquisition_complete'] is False
    assert client.get('/api/arxiv/papers/1/versions/2/files/pdf').status_code == 404
    assert client.post('/api/arxiv/papers/1/versions/2/ensure', json={}).status_code == 409
    assert client.post('/api/resources/arxiv/versions/2/archives', json={}).status_code == 409
    with sqlite3.connect(demo[1]) as db:
        assert db.execute('SELECT count(*) FROM papers').fetchone()[0] == 43


def test_corrupt_bundle_cannot_replace_existing_database(demo, tmp_path):
    module, database, _ = demo
    before = database.read_bytes()
    source = tmp_path / 'corrupt'
    shutil.copytree(module['DATA'], source)
    (source / 'metadata.json').write_text('{}')
    with pytest.raises(ValueError, match='demo_metadata_digest_mismatch'):
        module['prepare'](database, source, rebuild=True)
    assert database.read_bytes() == before
    other = tmp_path / 'unrelated.sqlite'
    with sqlite3.connect(other) as db:
        db.execute('CREATE TABLE sentinel(value)')
    original = other.read_bytes()
    with pytest.raises(sqlite3.OperationalError):
        module['prepare'](other, rebuild=True)
    assert other.read_bytes() == original


def demo_session(client, name):
    client.cookies.clear()
    csrf = client.get('/api/auth/session?prepare=1').json()['csrf']
    origin = str(client.base_url).rstrip('/')
    r = client.post('/api/auth/register', json={'username': name, 'password': 'demo-password-1'},
                    headers={'Origin': origin, 'X-CSRF-Token': csrf})
    assert r.status_code == 200
    return {'Origin': origin, 'X-CSRF-Token': r.json()['csrf']}


def test_demo_accounts_favorites_and_archives_use_the_real_implementation(demo, tmp_path):
    import io
    import zipfile
    module, database, client = demo
    assert client.get('/api/me/favorites').status_code == 401
    headers = demo_session(client, 'demo-reader')
    items = [{'source': 'ieee', 'paper_id': n} for n in ('11741266', '11126195', '11717827')]
    items += [{'source': 'arxiv', 'paper_id': '1', 'version': v} for v in (1, 2)]
    items += [{'source': 'arxiv', 'paper_id': '3300802', 'version': 1}, {'source': 'arxiv', 'paper_id': '3300801', 'version': 'latest'}]
    saved = client.post('/api/me/favorites', json={'items': items}, headers=headers).json()['items']
    assert len(saved) == 7 and all(saved.values())
    ids = list(saved.values())
    prepared = client.post('/api/me/archives', json={'ids': ids}, headers=headers).json()
    assert {s['reason'] for s in prepared['skipped']} == {'not_packaged'} and len(prepared['skipped']) == 2
    package = client.get(prepared['archive']['href'])
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    real = (TOOLS.parent / 'demo/arxiv/files/2611.14519v1-paper.pdf').read_bytes()
    assert hashlib.sha256(files['arxiv_2611.14519v1.pdf']).hexdigest() == hashlib.sha256(real).hexdigest()
    tests = [name for name, value in files.items() if b'TEST MATERIAL - not the paper' in value]
    assert len(tests) == 4 and len(files) == 5
    # Writes other than personal ones stay disabled, and the store is the demo's own.
    assert client.post('/api/arxiv/papers/1/versions/1/ensure', json={}, headers=headers).status_code == 409
    assert (tmp_path / 'state/accounts.sqlite').exists()


def test_admin_adapter_uses_isolated_fixtures_and_real_account_management(tmp_path, monkeypatch):
    module = runpy.run_path(str(TOOLS / 'demo_personal.py'))
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'state'))
    static = TOOLS.parent / 'src/cirdc/web/static'
    if not (static / 'index.html').exists():
        pytest.skip('Build the frontend first')
    for scenario, runs in (('mixed', 3), ('empty', 0)):
        app = module['create_admin_demo'](tmp_path / 'state', scenario, static)
        password = (tmp_path / 'state/admin-credentials.txt').read_text().split('password: ')[1].strip()
        with TestClient(app, base_url='http://localhost') as client:
            assert client.get('/api/admin/runs').status_code == 401
            csrf = client.get('/api/auth/session').json()['csrf']
            origin = {'Origin': 'http://localhost'}
            r = client.post('/api/auth/login', json={'username': 'demo-admin', 'password': password}, headers={**origin, 'X-CSRF-Token': csrf})
            headers = {**origin, 'X-CSRF-Token': r.json()['csrf']}
            assert len(client.get('/api/admin/runs').json()['items']) == runs
            accepted = client.post('/api/admin/actions/update', json={'stage': 'all'}, headers=headers).json()
            assert accepted['demo_adapter'] and 'no job was started' in accepted['note']
            assert client.post('/api/admin/users/create', json={'username': 'new-reader', 'password': 'reader-pass-1'}, headers=headers).status_code in (200, 422)
            assert 'new-reader' in [u['username'] for u in client.get('/api/admin/users').json()['items']]
