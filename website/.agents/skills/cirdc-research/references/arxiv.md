# arXiv access (Skill 1.2.0)

Use the configured CIRDC site, not arxiv.org directly. No local database, account,
API key, parser or collector is required. Ordinary reads never acquire upstream
resources. Check `/api/agent/v1/capabilities`: `sources.arxiv.enabled` enables
metadata access and `resources_enabled` enables on-demand files/body operations.
An absent/disabled source or HTTP 404/503 is not permission to switch sites or
start maintenance. The old IEEE API/CLI continue unchanged.

## Identity and versions

Keep `source=arxiv`, internal `paper_id`, base `arxiv_id`, integer `paper_version`,
and body `render_id` distinct. `0704.0001v2`, `2402.08954v1` and
`hep-th/9901001v1` are arXiv identifiers, not IEEE article numbers. Resolve them
with GET `/api/arxiv/resolve?id=...`; official abs/pdf/src/html links are accepted.
A topic search uses GET `/api/arxiv/papers?q=...&limit=20&cursor=...` and searches
local title/authors/abstract/categories. Follow its own `next_cursor`; full-text
coverage is separate. Internal numeric IDs must never be sent to IEEE endpoints.

GET `/api/arxiv/papers/PAPER_ID` returns metadata and observed versions; GET
`/api/arxiv/papers/PAPER_ID/versions` returns the version list. Preserve an explicit
user version; otherwise select the highest observed version and record it. Do not
change it mid-read when metadata updates. Current titles/abstracts/licenses are
not guaranteed historical snapshots for each version. Preserve metadata coverage
notices, missing dates and missing evidence.

## Cached reading and explicit acquisition

All version-bound paths use `/api/arxiv/papers/PAPER_ID/versions/VERSION`:

| Method/path | Purpose |
| --- | --- |
| GET `/resources` | Original-resource states and cached document descriptor |
| GET `/content?format=markdown&limit=12000` | Cached body blocks; also supports text/html |
| POST `/ensure`, JSON `{}` | One deduplicated request for HTML, PDF, source and reading preparation |
| POST `/ensure`, JSON `{"retry":true}` | Explicitly retry unfinished eligible branches; never an automatic polling action |
| GET `/pdf/reader` | Same browser PDF reader as IEEE |
| GET/HEAD `/files/pdf`, `/files/html`, `/files/source` | Cached original only; HTML/source are attachments |

Task receipts use GET `/api/arxiv/requests/REQUEST_ID` (64 hex characters; IEEE
receipt IDs use their own 32-character format). For direct POST clients include
`Origin: SITE_ORIGIN`; use the site's ordinary Origin/CSRF contract if it is
configured for authenticated browser use. The bundled helper sends the origin.

For `/content`, follow every `next_cursor` needed by the user's scope. Subsequent
pages stay pinned to the original render; use `render_id` to explicitly read a
known render. The response includes `paper_version`, `render_id`, source, hash,
TOC, blocks, assets and warnings. Do not cut a TeX expression/table or silently
summarize only the first page. Body evidence is HTML, LaTeXML-derived, or PDF-derived;
report that source and cite the paper version/render/section. Relative assets are
local version-and-render-bound URLs. Do not replace a missing body with the
metadata abstract without disclosure.

`reading_ready=true` permits reading even while original acquisition continues.
`acquisition_complete=true` says file branches terminated, not that all succeeded.
Inspect `resources.html/pdf/source.state` independently. `state=queued` is pending;
`state=partial` is terminal and may still have a usable document/PDF. Confirmed
`unavailable`, `blocked`, and `failed` are distinct. Automatic retries are bounded
by the server; poll the saved receipt within the caller's time budget, then report
its ID and current states. Never resubmit ensure merely because a receipt is
partial or an HTTP request returned 200. If POST acceptance is unknown, inspect
`/resources` and its existing request ID before another submission.

The server prefers official HTML, then source via LaTeXML, then PDF via MinerU.
A successful body stops extra conversions while requested originals continue
caching. Source packages may contain TeX, other formats or no usable TeX; never
promise every paper/version has PDF, HTML or TeX. Downloading source does not
compile it on the AI host. Never request paid S3 or a full-text library crawl.

## MCP and standard-library helper

MCP tools on the existing `/api/agent/v1/mcp` connection:
`search_arxiv(q,cursor)`, `resolve_arxiv(identifier)`,
`get_arxiv_paper(paper_id)`, `get_arxiv_resources(paper_id,version)`,
`ensure_arxiv_resources(paper_id,version,retry=false)`,
`get_arxiv_request(request_id)`, and
`read_arxiv_content(paper_id,version,format,cursor,render_id,limit)`.
If a connected server lacks an advertised operation, use the documented HTTP
route when available; do not invent tool names or treat a source failure as empty.

Run from the installed Skill's actual folder; site configuration and update
behavior remain shared with IEEE:

```sh
python scripts/cirdc_client.py capabilities
python scripts/cirdc_client.py arxiv-search 'operational amplifier'
python scripts/cirdc_client.py arxiv-resolve '0704.0001v2'
python scripts/cirdc_client.py arxiv-versions PAPER_ID
python scripts/cirdc_client.py arxiv-resources PAPER_ID --version 2
python scripts/cirdc_client.py arxiv-read PAPER_ID --version 2 --format markdown
# Only when missing resources are requested:
python scripts/cirdc_client.py arxiv-ensure PAPER_ID --version 2
python scripts/cirdc_client.py arxiv-status REQUEST_ID --wait-seconds 10
python scripts/cirdc_client.py arxiv-read PAPER_ID --version 2 --cursor NEXT_CURSOR
python scripts/cirdc_client.py arxiv-download PAPER_ID --version 2 --kind pdf --output paper.pdf
python scripts/cirdc_client.py arxiv-download PAPER_ID --version 2 --kind html --output article.html
python scripts/cirdc_client.py arxiv-download PAPER_ID --version 2 --kind source --output source.bin
```

Replace IDs/version/cursor with returned values. `arxiv-download` reads cache only,
refuses an existing output, validates transfer length and computes SHA-256; it
never calls ensure. The chosen source filename is local; inspect the actual
returned format rather than assuming `.tex` or `.tar.gz`. Do not put binary data
into model context. These CLI additions do not change the existing IEEE commands.
