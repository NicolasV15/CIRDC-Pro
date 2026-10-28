# New computer and target selection

Run from the CIRDC-Pro checkout. Missing `.venv` means run `sh tools/setup.sh`.
Also rerun setup after pulling or changing code, to refresh the regular installation.
This uses a private Python environment and does not require global agent changes.
The root READMEs contain the same user-facing command examples in both languages.

1. Check `CIRDC_CONFIG` and `.cirdc/active-target` without printing profile contents.
   If neither identifies the intended target, inspect available SSH aliases or ask
   the user for the target alias/database and JSON location. Do not infer a target
   from repository history or choose an unrelated existing application database.
2. For an existing server, run `target-init --ssh ALIAS --remote-config PRIVATE_PATH
   --output ~/.config/cirdc/targets/NAME.json`. It retrieves the application settings
   through SSH, checks the database, and saves secrets only in that private file.
   For local/direct access use `config-init` in the user's terminal, or a private
   profile plus externally supplied secret environment variables. Passwords belong
   in the terminal, not questions in chat or command arguments.
3. Run `--config PROFILE db-check --json`. `ready` permits work. `empty` or
   `empty_template` requires authorized `db-init`; `legacy_requires_adoption`
   requires authorized `db-init --adopt`. Other states require investigating the
   target; never repair them by deleting data or suppressing validation.
4. Run `--config PROFILE target-select --project PROJECT_ROOT`, then `doctor --json`.
   Selection binds the verified database UUID and saves an ignored local pointer.
   `doctor --network` is an optional small source probe after validation succeeds.
5. Inspect `plan` and use the requested publication/year/stage for an initial
   bounded update. Reuse existing import checkpoints; shared catalogs do not need
   copying to the client. Track the job with `status`, then resume/retry only as
   needed. For a complete authorized run, remove a test task budget deliberately.
   An entirely empty collection must first run `update --stage catalog` to seed
   its complete catalog baseline. Track/resume that job rather than replacing it
   with a narrow catalog job and assuming historic coverage. Do not request a
   publication-specific enrichment until that publication appears in the catalog.

A new empty local database can be provisioned with the installed project Python
and `tools/bootstrap_mysql.py --output PRIVATE_PROFILE --data-root PRIVATE_DIRECTORY`
against an already running MySQL/MariaDB service. This requires administrator
credentials entered locally. It refuses an existing database. Do not reset root
passwords, restart shared services, or create broad-access accounts as a workaround.
The DDL-only `database/schema.sql` is available for manual provisioning.

Project MCP starts via `sh tools/cirdc mcp` and uses the selected target. Launch
Codex with `sh tools/codex.sh` or Claude Code with `sh tools/claude.sh` when the
client needs explicit project context. Keep the client's workspace trust flow.
