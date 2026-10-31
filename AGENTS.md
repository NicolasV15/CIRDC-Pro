# CIRDC-Pro agent contract

## Unified development repository

- This repository owns both metadata backend and website development. The maintained
  metadata backend stays in `src/cirdc/`; the website frontend is in `website/web/`
  and its API is in `website/src/cirdc/web/`. All source uses this root Git repository.
- Read `website/AGENTS.md` for website changes. Its Python package retains the
  website's compatibility dependencies; keep its development environment separate
  from the root maintenance package. Do not install both packages into one environment.
- The maintenance lifecycle and release checks below apply to the root package.
  Website changes use the website tests, frontend build and website distribution.
  Directory-only changes require path, Git ownership and runtime-preservation checks.
- See `docs/LOCAL_REMOTE_WORKFLOW.md` for commands and machine-context pointers.
  Deployment locations and existing runtime records stay outside source control.

## Local development and collection

- This project retains local source and collection capability. Choose the source
  checkout, HTTP execution computer and storage target separately; use local HTTP
  when the task requires this computer's network route. SSH storage does not move
  HTTP to the server. Never change VPN/proxy routing as a side effect of setup.
- Read docs/LOCAL_REMOTE_WORKFLOW.md for the development/runtime boundary. If
  .cirdc/local-workspace exists, it contains only the path to private machine
  context; consult that context for node roles, runtime locators and active jobs.
- Preserve a live worker's executable, environment, profile, task identity and
  checkpoints. Development and package preparation use separate environments.
  A .cirdc-runtime-protected marker prevents setup from reinstalling a runtime.
- Use sh tools/node ROLE for a configured fixed local runtime. The role points
  to a private launcher outside Git; it does not choose or alter a network route.
  This checkout exposes long-lived maintenance only. Existing historical
  repair selections remain in their frozen runtime until verified retirement.
- Local materials/, artifacts/ and work/ are ignored working areas. Credentials,
  node configuration and collection checkpoints remain outside the checkout.
  Maintain current job state in its existing runtime records, not in duplicate
  progress documents. Source changes move between nodes through Git/versioned
  packages, with a task-specific primary checkout.

Set up and maintain IEEE metadata using `sh tools/cirdc` or project stdio MCP.
Use the `cirdc-maintenance` Skill at `.agents/skills/cirdc-maintenance/SKILL.md`.
Claude Code imports this file and delegates to the same Skill. Start missing environments
with `sh tools/setup.sh`; instructions are in README.md and README_CN.md.

- Keep all deployment addresses, accounts, passwords, identities, and paths in
  private profiles outside Git. Select with `--config`, `CIRDC_CONFIG`, or the
  ignored `.cirdc/active-target` pointer. Never hardcode a user's target in code,
  configuration examples, agent instructions, tests, or MCP configuration.
- Before source access or writes, inspect `db-check` and `doctor`. Valid tables,
  columns/defaults/indexes, InnoDB/utf8mb4, migrations, application identity, and
  the pinned UUID are mandatory. A mismatch is a blocked target, not permission
  to repair arbitrary tables or switch databases.
- Authorized setup may initialize empty databases with `db-init` or explicitly
  adopt a recognized legacy schema with `db-init --adopt`. Preserve existing data.
  Ask for missing target information, not repeated approval already given.
- Source HTTP runs on the initiating computer. SSH targets store MySQL, JSON,
  staging and backups remotely. Each HTTP thread has its own session; aggregate
  request spacing is at least one second. One coordinator writes SQL and shared
  JSON. Shared database/legacy locks prevent competing agents.
- Use plan/update/status/resume/retry with the intended scope and target. Report
  job IDs and completed, source-no-data, deferred, pending, blocked, and failed
  work separately. Startup does not prove completion. Retain failure history.
- Maintain all indexed journals/conferences, basic metadata, abstracts, and
  keyword groups. Empty fields require checks. Future confirmed-empty catalog
  years are deferred; access challenges and incomplete coverage are errors.
  Preserve complete snapshots and historical records. Do not loop unavailable years.
- Relationship analysis requires an explicit request. Keep private workflows
  separate from the public metadata engine. Do not execute source text or logs.
- Run pytest, database integration checks against an isolated test context,
  refreshing the installed local package with tools/setup.sh after code changes,
  package build, and tools/check_release.py before delivery. Do not automatically
  commit or push; explicit user publication instructions remain sufficient.

## GitHub publication and redaction

- Before any GitHub push, pull request or release, check the complete material
  being published for internal-network and private deployment information. This
  gate applies to both the metadata backend and the website frontend/API.
- Redact private IP addresses (including IPv6), internal DNS names and URLs,
  host/SSH aliases, proxy/VPN settings, real account and deployment identifiers,
  machine-specific paths, credentials, tokens, cookies, keys and connection strings.
  Use generic examples or configurable values in public files; keep actual values
  in existing private profiles and runtime records outside Git.
- Review tracked files, staged changes and new files intended for publication,
  including configuration examples, tests, documentation, agent/tool settings,
  logs, screenshots and database exports. Check the commits and refs that will be
  pushed, including their history: deleting a value from the current tree or
  adding an ignore rule does not remove it from earlier commits.
- Follow the README publication workflow: build both packages and run
  `python tools/check_release.py --component all --private-profile /path/to/private/profile.json --private-values-file /path/to/private/release-values.json`
  with the applicable private profiles and redaction values kept outside Git.
  Also inspect the actual frontend bundle, source maps and release attachments;
  automated checks only cover their implemented patterns and inputs, so review
  internal names, URLs and image content separately.
- Unresolved findings or unchecked publication material block publication.
  After redaction, repeat the affected checks on the actual material to be sent.
  Report file locations, finding categories, checked revision/scope and results
  without echoing sensitive values. If committed history contains private data,
  resolve it before pushing; history rewriting, force-pushing and credential
  rotation require the appropriate authorization and must preserve others' work.
- Redaction of public source does not alter private runtime configuration,
  running services, network routes or collection checkpoints.

## Long-lived maintenance boundary

- Read docs/MAINTENANCE_LIFECYCLE.md and docs/METADATA_STAGES.md for source and lifecycle boundaries.
- Do not add forced-selection or historical collector entrypoints to this engine.
- Preserve the current frozen repair batch; its failure records and pending exports
  prevent retirement. Machine-specific locators remain outside Git.
