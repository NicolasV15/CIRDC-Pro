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
directory. The application serializes submissions with a SQLite transaction; the
provider must also deduplicate active jobs and preserve failure state, including
when an HTTP response or receipt commit is interrupted. No new worker queue,
source crawler, scheduler or metadata schema is introduced. Keep this state file
with existing website state during upgrades and rollback.

Resources report independent availability and task states. Cached content remains
usable after another branch fails. A source access failure is not proof that a
publisher has no HTML. Any PDF fallback and later conversion retain the provider's
validated-absence rules. PDF downloads check actual readable files before streaming.

Public JSON endpoints support credential-free CORS. Limits apply to searches,
ensure calls and request bodies; they do not grant new source-request budgets.
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
| `agent_file(number, asset_id=None, version=None)` | Return a verified server-local `path` and `media_type` for streaming. An absent asset ID means the original PDF. Asset requests require a document version. Paths never enter client JSON. |

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
