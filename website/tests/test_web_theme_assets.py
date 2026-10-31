from cirdc.config import Config
from cirdc.web.app import create_app
from starlette.testclient import TestClient
import pytest


@pytest.mark.parametrize('interface', ['reader', 'admin'])
def test_theme_assets_are_public_static_revalidated_and_csp_compatible(tmp_path, monkeypatch, interface):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'state'))
    with TestClient(create_app(Config(tmp_path, tmp_path / 'runtime', {}), interface=interface), base_url='http://127.0.0.1') as client:
        for path in ['/assets/theme-init.js', '/assets/themes.css']:
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers['cache-control'] == 'no-cache'
            assert "script-src 'self'" in response.headers['content-security-policy']
            assert client.get(path, headers={'If-None-Match':response.headers['etag']}).status_code == 304
        html = client.get('/').text
        assert html.index('/assets/theme-init.js') < html.index('/assets/themes.css')
        assert '<script src="/assets/theme-init.js"></script>' in html
