# Research agents and application integration

The running reader directly serves an unauthenticated `/api/agent/v1` API,
Streamable HTTP MCP at `/api/agent/v1/mcp`, `/developers/ai`, `/llms.txt`, and the
online Skill at `/api/agent/v1/skills/cirdc-research/SKILL.md`. No archive download,
extraction or local adapter process is required. This namespace is public, including on
sites whose ordinary browser reader requires a session. Administrator and worker
node endpoints retain their existing authentication. No client database access or
private package is required.

See the maintained [client reference](../.agents/skills/cirdc-research/references/api.md)
for HTTP, command-line and MCP examples. The running site's `/api/agent/v1/openapi.json`
contains request and response schemas. `GET /capabilities` reports actual installed
provider support; a public source installation alone cannot supply reading files.

Start the website through its existing reader entrypoint. MCP shares that process,
port and lifecycle, using the installed `mcp>=1.30,<2` SDK; there is no extra daemon
or deployment environment. Clients add the MCP URL in their AI host, or give an
HTTP-capable AI the online Skill URL. The MCP initialization instructions and
`cirdc://research/skill` resource also supply the workflow directly. Reading an
online Skill is guidance, not an automatic native Skill installation in the AI host.

The AI Access page presents two copyable Agent prompts. The first binds a native
Skill installation to the current browser origin and asks the Agent to verify
calls without a URL argument. For the second, users open an Agent conversation
in the desired working directory and copy the prompt. The Agent confirms its
current directory, clones the canonical repository, initializes a local deployment,
starts persistent services, and installs the Skill using the actual resulting URL.
That local-deployment prompt does not inherit this remote site's origin. The page
itself does not run an installer, deploy a service, or acquire resources.

MCP tools dispatch into the same application with the original connection peer,
so HTTP and MCP share validation, rate limits, queues and task-origin records.
There are no loopback network requests and no tool accepting arbitrary destination
URLs. Transport sessions are stateless; durable resource receipts survive a client
disconnect and can be queried through either interface. Administrator operations
and worker control are not MCP research tools. The transport uses the
[official SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).

## Resource requests

Search and detail reuse existing metadata handlers and filters. Unknown article
numbers return 404 before any resource submission. Only POST ensure can submit
work, and only for the selected article and resource types. It accepts JSON, waits
up to 10 seconds by default (0–30), then returns a durable receipt. GET requests,
including receipt polling, never ensure or retry. Requests share active work and
the same receipt for each article/resource set. Explicit retry updates that receipt
while retaining prior references; it does not replace the underlying failure history.

Receipts live in `agent-requests.sqlite` under the existing private website state
directory. The application serializes submissions using a nonblocking per-article file lock;
provider calls run outside short SQLite transactions. The provider must also deduplicate active jobs and preserve failure state, including
when an HTTP response or receipt commit is interrupted. No new worker queue,
source crawler, scheduler or metadata schema is introduced. Keep this state file
with existing website state during upgrades and rollback.

Resources report independent availability and task states. Cached content remains
usable after another branch fails. A source access failure is not proof that a
publisher has no HTML. Any PDF fallback and later conversion retain the provider's
validated-absence rules. PDF downloads check actual readable files before streaming.
The final PDF output boundary owns the lightweight signature check, shared by
GET, HEAD and Range downloads. Availability and registration do not repeat this
check. MCP reports the normal download endpoint's type and size; a download
failure is returned separately without changing a completed acquisition receipt.
The standalone client saves a PDF using one GET, checking that response's type
and received length without an extra HEAD or a second signature check.

Accepted ordinary source acquisition persists without a cumulative retry cap.
PDF-to-text conversion retains an independent bounded recovery policy. Pending
responses expose acquisition_id, phase, next_action=wait and polling guidance.
A conversion can end with failed/partial and next_action=contact_administrator or
stop. Its receipt can return HTTP 200, pending=false and complete=false; clients
must report the terminal resource outcome without automatically resubmitting.
Mixed receipts keep each resource independent and remain pending only while
another branch still needs waiting. A confirmed institutional non-entitlement is
a normal terminal no-PDF outcome. Provider hooks receive optional caller context;
GET never promotes or submits work.

Public JSON endpoints support credential-free CORS. Resource ensure has no
per-peer frequency quota; short transactions queue accepted work durably.
Search and unrelated metadata/relationship limits retain their own contracts.
Source egress spacing and capacity are independent of local admission.
The existing visit/task recorder associates accepted Agent requests with actual
returned queue identities. It does not record prompts, document contents or
invent associations from paper numbers and timestamps.

## Optional provider protocol

The website discovers only explicitly enabled `cirdc.web_resources` entry points.
Providers can implement the following synchronous hooks; handlers execute them in
the thread pool. The generic website never imports a private provider module.

| Hook | Contract |
| --- | --- |
| `agent_capabilities()` | Mapping with supported `content` and/or `pdf` booleans. Each resource must have one provider; ambiguity is an error. |
| `agent_snapshot(number, resource, reference=None)` | Read-only normalized status, optional opaque JSON `reference`, and verified `jobs` with ID, kind, state and explicit parent ID when known. With a reference, follow those actual jobs/dependencies; do not choose an unrelated newer attempt. |
| `agent_ensure(number, resource, rate_key, retry=False)` | Reuse cached/active resources; submit missing resources only. Failed or partial work requires explicit retry. Return the same normalized status with a durable reference. |
| `agent_document(number, version=None)` | Read cleaned HTML plus `version`, `source`, `toc`, `state`, `assets_ready` and `assets_total`. A supplied version must select exactly that immutable document. |
| `agent_document_catalog(cursor=None, limit=100)` | Optional, read-only. Return `items` with `number`, `version`, `state` (`ready`/`partial` bodies are indexed; other states remove passages) and optional `source`, plus an opaque resumable `cursor`, `more` and optional `total`. Later cycles must discover new/changed documents and removals. Providers may replay unchanged entries; the indexer skips matching indexed versions. A replayable sweep may return `cursor=null` only at its end (`more=false`), so the next cycle starts another sweep. Used only by `cirdc web fulltext-index`. |
| `agent_file(number, asset_id=None, version=None)` | Resolve a registered server-local `path` and `media_type` for streaming. The final HTTP PDF output checks readability and the lightweight signature. An absent asset ID means the original PDF. Asset requests require a document version. Paths never enter client JSON. |

Status fields are `state` (`missing`, `pending`, `ready`, `partial`, `unavailable`,
`failed`), `phase`, `reason`, `retryable`, optional `transient`, source/version,
file size/checksum, image counts, and `jobs`. Public responses use an explicit
allowlist. Opaque references stay in private receipt state. Do not put deployment
paths, credentials, nodes or leases in status fields. An exception can carry a
machine-readable `code` and HTTP `status`; generic exceptions become service errors.

Existing providers without these hooks keep their normal browser behavior but
do not advertise Agent capabilities. Provider upgrades follow their independent
release process. Preserve prior provider wheels and all queue/checkpoint files.

## Text and online instructions

HTML is read without a browser or source-network requests. Markdown preserves TeX,
captions and image references; tables remain HTML to retain cell spans. Plain text
reports table flattening. Complete blocks are paged against an exact document
version and hash; larger individual blocks are returned intact with a warning.
No cached source document is rewritten. Image availability can advance separately
while the body and its pagination remain version-pinned.

The Skill's single source is `.agents/skills/cirdc-research/`. Python wheel builds
include the Skill, its API reference and both standard-library scripts as package data; source
development reads the same canonical files. They are served without attachment
headers, archives or a frontend build dependency. `/llms.txt` and capabilities link
to these readable URLs. The frontend presents only the two Agent setup prompts;
detailed commands and API examples remain in the references for Agents to consult.
Fixed allowlisted script routes serve the installer
and HTTP helper as Python text; arbitrary filesystem paths are never exposed. An optional standard-library HTTP CLI remains in the source Skill
folder for developers who already use the checkout.

## Verification and release

Run website tests, frontend tests/build, affected provider tests and isolated
database integration checks. Client tests exercise a real local HTTP server and
remote MCP connection with synthetic resources, including reconnecting to a saved
receipt and preserving caller identity. Browser fixtures check desktop/mobile
layouts, complete prompt copying, use of the current conversation directory and language switching
without API or source requests. Validate the Skill with the skill-creator validator. Inspect the plain
Markdown package data, website distributions and actual frontend bundles with
the project's publication/redaction checks.

Source implementation and package preparation do not deploy services. An existing
site requires a deliberate website release and a compatible provider release
before these interfaces become live. Old browser endpoints and the maintenance
MCP remain compatible.

## Native Skill installation

The first AI Access prompt asks the Agent to perform the native installation for
its current host. The installer downloads the canonical Skill files into one user-owned cache
and creates host-specific symlinks, or links a developer's existing local checkout.
Site configuration stays in a private local JSON file, separate from source. This
is the same single-source pattern as an application's bundled Skill; it works
across projects and does not require a local CIRDC backend or MCP adapter.

From a source checkout, `sh tools/install-skill --agent all` links the source and
completes configuration at installation time. Explicit arguments, environment and
saved configuration take precedence; first terminal setup asks for a site with
`http://127.0.0.1:18088` as the local default. Scripted setup accepts `--base-url`
and `--non-interactive`. A bounded read-only capabilities check precedes config
and link changes. Installation failure preserves the previous setup.

`sh tools/install-skill --configure` selects and checks a site without changing
native Skill links. The runtime helper reads the saved configuration without
prompting or silently switching sites. Source or transferred-copy installations
can intentionally skip the network check with `--skip-check` and an explicit or
saved address; their result reports `connection_verified=false`. A checkout over
SSH can still supply a local Skill copy; this does not configure another user's home.

See the [installation, update and uninstall reference](../.agents/skills/cirdc-research/references/api.md#native-skill-installation)
for exact commands and paths. The installer preserves unrelated host entries and
never changes global agent settings, services or collection state. Online Skill
reading, native Skill discovery and remote MCP connection remain separate choices.

## Busy responses and time budgets

Read cached content first. Only `409 content_not_ready` permits ensure; if the
response supplies a receipt, query that receipt instead. A 503 is a service error,
not evidence of missing content. Preserve `message`, `next_action`,
`retry_after_seconds`, `request_id` and `status_url`. HTTP `Retry-After` matches
the JSON interval. A 429 interval reflects the remaining rate-limit window.
A confirmed unavailable PDF is terminal; pending acquisition continues through its receipt.

Ensure's processing budget is `wait_seconds + 10` seconds from validated parameters,
including metadata lookup and submission; `wait_seconds=0` has a ten-second budget
and does not wait for resource completion. Receipt/capabilities reads have a
ten-second budget; content JSON has ten seconds. These budgets exclude network
transfer and do not limit PDF/image streaming. Capabilities reports budgets and
internal bounded execution pools with queued admission. Resource ensure has no per-IP quota. Local execution pools are not acquisition-attempt limits.

On ensure errors, `accepted=true` means submission was confirmed, `false` means
not submitted, and `null` means unknown. Only a committed receipt is returned as a
receipt. When submission times out, the synchronous hook can still finish and save
its receipt; it retains its execution slot until completion. Without a receipt,
back off, read first, then resume an ordinary ensure with `retry=false` if needed.
Ensure is idempotent and needs no retry flag. Polling never submits work. Preserve usable content and original failure history.

`/healthz` checks website liveness; it does not report resource worker capacity.

## Independent research Skill releases

The canonical release metadata, compatibility, SHA-256 inventory and bilingual
notes live in `.agents/skills/cirdc-research/version.json`; this version is independent
of API and Python package versions. Run `python3 website/tools/skill_release.py`
from the repository root to check, or `--write` after choosing a new release version.
Wheel/sdist builds validate the inventory; online distribution and the AI access
dialog read that same manifest. Local checks use only that static endpoint and
never queue database, paper, PDF or maintenance work.

See [version rules, safe updates and a forwardable migration notice](../.agents/skills/cirdc-research/references/api.md#skill-version-and-updates).
Older local copies require one manual update; remote MCP/HTTP-only and ordinary
website users require no native Skill update. Use isolated fixtures for all update
failure/caching tests; never acquire papers to validate a version check.


## Durable resource acquisition

Accepted work survives disconnects and restarts. Poll the original receipt; failures are diagnostics, not an acquisition lifetime limit. PDF ready and confirmed unavailable are normal terminal outcomes. Use wait_seconds=0 for submission bursts. Stable client_id and channel provide fair scheduling between API callers and browser users.

## Research Skill 1.2.0: IEEE and arXiv

The canonical `cirdc-research` release now supports both sources without changing
existing IEEE commands or installation settings. `capabilities.sources` advertises
source configuration; older sites without that field remain IEEE-compatible.
arXiv uses its own internal paper ID, integer paper version and render identity,
with HTTP paths under `/api/arxiv` and source-specific MCP tools on the existing
MCP connection. The Skill's `references/arxiv.md` contains routing, state handling,
CLI examples and cached original-file downloads. A configured source does not
prove its metadata index or full-text coverage is complete.

arXiv's cached `/content` response uses the existing block-pagination contract,
pins cursors to paper version/render/hash, and validates source-specific asset
URLs. Reading never creates acquisition. One explicit arXiv ensure requests
HTML/PDF/source plus reading preparation; its terminal partial outcomes and
bounded retries are different from IEEE recovery. MathML without original TeX
is preserved as markup with a warning rather than guessed into LaTeX.
