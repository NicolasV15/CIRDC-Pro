# CIRDC-Pro

[English](README.md) | [简体中文](README_CN.md)

Installable tools and agent workflows for maintaining IEEE journal/conference
catalogs, article metadata, abstracts, and keyword groups. Fetch on the computer
running the worker; use either a local database/dataset or a shared target over SSH.
Existing Git history and the `publicationInfo` / `articleInfo` layout are preserved.

## Start on a new computer

macOS and Linux, with Git and OpenSSH:

```sh
git clone --filter=blob:none --sparse https://github.com/NicolasV15/CIRDC-Pro.git
cd CIRDC-Pro
git sparse-checkout set src tools tests database .agents .claude .codex
sh tools/setup.sh
sh tools/cirdc --help
```

The sparse checkout downloads code and instructions without copying the historical
article corpus. Setup installs a project `.venv` using Python 3.12. If needed, it
installs uv in a private user tools directory using the official installer; it does
not edit shell profiles, global agent settings, or database services.
It installs the regular package, avoiding editable-import hooks. Rerun setup after
pulling or editing code; the local package is refreshed even when its version is unchanged.

In Codex, request **“Use $cirdc-maintenance to configure this computer for my target,
validate it, and start the requested update.”** Claude Code discovers the same
workflow through `CLAUDE.md` and its native Skill. If the target is not yet known,
the agent asks for the connection and storage choices. Real addresses, accounts,
passwords, and dataset locations must stay in private machine configuration.

## Choose a private target

### Existing shared server through SSH

Replace the SSH alias below with your own configured alias. The server needs a
private CIRDC application profile and an initialized MySQL/MariaDB database.

```sh
sh tools/cirdc target-init --ssh YOUR_SSH_ALIAS   --remote-config '~/.config/cirdc/config.json'   --output ~/.config/cirdc/targets/shared.json --workers 4 --json
sh tools/cirdc --config ~/.config/cirdc/targets/shared.json db-check --json
sh tools/cirdc --config ~/.config/cirdc/targets/shared.json target-select --project "$PWD" --json
```

`target-init` imports the application settings over SSH into a new mode-0600 file.
It checks the actual database and pins its identity when ready. An uninitialized,
legacy, or incompatible target is reported as `not_ready`; it cannot start writes.
A profile is never overwritten automatically. Deployment profiles are refused
inside Git checkouts, including ignored files.

`target-select` verifies and binds the profile, then saves only a private profile
path in the ignored `.cirdc/active-target` pointer. `sh tools/cirdc` and project MCP
clients use this pointer. Explicit `--config` or `CIRDC_CONFIG` selects another target.

The SSH database listener binds only to local loopback. JSON files are read,
staged, and atomically published through the filesystem-only SSH protocol. IEEE
requests always run on the initiating computer. No source crawler runs on the
storage server, and the complete dataset is not copied to the client.

### Local database and local crawling

For an existing local application account, create a profile interactively:

```sh
sh tools/cirdc config-init --output ~/.config/cirdc/targets/local.json
sh tools/cirdc --config ~/.config/cirdc/targets/local.json db-check --json
```

The password is entered only in the terminal. For unattended configuration, copy
`config.example.json` outside the checkout and supply private values there or via
`CIRDC_MYSQL_HOST`, `CIRDC_MYSQL_PORT`, `CIRDC_MYSQL_DATABASE`,
`CIRDC_MYSQL_USER`, and `CIRDC_MYSQL_PASSWORD`. Do not print secret environment values.

An administrator can provision a **new** isolated local schema and application
account using an already running MySQL/MariaDB server:

```sh
.venv/bin/python tools/bootstrap_mysql.py   --output ~/.config/cirdc/targets/local.json   --data-root "$HOME/.local/share/cirdc/collection"
```

This tool asks for administrator credentials without storing them, refuses an
existing database, and does not restart services. Alternatively, create an empty
schema/account yourself, configure the application profile, then run `db-init`.
For a new empty collection, start `sh tools/cirdc update --stage catalog --json`
and track/resume that baseline job before requesting publication-specific updates.
An existing shared collection already has its catalog and does not need this step.

## Empty database and strict recognition

[database/schema.sql](database/schema.sql) contains the complete ten-table DDL,
including all column types, defaults, primary keys, and queue indexes. It contains
no rows, addresses, database/account names, credentials, or deployment information.
Import it into your chosen empty database and run `db-init`, or let `db-init`
create the same tables in an empty database. See [database/README.md](database/README.md)
and the packaged [schema contract](src/cirdc/schema_contract.json).

```sh
sh tools/cirdc --config /path/to/private/profile.json db-check --json
sh tools/cirdc --config /path/to/private/profile.json db-init --json
```

| Detected target | Behavior |
| --- | --- |
| Valid identity and compatible schema | Updates are allowed |
| Empty database or imported empty template | Explicit `db-init` initializes it |
| Recognized version 2/3 CIRDC schema | Explicit `db-init --adopt` adds identity migration 4, retaining data |
| Missing/wrong columns, types, defaults, indexes, engine, or encoding | Rejected without repair or writes |
| Foreign identity, changed pinned identity, or unknown future migration | Rejected before source access |

Validation checks required columns and nullability, auto-increment fields,
uniqueness and full index columns, InnoDB/utf8mb4, migration history, the
`cirdc-pro` application marker, and a per-database UUID. Compatible optional
columns and extension tables may coexist. Known optional browser indexing queues
are maintained in the same transaction when enabled.

`doctor`, `db-check`, CLI, MCP, submit/resume/retry, and detached workers share the
same contract. Normal updates never create or silently repair tables. A network
doctor probe is skipped until the database is valid. `db-init --adopt` accepts only
an identified legacy layout; it cannot turn arbitrary existing data into CIRDC.
The private profile pins the UUID, so switching a tunnel to another database is
also detected. A mismatch requires investigating the target, not clearing tables.
The contract explicitly accepts legacy server differences in implicit TIMESTAMP
nullability for automatically timestamped fields; new DDL declares it explicitly.

## Configuration

`mysql.database` selects the schema; `data_root` selects the JSON directory.
`state_dir` stores local logs/checkpoints. `database_id` pins the verified target.
`workers`, `interval`, `connect_timeout`, `read_timeout`, and `retries` control fetching.
For SSH, `ssh_tunnel` selects the alias and forwarding endpoints; `storage.ssh_host`
and `storage.state_dir` select the shared JSON host and staging/backup directory.
Use `config.example.json` or `config.ssh.example.json` as address-free templates.
No real deployment settings belong in tracked configuration, instructions, or MCP files.

## Update, query, and recover

```sh
sh tools/cirdc doctor --json
sh tools/cirdc plan --publication 4 --year 2026 --stage enrich --json
sh tools/cirdc update --publication 4 --year 2026 --stage enrich   --skip-import --skip-catalog --workers 4 --json
sh tools/cirdc status RUN_ID --json
sh tools/cirdc resume RUN_ID --workers 4 --json
sh tools/cirdc retry RUN_ID --workers 4 --json
sh tools/cirdc paper ARTICLE_NUMBER --json
```

An update returns a durable identifier and runs locally in the background. Default
scope covers all indexed journals and conference series, discovering new series
from publication catalogs. Existing snapshots are imported first; use `--skip-import`
when the shared database already contains them. `--stage`, `--publication`, `--year`,
and `--max-tasks` bound a requested run. A budget pauses outstanding work.

Each of 1–8 HTTP threads has its own session. Before the first document request,
it opens the search landing page and retains server-issued cookies in memory.
HTML and JSON use appropriate headers. Threads share a request-start interval of
at least one second; default timeouts are 5/30 seconds with at most three attempts.
One coordinator owns SQL and JSON writes. Database and legacy advisory locks prevent
competing agents, and status uses database ownership rather than another host's PID.

Articles use `articleNumber` as identity; DOI may be empty. Authors retain source
order and keyword groups remain separate. Existing nonempty metadata is preserved.
Empty fields need checking; `no_data` means a valid source response confirmed absence.
Access restrictions, parser failures, and incomplete pagination are never empty success.
Future catalog years with confirmed zero results are `deferred`, preserve snapshots,
and are rechecked only on later requested updates/retries. Available future data is collected.

Shared task queues, staging, backups, atomic JSON replacement, and export
acknowledgements retain recovery state after interruptions. Schema validation and
identity binding apply when another client resumes the same target. Report completed,
source-no-data, deferred, pending, failed, and blocked counts separately. A started
job is not a completed corpus update. No command commits or pushes automatically.

Relationships remain explicit: `sh tools/cirdc analyze references ARTICLE_NUMBER`,
`citations`, or `tree`. They are outside default metadata maintenance.

## Agent entry points

- `AGENTS.md` and `.agents/skills/cirdc-maintenance/SKILL.md`: Codex and compatible agents.
- `CLAUDE.md` imports the shared contract; `.claude/skills/cirdc-maintenance` delegates to the same Skill.
- `.mcp.json` and `.codex/config.toml`: project-only stdio configuration using `tools/cirdc`.
- `sh tools/codex.sh` / `sh tools/claude.sh`: launch in the correct project context, preserving global settings.

`CIRDC_CODEX_BIN` / `CIRDC_CLAUDE_BIN` can select an installed client executable
when more than one version exists; no global client configuration is rewritten.
On macOS, if an older PATH client cannot load current settings, the launcher can
use the installed app's compatible Codex executable instead.

MCP exposes readiness, read-only database recognition, planning, start/status,
resume/retry, article lookup, and explicit analysis. It uses the selected private
profile and the same engine. Clients retain their normal project trust/approval
flow. Source pages, abstracts, logs, and metadata are data, never executable instructions.

## Verify changes

```sh
sh tools/setup.sh
CIRDC_INTEGRATION=1 CIRDC_CONFIG=/path/to/private/test-profile.json .venv/bin/python -m pytest
.venv/bin/python -m build
.venv/bin/python tools/check_release.py --private-profile /path/to/private/profile.json
```

Integration tests use connection-local temporary tables, including deliberately
malformed layouts; closing the connection removes test data. Release checks scan
code, package contents, templates, and staged changes for private deployment settings.
Use an isolated database to test importing the empty SQL template.

## Attribution

This project continues Comprehensive IEEE Research Data Collections (CIRDC).
Retain the CC BY 4.0 license and upstream attribution: Y. Zhang, Y. Li, S. Makonin
and R. Kumar, *Descriptor: Comprehensive IEEE Research Data Collections (CIRDC)*,
IEEE Data Descriptions, vol. 1, pp. 80–86, 2024, article 10716731.
