"""Standalone CIRDC HTTP client and CLI. Python standard library only."""

import argparse
import json
import os
import re
import socket
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

PREFIX = "/api/agent/v1"
ARXIV_PREFIX = "/api/arxiv"


class ClientError(Exception):
    def __init__(self, value, status=None):
        self.value, self.status = value, status
        super().__init__(value.get("error", "request_failed"))


class Client:
    def __init__(self, base_url=None, *, check_updates=True):
        value = base_url or os.environ.get("CIRDC_BASE_URL", "")
        if not value:
            config = Path.home() / ".config/cirdc/research.json"
            if not config.exists():
                raise ClientError(
                    {
                        "error": "site_not_configured",
                        "message": "Complete installation with install_skill.py --configure (or sh tools/install-skill --configure). Research use does not prompt for a URL.",
                    }
                )
            try:
                value = json.loads(config.read_text(encoding="utf-8"))["base_url"]
            except (OSError, ValueError, KeyError, TypeError):
                raise ClientError({"error": "invalid_site_config"}) from None
        if not isinstance(value, str):
            raise ClientError({"error": "invalid_site_config"})
        value = value.rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ClientError(
                {
                    "error": "configure_site_origin",
                    "message": "Set CIRDC_BASE_URL or --base-url to the site origin.",
                }
            )
        self.base_url = value
        import uuid

        identity = Path.home() / ".config/cirdc/research-client-id"
        identity.parent.mkdir(parents=True, exist_ok=True)
        if not identity.exists():
            try:
                identity.write_text(uuid.uuid4().hex, encoding="ascii")
            except OSError:
                pass
        self.client_id = identity.read_text().strip() if identity.exists() else uuid.uuid4().hex
        if check_updates:
            self.updates(notify=True)

    def updates(self, action="status", hours=24, version=None, notify=False):
        installer = Path(__file__).resolve().with_name("install_skill.py")
        try:
            namespace = {"__name__": "cirdc_skill_updates", "__file__": str(installer)}
            exec(compile(installer.read_text(encoding="utf-8"), str(installer), "exec"), namespace)
            return namespace["skill_updates"](
                self.base_url, action=action, hours=hours, version=version, notify=notify
            )
        except (OSError, ValueError, SyntaxError):
            return {"status": "unavailable"}  # Older partial copies keep working.

    def absolute(self, value):
        if isinstance(value, list):
            return [self.absolute(item) for item in value]
        if isinstance(value, dict):
            return {
                key: urljoin(self.base_url, item)
                if isinstance(item, str) and key.endswith(("url", "_href")) and item.startswith("/")
                else self.absolute(item)
                for key, item in value.items()
            }
        return value

    def request(self, path, data=None, params=None, method=None, timeout=45, *, prefix=PREFIX):
        if prefix not in (PREFIX, ARXIV_PREFIX):
            raise ClientError({"error": "invalid_api_prefix"})
        url = self.base_url + prefix + path
        if params:
            url += "?" + urlencode({k: v for k, v in params.items() if v is not None and v != ""})
        body = None if data is None else json.dumps(data, allow_nan=False).encode()
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                **({"Origin": self.base_url} if prefix == ARXIV_PREFIX and data is not None else {}),
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                if method == "HEAD":
                    return {
                        "url": url,
                        "bytes": int(response.headers["Content-Length"]),
                        "media_type": response.headers.get_content_type(),
                    }
                result = json.load(response)
                result["http_status"] = response.status
                if response.headers.get("Retry-After", "").isdigit():
                    result["retry_after_seconds"] = int(response.headers["Retry-After"])
        except HTTPError as error:
            try:
                value = json.load(error)
            except (ValueError, UnicodeError):
                value = {"error": "http_error", "status": error.code}
            value["http_status"] = error.code
            if error.headers.get("Retry-After", "").isdigit():
                value["retry_after_seconds"] = int(error.headers["Retry-After"])
            raise ClientError(self.absolute(value), error.code) from None
        except (URLError, TimeoutError, OSError) as error:
            operation = request.get_method()
            reason = getattr(error, "reason", error)
            raise ClientError(
                {
                    "error": "connection_failed",
                    "method": operation,
                    "failure_kind": "timeout"
                    if isinstance(reason, (TimeoutError, socket.timeout))
                    else "connection",
                    "next_action": "wait",
                    "retry_after_seconds": 5,
                    **({"accepted": None} if operation == "POST" else {}),
                    "message": "Submission status is unknown; back off, read first, then resume without retry."
                    if operation == "POST"
                    else "Read failed; back off before reading again.",
                }
            ) from None
        return self.absolute(result)

    @staticmethod
    def arxiv_paper_id(value):
        if type(value) not in (str, int) or not re.fullmatch("[1-9][0-9]{0,63}", str(value)):
            raise ClientError({"error": "invalid_arxiv_paper_id"})
        return str(value)

    @staticmethod
    def arxiv_version(version):
        if type(version) is not int or version < 1:
            raise ClientError({"error": "invalid_arxiv_version"})
        return str(version)

    def arxiv_search(self, query, cursor=None, limit=20):
        return self.request(
            "/papers", params={"q": query, "cursor": cursor, "limit": limit}, prefix=ARXIV_PREFIX
        )

    def arxiv_resolve(self, identifier):
        return self.request("/resolve", params={"id": identifier}, prefix=ARXIV_PREFIX)

    def arxiv_paper(self, paper_id):
        return self.request("/papers/" + self.arxiv_paper_id(paper_id), prefix=ARXIV_PREFIX)

    def arxiv_versions(self, paper_id):
        return self.request("/papers/" + self.arxiv_paper_id(paper_id) + "/versions", prefix=ARXIV_PREFIX)

    def arxiv_resources(self, paper_id, version):
        return self.request(
            "/papers/"
            + self.arxiv_paper_id(paper_id)
            + "/versions/"
            + self.arxiv_version(version)
            + "/resources",
            prefix=ARXIV_PREFIX,
        )

    def arxiv_ensure(self, paper_id, version, retry=False):
        return self.request(
            "/papers/"
            + self.arxiv_paper_id(paper_id)
            + "/versions/"
            + self.arxiv_version(version)
            + "/ensure",
            data={"retry": retry},
            prefix=ARXIV_PREFIX,
        )

    def arxiv_status(self, request_id, wait_seconds=0):
        if not re.fullmatch("[a-f0-9]{64}", request_id):
            raise ClientError({"error": "invalid_arxiv_request_id"})
        if not 0 <= wait_seconds <= 30:
            raise ClientError({"error": "invalid_wait_seconds"})
        deadline = time.monotonic() + wait_seconds
        last = None
        while True:
            remaining = deadline - time.monotonic()
            if wait_seconds and remaining <= 0 and last is not None:
                return last
            try:
                value = self.request(
                    "/requests/" + request_id,
                    prefix=ARXIV_PREFIX,
                    timeout=max(0.001, remaining) if wait_seconds else 45,
                )
            except ClientError as error:
                if (
                    last is not None
                    and wait_seconds
                    and time.monotonic() >= deadline
                    and error.value.get("failure_kind") == "timeout"
                ):
                    return last
                error.value.update(
                    request_id=request_id, status_url=self.base_url + ARXIV_PREFIX + "/requests/" + request_id
                )
                raise
            last = value
            if value.get("state") != "queued" or time.monotonic() >= deadline:
                return value
            time.sleep(min(value.get("retry_after_seconds") or 3, max(0, deadline - time.monotonic())))

    def arxiv_read(self, paper_id, version, format="markdown", cursor=None, render_id=None, limit=12000):
        return self.request(
            "/papers/"
            + self.arxiv_paper_id(paper_id)
            + "/versions/"
            + self.arxiv_version(version)
            + "/content",
            params={"format": format, "cursor": cursor, "render_id": render_id, "limit": limit},
            prefix=ARXIV_PREFIX,
        )

    def arxiv_download(self, paper_id, version, kind, output):
        if kind not in ("pdf", "html", "source"):
            raise ClientError({"error": "invalid_resource_kind"})
        target = Path(output).expanduser()
        if target.exists():
            raise ClientError({"error": "output_exists"})
        url = (
            self.base_url
            + ARXIV_PREFIX
            + "/papers/"
            + self.arxiv_paper_id(paper_id)
            + "/versions/"
            + self.arxiv_version(version)
            + "/files/"
            + kind
        )
        temporary = None
        try:
            import hashlib

            with urlopen(
                Request(url, headers={"Accept": "application/pdf" if kind == "pdf" else "*/*"}), timeout=45
            ) as response:
                media = response.headers.get_content_type()
                if kind == "pdf" and media != "application/pdf" or media == "application/json":
                    raise ClientError({"error": "invalid_download_response"})
                expected = response.headers.get("Content-Length")
                if expected is not None and not expected.isdigit():
                    raise ClientError({"error": "invalid_download_response"})
                sha = hashlib.sha256()
                count = 0
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    while chunk := response.read(1024 * 1024):
                        count += len(chunk)
                        if count > 512 * 1024 * 1024:
                            raise ClientError({"error": "download_size_limit"})
                        stream.write(chunk)
                        sha.update(chunk)
                if not count or expected is not None and count != int(expected):
                    raise ClientError({"error": "incomplete_download"})
                os.link(temporary, target)
            return {
                "url": url,
                "media_type": media,
                "bytes": count,
                "sha256": sha.hexdigest(),
                "saved_to": str(target.resolve()),
                "paper_version": version,
                "kind": kind,
            }
        except FileExistsError:
            raise ClientError({"error": "output_exists"}) from None
        except HTTPError as error:
            raise ClientError(
                {
                    "error": "resource_not_ready" if error.code == 409 else "download_failed",
                    "http_status": error.code,
                },
                error.code,
            ) from None
        except (URLError, TimeoutError, OSError):
            raise ClientError({"error": "download_failed"}) from None
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def capabilities(self):
        return self.request("/capabilities")

    def search(self, query="", **filters):
        return self.request("/papers", params={"q": query, **filters})

    def search_unified(self, query="", **filters):
        return self.request("/search", params={"q": query, **filters})

    @staticmethod
    def number(value):
        if not isinstance(value, str) or not re.fullmatch("[0-9]{1,64}", value):
            raise ClientError({"error": "invalid_number"})
        return value

    def paper(self, number):
        return self.request("/papers/" + self.number(number))

    def ensure(self, number, resources=None, wait_seconds=10, retry=False):
        return self.request(
            "/papers/" + self.number(number) + "/ensure",
            data={
                "resources": resources or ["content"],
                "wait_seconds": wait_seconds,
                "client_id": self.client_id,
                "channel": "api",
            },
        )

    def status(self, request_id, wait_seconds=0):
        if not re.fullmatch("[a-f0-9]{32}", request_id):
            raise ClientError({"error": "invalid_request_id"})
        if not 0 <= wait_seconds <= 30:
            raise ClientError({"error": "invalid_wait_seconds"})
        deadline = time.monotonic() + wait_seconds
        last = None
        while True:
            remaining = deadline - time.monotonic()
            if wait_seconds and remaining <= 0 and last is not None:
                return last
            try:
                value = self.request(
                    "/requests/" + request_id, timeout=max(0.001, remaining) if wait_seconds else 45
                )
            except ClientError as error:
                # Exhausting our polling budget does not invalidate the last
                # pending receipt. Other transport and HTTP errors stay visible.
                if (
                    last is not None
                    and wait_seconds
                    and time.monotonic() >= deadline
                    and error.value.get("failure_kind") == "timeout"
                ):
                    return last
                error.value.update(
                    request_id=request_id, status_url=self.base_url + PREFIX + "/requests/" + request_id
                )
                raise
            last = value
            if not value.get("pending") or time.monotonic() >= deadline:
                return value
            time.sleep(min(value.get("retry_after_seconds") or 2, max(0, deadline - time.monotonic())))

    def read(self, number, format="markdown", cursor=None, version=None, limit=12000):
        return self.request(
            "/papers/" + self.number(number) + "/content",
            params={"format": format, "cursor": cursor, "version": version, "limit": limit},
        )

    def pdf(self, number, wait_seconds=10, output=None):
        value = self.ensure(number, ["pdf"], wait_seconds)
        if value["resources"]["pdf"]["state"] == "ready":
            if output:
                value["download"] = self.download(number, output)
                return value
            try:
                value["download"] = self.request("/papers/" + self.number(number) + "/pdf", method="HEAD")
            except ClientError as error:
                value["download_error"] = error.value
        return value

    def download(self, number, output):
        target = Path(output).expanduser()
        if target.exists():
            raise ClientError({"error": "output_exists"})
        url = self.base_url + PREFIX + "/papers/" + self.number(number) + "/pdf"
        temporary = None
        try:
            with urlopen(Request(url, headers={"Accept": "application/pdf"}), timeout=45) as response:
                if response.headers.get_content_type() != "application/pdf":
                    raise ClientError({"error": "invalid_pdf_response"})
                length = response.headers.get("Content-Length")
                if length is not None and not length.isdigit():
                    raise ClientError({"error": "invalid_pdf_response"})
                expected = int(length) if length is not None else None
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    count = 0
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
                        count += len(chunk)
                if count <= 5 or expected is not None and count != expected:
                    raise ClientError({"error": "incomplete_download"})
                # Linking publishes atomically and refuses a concurrently created target.
                os.link(temporary, target)
            return {
                "url": url,
                "media_type": "application/pdf",
                "bytes": count,
                "saved_to": str(target.resolve()),
            }
        except FileExistsError:
            raise ClientError({"error": "output_exists"}) from None
        except (URLError, TimeoutError, OSError):
            raise ClientError({"error": "download_failed"}) from None
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Site origin; alternatively set CIRDC_BASE_URL")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    search = commands.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    for flag in ("field", "sort", "kind", "venue", "venue-tags", "author-id", "author-source", "cursor"):
        search.add_argument("--" + flag)
    for flag in ("limit", "year-from", "year-to"):
        search.add_argument("--" + flag, type=int)
    commands.add_parser("paper").add_argument("number")
    ensure = commands.add_parser("ensure")
    ensure.add_argument("number")
    ensure.add_argument("--resources", nargs="+", choices=["content", "pdf"], default=["content"])
    ensure.add_argument("--wait-seconds", type=float, default=10)
    ensure.add_argument("--retry", action="store_true")
    status = commands.add_parser("status")
    status.add_argument("request_id")
    status.add_argument("--wait-seconds", type=float, default=0)
    read = commands.add_parser("read")
    read.add_argument("number")
    read.add_argument("--format", choices=["markdown", "text", "html"], default="markdown")
    read.add_argument("--version")
    read.add_argument("--cursor")
    read.add_argument("--limit", type=int, default=12000)
    pdf = commands.add_parser("pdf")
    pdf.add_argument("number")
    pdf.add_argument("--wait-seconds", type=float, default=10)
    pdf.add_argument("--output")
    arxiv_search = commands.add_parser("arxiv-search")
    arxiv_search.add_argument("query")
    arxiv_search.add_argument("--cursor")
    arxiv_search.add_argument("--limit", type=int, default=20)
    commands.add_parser("arxiv-resolve").add_argument("identifier")
    commands.add_parser("arxiv-paper").add_argument("paper_id")
    commands.add_parser("arxiv-versions").add_argument("paper_id")
    for name in ("arxiv-resources", "arxiv-ensure", "arxiv-read", "arxiv-download"):
        command_parser = commands.add_parser(name)
        command_parser.add_argument("paper_id")
        command_parser.add_argument("--version", type=int, required=True)
        if name == "arxiv-ensure":
            command_parser.add_argument("--retry", action="store_true")
        if name == "arxiv-read":
            command_parser.add_argument("--format", choices=["markdown", "text", "html"], default="markdown")
            command_parser.add_argument("--cursor")
            command_parser.add_argument("--render-id")
            command_parser.add_argument("--limit", type=int, default=12000)
        if name == "arxiv-download":
            command_parser.add_argument("--kind", choices=["pdf", "html", "source"], required=True)
            command_parser.add_argument("--output", required=True)
    arxiv_status = commands.add_parser("arxiv-status")
    arxiv_status.add_argument("request_id")
    arxiv_status.add_argument("--wait-seconds", type=float, default=0)
    unified = commands.add_parser(
        "search-unified", help="Search IEEE and arXiv together with RRF/chronological merging"
    )
    unified.add_argument("query", nargs="?", default="")
    unified.add_argument("--sources", default="ieee,arxiv")
    unified.add_argument("--field", default="all")
    unified.add_argument("--sort")
    unified.add_argument("--limit", type=int, default=20)
    unified.add_argument("--year-from", type=int)
    unified.add_argument("--year-to", type=int)
    unified.add_argument("--venue")
    unified.add_argument("--venue-any")
    unified.add_argument("--category")
    unified.add_argument("--cursor")
    updates = commands.add_parser(
        "updates", help="Check releases or defer/skip/disable update prompts; never installs"
    )
    updates.add_argument(
        "action", nargs="?", default="status", choices=["status", "snooze", "skip", "disable"]
    )
    updates.add_argument("--hours", type=int, default=24)
    updates.add_argument("--version", help="Exact version to skip")
    args = vars(parser.parse_args(argv))
    command, base_url = args.pop("command"), args.pop("base_url")
    try:
        client = Client(base_url, check_updates=command != "updates")
        value = getattr(client, command.replace("-", "_"))(**args)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except ClientError as error:
        print(json.dumps(error.value, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
