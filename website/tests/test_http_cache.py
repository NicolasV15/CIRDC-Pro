from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient
import pytest

from cirdc.web.http_cache import CatalogCache, PublicTextCompression, accepts_gzip


@pytest.mark.parametrize('header,expected', [('gzip', True), ('br, gzip;q=0.8', True),
    ('*;q=1', True), ('gzip;q=0, *;q=1', False), ('identity', False),
    ('GZIP; q=0', False), ('gzip;q=bad', False), ('', False)])
def test_encoding_quality_is_respected(header, expected):
    assert accepts_gzip(header) is expected


def test_expired_catalog_changes_its_validator_and_payload():
    cache = CatalogCache()
    request = Request({'type': 'http', 'headers': []})
    old = cache.response(request, lambda: b'old catalog')
    cache.expires = 0
    check = Request({'type': 'http', 'headers': [(b'if-none-match', old.headers['etag'].encode())]})
    new = cache.response(check, lambda: b'new catalog')
    assert new.status_code == 200 and new.body == b'new catalog'
    assert new.headers['etag'] != old.headers['etag']


def test_public_text_compression_excludes_resources_range_and_account_routes():
    body = b'fixture text ' * 300
    def content(request):
        return Response(body, status_code=206 if 'range' in request.headers else 200,
                        media_type='text/javascript' if request.url.path.endswith('.js') else 'application/json' if request.url.path.endswith('.json') else 'application/octet-stream',
                        headers={'Content-Range': f'bytes 0-{len(body)-1}/{len(body)}'} if 'range' in request.headers else {})
    paths = ['/assets/a.js', '/assets/map.json', '/api/papers', '/api/auth/session', '/api/admin/users',
             '/api/resources/local-library/1/pdf', '/api/resources/local-library/1/reader']
    app = Starlette(routes=[Route(p, content, methods=['GET', 'HEAD']) for p in paths])
    app.add_middleware(PublicTextCompression)
    with TestClient(app) as client:
        for path in paths:
            response = client.get(path, headers={'Accept-Encoding': 'gzip'})
            assert response.content == body
            assert ('content-encoding' in response.headers) == (path in paths[:3])
        disabled = client.get(paths[0], headers={'Accept-Encoding': 'gzip;q=0'})
        assert 'content-encoding' not in disabled.headers
        assert 'Accept-Encoding' in disabled.headers['vary']
        ranged = client.get('/api/resources/local-library/1/pdf', headers={'Range': 'bytes=0-99', 'Accept-Encoding': 'gzip'})
        assert ranged.status_code == 206 and 'content-range' in ranged.headers
        assert 'content-encoding' not in ranged.headers
        assert not client.head('/api/resources/local-library/1/pdf', headers={'Accept-Encoding': 'gzip'}).content
