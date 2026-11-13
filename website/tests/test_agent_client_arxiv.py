"""Dual-source helper routing and safe arXiv receipts; no real acquisition."""

import json
import subprocess
import sys

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from test_agent_clients import serve
from test_skill_install import SOURCE, load_script


@pytest.fixture
def helper():
    module = load_script(SOURCE / "scripts/cirdc_client.py")
    client = module.Client.__new__(module.Client)
    client.base_url = "https://papers.example.org"
    client.client_id = "fixture"
    return module, client


def test_namespaces_and_versions_cannot_be_confused(helper):
    module, client = helper
    calls = []
    client.request = lambda path, **kw: calls.append((path, kw)) or {}
    client.paper("123")
    client.arxiv_paper(123)
    client.arxiv_ensure("123", 2)
    client.arxiv_resolve("hep-th/9901001v1")
    assert calls[0] == ("/papers/123", {})
    assert calls[1][1]["prefix"] == "/api/arxiv"
    assert calls[2][0] == "/papers/123/versions/2/ensure"
    assert calls[2][1]["data"] == {"retry": False}
    assert calls[3][1]["params"] == {"id": "hep-th/9901001v1"}
    with pytest.raises(module.ClientError):
        client.paper("0704.0001v2")
    with pytest.raises(module.ClientError):
        client.arxiv_resources("123", 0)
    with pytest.raises(module.ClientError):
        client.arxiv_resources("123", True)
    with pytest.raises(module.ClientError):
        client.arxiv_status("a" * 32)
    with pytest.raises(module.ClientError):
        client.status("a" * 64)


def test_partial_is_terminal_even_when_reading_ready(helper):
    _, client = helper
    calls = []
    value = {"state": "partial", "reading_ready": True, "acquisition_complete": True}
    client.request = lambda *args, **kw: calls.append(args) or value
    assert client.arxiv_status("a" * 64, 10) == value
    assert len(calls) == 1


def test_stdlib_cli_reads_only_and_posts_with_origin(tmp_path, monkeypatch):
    calls = []

    async def endpoint(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            assert request.headers["origin"] == str(request.base_url).rstrip("/")
            assert await request.json() == {"retry": False}
            return JSONResponse({"state": "queued", "request_id": "a" * 64})
        if request.url.path.endswith("/files/pdf"):
            return Response(b"%PDF-fixture", media_type="application/pdf")
        return JSONResponse(
            {"state": "partial", "reading_ready": True, "paper_version": 2, "content": "Cached text"}
        )

    routes = [Route("/api/arxiv/{path:path}", endpoint, methods=["GET", "POST"])]
    with serve(Starlette(routes=routes)) as origin:

        def cli(*args):
            env = __import__("os").environ.copy()
            env.update(HOME=str(tmp_path), CIRDC_SKILL_UPDATE_CHECK="0")
            result = subprocess.run(
                [sys.executable, "-I", str(SOURCE / "scripts/cirdc_client.py"), "--base-url", origin, *args],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            return json.loads(result.stdout)

        assert cli("arxiv-read", "1", "--version", "2")["content"] == "Cached text"
        assert cli("arxiv-status", "a" * 64)["reading_ready"]
        assert all(method == "GET" for method, _ in calls)
        assert cli("arxiv-ensure", "1", "--version", "2")["request_id"] == "a" * 64
        before = len([c for c in calls if c[0] == "POST"])
        output = tmp_path / "paper.pdf"
        value = cli("arxiv-download", "1", "--version", "2", "--kind", "pdf", "--output", str(output))
        assert output.read_bytes() == b"%PDF-fixture" and value["sha256"]
        assert len([c for c in calls if c[0] == "POST"]) == before


def test_mathml_without_tex_is_preserved_in_markdown():
    from cirdc.web.agent_documents import page_document

    raw = "<p>Original formula: <math><mfrac><mi>x</mi><mi>y</mi></mfrac></math></p>"
    document = {"version": "fixture", "html": raw}
    value = page_document(document, "arxiv:1:v2")
    assert "<mfrac>" in value["content"] and "<mi>x</mi>" in value["content"]
    assert "mathml_without_tex" in value["warnings"]
    assert document["html"] == raw
