from concurrent.futures import ThreadPoolExecutor
import copy
import json
import threading

import pytest
from starlette.testclient import TestClient

from cirdc.web.app import create_app
from cirdc.web.resources import ResourceProviders
from cirdc.web.agent import AgentError, PREFIX
from test_web import website  # noqa: F401


class FakeProvider:
    def __init__(self, tmp_path):
        self.current = {'content': {'state': 'missing'}, 'pdf': {'state': 'missing'}}
        self.jobs, self.calls = {}, []
        self.root = tmp_path
        self.lock = threading.Lock()
        self.document = {'version': 'v1', 'source': 'publisher', 'state': 'ready', 'toc': [],
                         'assets_ready': 1, 'assets_total': 1,
                         'html': '<h2>Evidence</h2>' + ''.join('<p>' + str(i) + 'x' * 600 + '</p>' for i in range(5))}
        (tmp_path / 'original.pdf').write_bytes(b'%PDF-1.4\nfixture\n%%EOF')
        (tmp_path / 'figure.png').write_bytes(b'fixture-image')

    def links(self, numbers): return {}
    def routes(self): return []
    def agent_capabilities(self): return {'content': True, 'pdf': True}

    def agent_snapshot(self, number, kind, reference=None):
        if reference and reference.get('jobs'):
            return copy.deepcopy(self.jobs[reference['jobs'][0]])
        return copy.deepcopy(self.current[kind])

    def agent_ensure(self, number, kind, rate_key, retry=False):
        with self.lock:
            if self.current[kind]['state'] in ('pending', 'ready'):
                return self.agent_snapshot(number, kind)
            self.calls.append((kind, retry))
            job_id = kind + '-' + str(len(self.calls))
            value = {'state': 'pending', 'jobs': [{'id': job_id, 'kind': kind, 'state': 'queued'}],
                     'reference': {'jobs': [job_id]}}
            self.jobs[job_id] = self.current[kind] = value
            return copy.deepcopy(value)

    def finish(self, kind, state='ready'):
        self.current[kind]['state'] = state
        if state == 'failed':
            self.current[kind]['reason'] = 'access_restricted'
        if kind == 'content' and state == 'ready':
            self.current[kind].update(version='v1', source='publisher', assets_ready=1, assets_total=1)
        if kind == 'pdf' and state == 'ready':
            self.current[kind]['bytes'] = (self.root / 'original.pdf').stat().st_size
        for job in self.current[kind].get('jobs', []):
            job['state'] = state

    def agent_document(self, number, version=None):
        if version not in (None, 'v1'):
            raise AgentError('version_not_found', 404)
        return self.document

    def agent_file(self, number, asset_id=None, version=None):
        if not asset_id and self.current['pdf']['state'] != 'ready':
            raise AgentError('pdf_not_ready', 409)
        path = self.root / ('figure.png' if asset_id else 'original.pdf')
        if not path.is_file():
            raise AgentError('file_unavailable', 503)
        return {'path': path, 'media_type': 'image/png' if asset_id else 'application/pdf'}


@pytest.fixture
def agent_site(website, tmp_path, monkeypatch):
    class Store:
        def __init__(self, *args): pass
        def close(self): pass
        def execute(self, sql, args=()):
            if args and args[0] == '999': return []
            return [{'number': args[0] if args else '100', 'data': json.dumps({'articleTitle': 'RF AI study',
                     'authors': [], 'doi': '10.1234/example', 'publicationYear': '2025'}), 'updated_at': '2026-01-01'}]
    monkeypatch.setattr('cirdc.web.app.Store', Store)
    provider = FakeProvider(tmp_path)
    resources = object.__new__(ResourceProviders)
    resources.providers, resources.interface = [provider], 'reader'
    return website, provider, resources


def client_for(site, **kwargs):
    config, _, resources = site
    return TestClient(create_app(config, resource_providers=resources, **kwargs))


def ensure(client, kinds=None, **kwargs):
    return client.post(PREFIX + '/papers/100/ensure', json={'resources': kinds or ['content'], 'wait_seconds': 0, **kwargs})


def test_open_access_cors_and_admin_node_boundaries(agent_site):
    with client_for(agent_site, reader_auth='required') as client:
        assert client.get('/api/papers').status_code == 401
        assert client.get(PREFIX + '/capabilities').json()['authentication'] == 'none'
        result = ensure(client)
        assert result.status_code == 202
        assert result.headers['access-control-allow-origin'] == '*'
        assert 'access-control-allow-credentials' not in result.headers
        assert client.options(PREFIX + '/papers/100/ensure', headers={'Origin': 'https://consumer.example.org',
            'Access-Control-Request-Method': 'POST'}).status_code == 204
        assert client.get('/api/admin/users').status_code == 404
        assert client.post('/api/content-nodes/claim', json={}).status_code in (401, 403)
        assert client.post(PREFIX + '/papers/100/ensure', content='{}').status_code == 415
        assert client.get('/llms.txt').status_code == 200
        preflight = client.options(PREFIX + '/mcp', headers={'Origin': 'https://consumer.example.org',
            'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'MCP-Protocol-Version'})
        assert 'MCP-Protocol-Version' in preflight.headers['access-control-allow-headers']
    with client_for(agent_site, interface='admin') as admin:
        assert admin.get(PREFIX + '/capabilities').status_code in (400, 401, 404)
        assert admin.post(PREFIX + '/mcp', json={}).status_code in (400, 401, 403, 404)


def test_online_skill_and_reference_are_readable_without_an_archive(agent_site):
    from urllib.parse import urljoin
    with client_for(agent_site) as client:
        caps = client.get(PREFIX + '/capabilities').json()
        skill = client.get(caps['skill_url'])
        assert skill.status_code == 200 and skill.headers['content-type'].startswith('text/markdown')
        assert 'next_cursor' in skill.text
        reference = client.get(urljoin(caps['skill_url'], 'references/api.md'))
        assert reference.status_code == 200 and '/api/agent/v1/mcp' in reference.text
        assert client.get(PREFIX + '/skill.zip').status_code == 404
        assert '.zip' not in client.get('/llms.txt').text


def test_cached_resources_never_queue_and_no_provider_is_explicit(agent_site):
    _, provider, resources = agent_site
    provider.finish('content')
    with client_for(agent_site) as client:
        result = ensure(client).json()
        assert result['complete'] and not provider.calls
        resources.providers = []
        result = ensure(client, ['pdf']).json()
        assert result['resources']['pdf']['reason'] == 'provider_not_configured'
        assert not result['complete']
        assert client.get(PREFIX + '/papers/100/content').status_code == 503


def test_concurrent_ensure_and_restart_reuse_request_and_job(agent_site):
    with client_for(agent_site) as client:
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(lambda _: ensure(client).json(), range(4)))
        assert len({value['request_id'] for value in values}) == 1
        assert len(agent_site[1].calls) == 1
        url = values[0]['status_url']
    with client_for(agent_site) as restarted:
        assert restarted.get(url).status_code == 202
        agent_site[1].finish('content')
        assert restarted.get(url).json()['complete']
        assert len(agent_site[1].calls) == 1


def test_failure_partial_success_and_explicit_retry(agent_site):
    provider = agent_site[1]
    with client_for(agent_site) as client:
        first = ensure(client, ['content', 'pdf']).json()
        provider.finish('content')
        provider.finish('pdf', 'failed')
        for _ in range(2):
            value = client.get(first['status_url']).json()
            assert value['resources']['content']['state'] == 'ready'
            assert value['resources']['pdf']['reason'] == 'access_restricted'
            ensure(client, ['content', 'pdf'])
        assert len(provider.calls) == 2
        retry = ensure(client, ['content', 'pdf'], retry=True).json()
        assert retry['request_id'] == first['request_id']
        assert provider.calls == [('content', False), ('pdf', False), ('pdf', True)]
        assert retry['prior_attempts'] == 1


def test_wait_returns_ready_and_unknown_paper_never_queues(agent_site):
    provider = agent_site[1]
    with client_for(agent_site) as client:
        assert client.post(PREFIX + '/papers/999/ensure', json={}).status_code == 404
        assert not provider.calls
        ensure(client)
        timer = threading.Timer(0.05, lambda: provider.finish('content'))
        timer.start()
        result = ensure(client, wait_seconds=0.1)
        timer.join()
        assert result.status_code == 200 and result.json()['complete']


def test_content_cursor_pins_version_and_pdf_bytes_are_checked(agent_site):
    provider = agent_site[1]
    provider.finish('content'); provider.finish('pdf')
    with client_for(agent_site) as client:
        first = client.get(PREFIX + '/papers/100/content?limit=1000').json()
        assert first['version'] == 'v1' and first['next_cursor']
        cursor = first['next_cursor']
        result = client.get(PREFIX + '/papers/100/content', params={'cursor': cursor, 'limit': 1000})
        assert result.status_code == 200 and result.json()['offset'] > 0
        assert client.get(PREFIX + '/papers/100/content', params={'cursor': cursor, 'version': 'v2'}).status_code == 422
        assert client.head(PREFIX + '/papers/100/pdf').headers['content-type'] == 'application/pdf'
        assert client.get(PREFIX + '/papers/100/pdf').content.startswith(b'%PDF-')
        (provider.root / 'original.pdf').unlink()
        assert client.head(PREFIX + '/papers/100/pdf').status_code == 503
        assert client.get(PREFIX + '/papers/100/assets/a1').status_code == 422
        assert client.get(PREFIX + '/papers/100/assets/a1?version=v1').content == b'fixture-image'


def test_input_bounds_search_and_schema(agent_site):
    with client_for(agent_site) as client:
        for value in ({'wait_seconds': 31}, {'wait_seconds': True}, {'resources': []}, {'resources': ['content', 'content']}, {'retry': 'yes'}, {'extra': True}):
            assert client.post(PREFIX + '/papers/100/ensure', json=value).status_code == 422
        assert client.get(PREFIX + '/papers', params={'q': 'RF'}).json()['items']
        schema = client.get(PREFIX + '/openapi.json').json()
        assert schema['security'] == []
        assert '/papers/{number}/ensure' in schema['paths']


def test_task_origin_keeps_actual_resource_identity(agent_site, tmp_path, monkeypatch):
    import sqlite3
    from cirdc.web.task_origins import response_jobs, request_kind
    path = tmp_path / 'visits.sqlite'
    monkeypatch.setenv('CIRDC_WEB_VISITS_FILE', str(path))
    assert request_kind({'type': 'http', 'method': 'POST', 'path': PREFIX + '/papers/100/ensure'}) == ('agent_resources', '100')
    config, _, resources = agent_site
    with TestClient(create_app(config, resource_providers=resources), client=('198.51.100.7', 1234)) as client:
        value = ensure(client, ['content', 'pdf']).json()
    jobs = response_jobs(value, '100')
    assert {item['task_id'] for item in jobs} == {'content-1', 'pdf-2'}
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT kind,paper FROM task_requests').fetchall() == [('agent_resources', '100')]
        assert {r[0] for r in db.execute('SELECT task_id FROM task_links')} == {'content-1', 'pdf-2'}


def test_openapi_models_validate_real_responses(agent_site):
    from jsonschema import Draft202012Validator
    from cirdc.web.agent_schema import specification
    spec = specification()
    with client_for(agent_site) as client:
        for model, value in [('Capabilities', client.get(PREFIX + '/capabilities').json()),
                             ('Receipt', ensure(client).json()),
                             ('PaperDetail', client.get(PREFIX + '/papers/100').json()),
                             ('ContentPage', client.get(PREFIX + '/papers/100/content').json())]:
            schema = {'$ref': '#/components/schemas/' + model, 'components': spec['components']}
            Draft202012Validator(schema).validate(value)


def test_ensure_can_join_new_work_while_old_receipt_remains_bound(agent_site):
    provider = agent_site[1]
    with client_for(agent_site) as client:
        first = ensure(client).json()
        provider.finish('content', 'failed')
        other = ensure(client, ['content', 'pdf'], retry=True).json()
        assert other['pending']
        assert client.get(first['status_url']).json()['resources']['content']['state'] == 'failed'
        joined = ensure(client).json()
        assert joined['pending'] and joined['request_id'] == first['request_id']
        assert joined['resources']['content']['jobs'][0]['id'] == other['resources']['content']['jobs'][0]['id']
        assert len(provider.calls) == 3
