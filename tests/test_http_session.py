import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
import requests

from cirdc.config import Config
from cirdc.provider import IEEE, UpstreamError


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr('cirdc.provider.time.sleep', lambda _: None)
    seen = []
    control = {'entry_status': 200, 'document_status': 200}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, body, headers=None):
            self.send_response(status)
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            seen.append({'method': 'GET', 'path': self.path, 'headers': dict(self.headers)})
            if self.path == '/search/searchresult.jsp':
                self.reply(control['entry_status'], '<html>Search</html>', {
                    'Content-Type': 'text/html',
                    'Set-Cookie': 'worker-session=test-worker; Path=/; HttpOnly',
                })
            elif control['document_status'] != 200:
                self.reply(control['document_status'], '', {'x-amzn-waf-action': 'challenge'})
            elif self.headers.get('Cookie') != 'worker-session=test-worker':
                self.reply(202, '', {'x-amzn-waf-action': 'challenge'})
            else:
                number = self.path.rsplit('/', 1)[-1]
                data = {'articleNumber': number, 'abstract': 'Available abstract',
                        'keywords': [{'type': 'Author Keywords', 'kwd': ['one', 'two']}]}
                self.reply(200, 'xplGlobal.document.metadata=' + json.dumps(data) + ';',
                           {'Content-Type': 'text/html'})

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            seen.append({'method': 'POST', 'path': self.path, 'headers': dict(self.headers),
                         'body': json.loads(body)})
            self.reply(200, json.dumps({'records': [], 'totalRecords': 0, 'totalPages': 1}),
                       {'Content-Type': 'application/json'})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = requests.Session()
    session.trust_env = False  # This fixture talks only to its local test server.
    provider = IEEE(Config(tmp_path, tmp_path / 'state'), session)
    provider.BASE = f'http://127.0.0.1:{server.server_port}'
    yield provider, seen, control
    session.close()
    server.shutdown()
    thread.join()
    server.server_close()


def test_server_session_cookie_is_reused_and_entry_is_loaded_once(source):
    provider, seen, _ = source
    first, states = provider.document('7')
    second, _ = provider.document('8')
    assert first['abstract'] == 'Available abstract'
    assert second['articleNumber'] == '8'
    assert states == {'abstract': 'complete', 'keywords': 'complete'}
    assert [r['path'] for r in seen] == ['/search/searchresult.jsp', '/document/7', '/document/8']
    assert all('text/html' in r['headers']['Accept'] for r in seen)
    assert all('Content-Type' not in r['headers'] for r in seen)
    assert all(r['headers']['Cookie'] == 'worker-session=test-worker' for r in seen[1:])


def test_json_headers_and_body_remain_correct_after_document_navigation(source):
    provider, seen, _ = source
    provider.document('7')
    assert provider.search_all('4', 2026) == []
    request = seen[-1]
    assert request['method'] == 'POST'
    assert request['headers']['Content-Type'] == 'application/json'
    assert request['headers']['Accept'] == IEEE.JSON_ACCEPT
    assert request['body']['ranges'] == ['2026_2026_Year']


def test_get_removes_a_caller_supplied_global_content_type(source):
    provider, seen, _ = source
    provider.session.headers['Content-Type'] = 'application/json'
    provider.document('7')
    assert all('Content-Type' not in r['headers'] for r in seen)


def test_failed_session_initialization_is_bounded_and_can_be_retried(source):
    provider, seen, control = source
    control['entry_status'] = 418
    with pytest.raises(UpstreamError) as error:
        provider.document('7')
    assert error.value.code == 'access_restricted'
    assert [r['path'] for r in seen] == ['/search/searchresult.jsp'] * 3
    control['entry_status'] = 200
    assert provider.document('7')[0]['articleNumber'] == '7'
    assert [r['path'] for r in seen][-2:] == ['/search/searchresult.jsp', '/document/7']


def test_remaining_document_challenge_stays_blocked_after_initialization(source):
    provider, seen, control = source
    control['document_status'] = 202
    with pytest.raises(UpstreamError, match='AWS WAF challenge') as error:
        provider.document('7')
    assert error.value.code == 'access_restricted'
    assert [r['path'] for r in seen] == ['/search/searchresult.jsp'] + ['/document/7'] * 3


def test_invalid_document_id_does_not_initialize_a_session(source):
    provider, seen, _ = source
    with pytest.raises(ValueError):
        provider.document('../7')
    assert not seen
