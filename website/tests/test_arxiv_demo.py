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
    app = module['create_demo'](database)
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
