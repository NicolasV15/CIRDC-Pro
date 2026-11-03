# Database access roles

Reader, administration and indexing services can use separate private profiles
through `CIRDC_CONFIG`. They connect to the same verified metadata database.
Keep real endpoints, account names, passwords and profile paths outside Git.

| Role | Metadata database privileges |
| --- | --- |
| Reader API | SELECT on `papers`, `venues`, `paper_files`, optional `authors`, and identity/version tables used for verification |
| Administration / maintenance | Required reads; INSERT/UPDATE/DELETE on metadata, job, export and enabled extension tables; queue writes for change capture |
| Index worker | SELECT on papers, venues, capture versions and settings; SELECT/INSERT/UPDATE/DELETE on `web_index_queue` |
| Setup | Explicit schema initialization, migrations, capture triggers and index activation |

Normal reader, administration and index credentials do not need CREATE, ALTER,
DROP or TRIGGER privileges. Create accounts and grants with a database
administrator. Existing collection runtimes retain their current profile until a
deliberate transition; creating website roles does not revoke other accounts.

## Prepare indexing once

Initialize the metadata target through the root package and verify its schema and
pinned identity before using website setup credentials. Then run from the
repository root:

```sh
CIRDC_CONFIG=/path/to/private/setup.json \
  website/.venv-dev/bin/python -m cirdc.cli web init-index
```

This explicitly prepares the website capture schema, migrations and triggers,
then enables indexing. It does not run a backfill, start a worker or collect
source metadata. The setup account remains separate from runtime service profiles.

The index worker now validates installed capture version 2 and the enabled flag
before processing records. It does not install or repair capture objects at
startup. An unprepared target fails before an index rebuild. Prepare a fresh
installation or incompatible capture state with the setup command first.

Ordinary website-package `update` commands also require an initialized metadata
schema; they no longer run schema migrations implicitly. Explicit `db-init`
continues to use setup credentials.

## Select each runtime profile

Use the same website state directory but a different MySQL account per service:

```sh
CIRDC_CONFIG=/path/to/private/reader.json sh tools/web serve \
  --interface reader --host 127.0.0.1 --port 18090
```

```sh
CIRDC_CONFIG=/path/to/private/writer.json sh tools/web serve \
  --interface admin --host 127.0.0.1 --port 18091
```

```sh
CIRDC_CONFIG=/path/to/private/indexer.json \
  website/.venv-dev/bin/python -m cirdc.cli web index
```

The service templates have separate `CIRDC_READER_CONFIG`,
`CIRDC_WRITER_CONFIG` and `CIRDC_INDEX_CONFIG` placeholders. Render them privately.
For existing units, use private service drop-ins rather than replacing unrelated
service settings. Check inherited `CIRDC_MYSQL_*` environment overrides: they take
precedence over profile fields and must not select a different account.

This boundary applies to the metadata MySQL connection. Website accounts/sessions
and search indexes use their own local SQLite files. Enabled resource providers
may also maintain independent task state or result storage; preserve those
explicit write paths while restricting metadata access.

## Verify the transition

Check the actual runtime user and its grants, rather than relying on a profile
filename. Confirm search, article details, author discovery and configured
resource links still work. A reader account must be denied metadata DML even for
an UPDATE with a condition matching no rows. The index account must be denied
paper updates and DDL while retaining versioned queue acknowledgement.

Test positive writes against isolated test tables and paths; do not insert
synthetic jobs or articles into a live corpus. Retain checkpoints and queued
events across restarts. Keep old service profiles available for rollback until
the new runtime behavior has been verified.
