# Single-author profiles / 单作者资料

The optional `authors` table lives beside `papers` in the configured database.
It is empty after initialization. No paper updates, indexing, page visits or
coauthor links initiate profile retrieval. No batches or schedules are installed.

## Commands

Use Python 3.12 in a dedicated environment (`uv sync --python python3.12`).
The CLI and stdio MCP share the same implementation.

```sh
cirdc doctor --json
cirdc author init --json
cirdc author fetch AUTHOR_ID --output author.json --json
cirdc author import author.json --json
cirdc author update AUTHOR_ID --json
cirdc author show AUTHOR_ID --json
```

`fetch` needs no database credentials. Run it on an allowed acquisition host,
then transfer only its sanitized JSON to the database host and run `import`.
`update` performs fetch and import for exactly one ID on the initiating host.
`show` is local-only. `init` checks the paper database and creates only `authors`;
it does not call paper migrations, modify paper rows or start a maintenance job.
All operations return versioned JSON; failed operations return a nonzero exit.
Use `--config FILE` or `CIRDC_CONFIG` for private deployment configuration.
Never place credentials, deployment identities or addresses in committed files.

MCP tools: `author_init`, `author_fetch(author_id, output)`, `author_import(path)`,
`author_update(author_id)`, `author_show(author_id)`. They never enumerate IDs.

## Table and portable format

- [SQL template](author-schema.sql), [column header CSV](author-columns.csv),
  [synthetic JSON example](author-example.json).
- Independent contract version: table comment `cirdc-author-schema:1`.
  The paper engine's `schema_migrations` remains unchanged. Existing incompatible
  author tables cause an error; no automatic alteration or data deletion occurs.
- Primary key: `(source, author_id)`, binary-collated strings, never numeric IDs.
  Same-name authors are separate; ORCID is nullable and not a unique merge key.
- Names and ORCID are nullable text. `current_affiliations_json`,
  `bio_paragraphs_json`, `coauthors_json`, `topics_json`, `publication_years_json`,
  `field_states_json` are MariaDB-compatible JSON encoded LONGTEXT. Lists preserve
  source order; coauthor IDs remain strings. Institutions are the source's
  reported current affiliations, not an independently verified employment history.
- `ieee_article_count`, `ieee_citation_count` are nullable unsigned BIGINT values;
  publication years are nullable unsigned SMALLINT. They are source observations,
  not counts of locally indexed papers. `is_hidden` is nullable boolean.
- `source_url`, `source_endpoint`, `fetched_at`, `parser_version`, `payload_sha256`
  and relative `snapshot_path` establish provenance. All timestamps are UTC.
- `fetch_state` is complete/hidden/blocked/failed; an absent row means not fetched.
  Per-field states distinguish complete, explicit empty/no_data and not_returned.
  Missing properties are not evidence of a source-confirmed empty field.
- `last_attempt_at`, `last_http_status`, `last_error_code`, `last_error` describe
  the latest attempt; failures preserve previous successful fields and fetch time.
  `created_at` and `updated_at` record database writes.
- No image binaries, image links or image columns are retained. Only whitelisted
  fields reach files or SQL. Biographies are plain text with image elements and
  visible image URLs removed. Upstream bodies, cookies and headers are not logged.

The snapshot format carries `author_schema_version`, `parser_version`, `source`,
`author_id`, UTC `fetched_at`, normalized `profile`, `field_states`, and a SHA256
of canonical sorted UTF-8 profile JSON. Import checks identity, field types,
counts, timezone, field states, digest and size (4 MiB), then re-sanitizes.

## Request and recovery behavior

Acquisition uses a fresh normal IEEE search session followed by
`/rest/author/{id}`. This is an observed website endpoint, not a promised public
profile API. See [research notes](ieee-author-api.md). There is no API key, browser
cookie import, proxy rotation or coauthor traversal. Requests use 5/30 second
connection/read timeouts, at least one-second spacing, and at most three attempts
for network failures or 5xx. Restricted responses (including 202/418) stop
immediately. HTML, empty arrays, unexpected IDs and malformed JSON are failures.
A local file lock serializes single-author HTTP and spacing between processes;
a database-scoped advisory lock serializes writes for the same identity.

Sanitized content-addressed snapshots live beneath the personal configured
`state_dir/authors/ieee/ID/`, mode 0600 in private directories. The file is
atomically written and synced before the SQL transaction commits. A database
failure can leave an unreferenced valid snapshot: import that file to recover.
A disk failure cannot commit a profile update. Repeated imports use one row;
older observations cannot overwrite newer attempts. Identical content shares
its first snapshot; the latest row separately records the newer observation time.
No successful snapshot is deleted automatically. Re-run the same ID after an
interruption, or import its already exported snapshot without source requests.

## Website

Reader page: `/authors/ieee/ID`; authenticated API:
`GET /api/author-profiles/ieee/ID`. No write methods or fetch buttons exist.
The selected author identity card links to this independent page. Paper bylines
continue linking to exact-ID paper searches; candidate lists stay collapsed.
The page supports Chinese/English and mobile layouts, has no image placeholder,
and keeps source article/citation metrics distinct from local paper counts.
An absent profile displays not retrieved. A restricted/failed refresh retains
and timestamps the previous profile. A source-hidden profile suppresses cached
rich details in the reader API. Coauthor links open only stored-profile pages.

## Rollback

Switch the deployment's `current` symlink to its previous release and restart the
two web listeners. Keep `authors` and snapshots for forward recovery; old paper
clients permit the additional table and do not depend on it. Never drop author
records as part of application rollback. No database restart is required.
