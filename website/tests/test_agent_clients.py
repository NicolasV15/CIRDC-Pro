"""Direct HTTP and hosted MCP integration using only fixture resources."""
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import shutil

import pytest
import uvicorn
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from cirdc.web.app import create_app
from test_agent import agent_site, website  # noqa: F401


@contextmanager
def serve(app):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
    worker = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    worker.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if not worker.is_alive() or time.monotonic() > deadline:
            raise RuntimeError('Fixture server did not start')
        time.sleep(0.01)
    try:
        yield 'http://127.0.0.1:' + str(sock.getsockname()[1])
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        sock.close()
        assert not worker.is_alive()


@pytest.fixture
def client_script(tmp_path):
    source = Path(__file__).parents[1] / '.agents/skills/cirdc-research/scripts/cirdc_client.py'
    target = tmp_path / 'cirdc_client.py'
    shutil.copyfile(source, target)
    return target


def test_standalone_http_helper_acquire_resume_read_download(agent_site, client_script, tmp_path):
    config, provider, resources = agent_site
    with serve(create_app(config, resource_providers=resources, reader_auth='required')) as origin:
        script = client_script

        def cli(*args, success=True):
            result = subprocess.run([sys.executable, '-I', str(script), '--base-url', origin, *args],
                                    cwd=tmp_path, capture_output=True, text=True, timeout=15)
            assert result.returncode == (0 if success else 1), result.stderr + result.stdout
            return json.loads(result.stdout)

        assert cli('capabilities')['authentication'] == 'none'
        assert cli('search', 'RF')['items']
        pending = cli('ensure', '100', '--resources', 'content', 'pdf', '--wait-seconds', '0')
        assert pending['pending'] and pending['status_url'].startswith(origin)
        provider.finish('content'); provider.finish('pdf')
        assert cli('status', pending['request_id'])['complete']
        content = cli('read', '100', '--limit', '1000')
        assert content['version'] == 'v1' and content['next_cursor']
        assert cli('read', '100', '--cursor', content['next_cursor'])['offset'] > 0
        output = tmp_path / 'article.pdf'
        value = cli('pdf', '100', '--output', str(output))
        assert output.read_bytes().startswith(b'%PDF-')
        assert value['download']['bytes'] == output.stat().st_size
        assert cli('pdf', '100', '--output', str(output), success=False)['error'] == 'output_exists'
        assert len(provider.calls) == 2


def test_hosted_mcp_real_http_workflow(agent_site, tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / 'mcp-visits.sqlite'
    monkeypatch.setenv('CIRDC_WEB_VISITS_FILE', str(path))
    config, provider, resources = agent_site
    with serve(create_app(config, resource_providers=resources, reader_auth='required')) as origin:
        async def exercise():
            async with httpx.AsyncClient(trust_env=False) as http_client, streamable_http_client(
                    origin + '/api/agent/v1/mcp', http_client=http_client) as (read, write, session_id):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    assert 'request_id' in initialized.instructions
                    assert session_id() is None
                    listed = await session.list_tools()
                    assert {tool.name for tool in listed.tools} == {'capabilities', 'search_papers', 'get_paper',
                        'ensure_resources', 'get_request', 'read_content', 'get_pdf'}
                    assert next(t for t in listed.tools if t.name == 'get_request').annotations.readOnlyHint

                    async def call(name, args=None):
                        result = await session.call_tool(name, args or {})
                        assert not result.isError
                        return result.structuredContent

                    capabilities = await call('capabilities')
                    assert capabilities['authentication'] == 'none'
                    assert capabilities['mcp_url'] == origin + '/api/agent/v1/mcp'
                    skill = await session.read_resource('cirdc://research/skill')
                    assert 'next_cursor' in skill.contents[0].text
                    assert (await call('search_papers', {'query': 'RF'}))['items']
                    receipt = await call('ensure_resources', {'number': '100', 'resources': ['content', 'pdf'], 'wait_seconds': 0})
                    assert receipt['pending']
                    provider.finish('content'); provider.finish('pdf')
                    assert (await call('get_request', {'request_id': receipt['request_id']}))['complete']
                    assert (await call('read_content', {'number': '100'}))['source'] == 'publisher'
                    pdf = await call('get_pdf', {'number': '100', 'wait_seconds': 0})
                    assert pdf['download']['media_type'] == 'application/pdf'
                    assert pdf['download']['url'].startswith(origin)
                    assert len(provider.calls) == 2
                    assert (await call('get_paper', {'number': '../../admin/users'}))['error'] == 'invalid_number'
            # A new MCP connection can resume the same durable CIRDC receipt.
            async with httpx.AsyncClient(trust_env=False) as http_client, streamable_http_client(
                    origin + '/api/agent/v1/mcp', http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool('get_request', {'request_id': receipt['request_id']})
                    assert result.structuredContent['complete']
        asyncio.run(exercise())
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT ip,kind,paper FROM task_requests').fetchall()
        assert rows and all(row == ('127.0.0.1', 'agent_resources', '100') for row in rows)
        assert db.execute('SELECT count(*) FROM task_links').fetchone()[0] >= 2
