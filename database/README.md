# Empty database / 空数据库

[English guide](../README.md#empty-database-and-strict-recognition) | [中文说明](../README_CN.md#空库示例与严格识别)

`schema.sql` contains CREATE TABLE statements only. Choose your database and
account outside the repository; the file has no rows or deployment values.
Import using your database client's own connection settings, then run `db-init`.
It creates the application identity and migration metadata at runtime; all business
tables remain empty. Do not insert a copied identity UUID from another database.

| Table | Role / 用途 |
| --- | --- |
| cirdc_identity | Application, schema version, generated database UUID / 库身份 |
| schema_migrations | Applied migration versions / 迁移版本 |
| venues | Journal and conference series metadata / 刊会目录 |
| papers | Article identifiers, metadata and field states / 论文与字段状态 |
| paper_files | Article-to-JSON mapping and order / JSON 路径与顺序 |
| manifests | Imported/exported content digests / 内容摘要 |
| sync_cursors | Partition coverage and checkpoints / 分片覆盖与检查点 |
| runs | Durable jobs, counters, heartbeat and executor / 持久任务 |
| tasks | Pending/running/done/failed work and attempts / 任务队列 |
| exports | Shared staging and JSON publication acknowledgements / 导出确认 |

All column definitions, primary/unique keys, defaults, and queue indexes are in
`schema.sql`; the validator uses `src/cirdc/schema_contract.json`. The SQL file must
stay consistent with `src/cirdc/schema_ddl.py`. No data dump is included.
