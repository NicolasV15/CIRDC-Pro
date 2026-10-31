# CIRDC-Pro Website

[English](README.md) | [简体中文](README_CN.md) | [Project overview](../README.md)

The website turns the CIRDC metadata collection into a searchable research library.
This directory contains its React frontend and Python API, managed by the parent
repository's Git. Use the [root metadata engine](../README.md#metadata-backend) for
long-lived collection; this package includes the compatibility modules needed by
the website's existing administration workflows.

## Reader and administrator features

| Interface | Features |
| --- | --- |
| Search | Title, author, keyword and abstract search; DOI/article-number lookup; year, publication and curated venue-family filters; adjustable page sizes |
| Paper details | Ordered author links, exact source-ID searches, abstracts, classified keywords and original-source links |
| Citations | BibTeX, IEEE and GB/T 7714 formats; copy/download; individual or selected-result export |
| Presentation | Chinese/English UI, six appearance presets and system mode, responsive layouts and KaTeX titles |
| Administration | Account management, update plans/jobs/logs, index status and preflight, optional resource settings |
| Optional reading resources | Provider-supplied cached bodies, chapter navigation, local PDFs and verified batch archives |

The public installation supplies metadata browsing. Reading resources require an
explicitly configured provider and available files/content. Missing resources are
reported separately. Author identity browsing uses the existing index; optional
profile acquisition is an explicit single-author operation.

## How the website fits together

| Source | Role |
| --- | --- |
| [web/src/](web/src/) | React + TypeScript reader and administration pages |
| [src/cirdc/web/app.py](src/cirdc/web/app.py) | Starlette API, reader/admin routes and static assets |
| [src/cirdc/web/index.py](src/cirdc/web/index.py) | SQLite FTS5 search projection, backfill and incremental synchronization |
| [src/cirdc/web/auth.py](src/cirdc/web/auth.py) | Argon2 password hashes, sessions and account audit |
| [tests/](tests/) / [web/tests/](web/tests/) | Python/API and frontend tests |
| [deploy/](deploy/) / [tools/deploy_web.sh](tools/deploy_web.sh) | Service templates and release/rollback workflow |

Paper details read MySQL/MariaDB directly. Search reads a derived SQLite index.
The indexer backfills existing records and consumes versioned database changes,
committing the search projection before acknowledging each event. Account and index
state live outside the source tree, selected by `CIRDC_WEB_STATE`.

Reader and administrator applications use separate route tables and sessions.
Administrator serving is restricted to loopback; writes require administrator
authentication, same-origin checks and a session CSRF token.

## Local setup

All commands below run from the **repository root**, unless stated otherwise.
Use Python 3.12, uv, Node.js 22.12+ and npm. The metadata database must already
be initialized and verified through the root package. Keep this environment
separate from the root `.venv`; both packages import `cirdc`.

### 1. Install and build

```sh
sh tools/web setup
sh tools/web build
uv pip install --python website/.venv-dev/bin/python \
  --reinstall-package cirdc-pro --no-deps ./website
```

Setup installs the website's `dev,web` extras in `website/.venv-dev` and installs
frontend dependencies. Build runs TypeScript checking and Vite, then produces a
wheel and source archive under `website/dist/`. The final command refreshes the
regular development install so it serves the newly built assets. Repeat it after
source/asset changes, or use a deliberately configured editable development install.

### 2. Configure storage and private state

Create a private profile using [config.example.json](config.example.json).
Configure a MySQL endpoint reachable from the website host, its dataset path and
runtime paths. Root maintenance SSH profiles are not automatically translated by
the website's configuration loader; provide the reachable endpoint or an existing
tunnel explicitly.

```sh
export CIRDC_CONFIG=/path/to/private/website.json
export CIRDC_WEB_STATE="$HOME/.local/state/cirdc-web-dev"
```

Use the same values in each terminal below. Keep state on local storage; it contains
the account/session database, search index and indexer checkpoints. Initial search
backfill requires at least 20 GiB free on the index volume.

### 3. Initialize accounts and run the indexer

For a **new** website state directory:

```sh
website/.venv-dev/bin/python -m cirdc.cli web init-users --username admin
```

This prompts for an initial password and creates the explicitly named administrator.
Alternatively, omit `--username` and define `web.bootstrap_users` in the private
profile as a list of `{"username": "admin", "role": "admin"}` and reader entries.
At least one administrator is required. Actual server account lists stay private.
Further accounts are managed by the authenticated administrator.
Existing accounts are preserved; website accounts are independent of OS accounts,
and first login requires a password change.

Run the indexer in its own terminal:

```sh
website/.venv-dev/bin/python -m cirdc.cli web index
```

It builds/resumes the index and then continues consuming changes. `--max-rows N`
limits the initial backfill; `--once` exits after the initial backfill, if needed,
and one incremental/author-backfill pass. A bounded or partial index does not
establish complete search coverage. Indexing installs its database capture/queue
support but does not start IEEE collection.

### 4. Start the reader and administrator

In separate terminals, with the same private profile and state:

```sh
sh tools/web serve --interface reader --host 127.0.0.1 --port 18090
```

```sh
sh tools/web serve --interface admin --host 127.0.0.1 --port 18091
```

Open [the reader](http://127.0.0.1:18090/) and
[administration](http://127.0.0.1:18091/admin/). These are local development ports.

The reader requires sign-in by default. `CIRDC_WEB_READER_AUTH=public` enables
anonymous, read-only reader access; administrator authentication remains required.
Keep the administrator on loopback and use an authorized tunnel when accessing it remotely.

## Tests and packages

From the repository root:

```sh
sh tools/web test
sh tools/web build
```

For the Python suite with database integration, run inside the website directory:

```sh
cd website
CIRDC_INTEGRATION=1 CIRDC_CONFIG=/path/to/private/website-test-profile.json \
  .venv-dev/bin/python -m pytest
```

Integration fixtures use connection-local temporary tables and isolated test paths;
select a verified isolated test context. The website wheel includes built frontend
assets. The root maintenance distribution is built and checked separately.
Node.js is required for frontend development/building; serving a built wheel uses Python.

## Deployment and further guides

For an **existing configured deployment**, the root command is:

```sh
CIRDC_WEB_ROOT=/path/to/existing/deployment sh tools/web deploy RELEASE_ID
```

This is a release operation, separate from local setup. It requires existing private
state, services and a rollback wheel. The workflow builds a source snapshot before
stopping services, installs the wheel offline, preserves dependency/provider versions,
and restores the prior release if activation checks fail. Website deployment does
not start or resume metadata maintenance.

- [Project overview and metadata backend](../README.md)
- [Shared development/runtime workflow](../docs/LOCAL_REMOTE_WORKFLOW.md)
- [Website behavior, search consistency and deployment](docs/web.md)
- [Explicit single-author profiles](docs/authors.md)
- [CC BY 4.0 license](LICENSE) and [upstream attribution](../README.md#attribution)

Keep credentials, deployment profiles, account state, indexes and document stores
outside Git.
