# CIRDC-Pro agent contract

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
