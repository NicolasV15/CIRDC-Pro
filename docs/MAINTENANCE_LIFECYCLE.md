# Maintenance lifecycle

This checkout is the sole maintained metadata engine. It owns publication catalogs,
basic article metadata, normal missing-field enrichment, Early Access bibliography
refresh, resumable queues and consistent database/JSON publication.

Historical forced rechecks and manual result-packet collection stay in their frozen
repair runtime for the already submitted batch. They are not installed or exposed
by this package. CLI, Python and MCP reject repair selection parameters rather than
turning a repair request into a wider maintenance run. Existing repair records may
still be inspected with status; resuming them requires their frozen runtime.

Normal metadata updates may coexist with an existing external document writer by
using short shared write locks. The retained `cooperative_writes` checkpoint flag
means this write protocol; it does not install or invoke a historical collector.
Legacy ordinary jobs keep their exact scope when resumed.

Retire the repair runtime only after its frozen selection has no pending, running,
failed, blocked or deferred tasks; all JSON obligations are acknowledged; and shard
leases are released. Keep canonical results and failure history. Machine-specific
job identities, paths and the retirement guard belong in private runtime records,
outside the source tree. A blocked or exhausted batch is not a completed batch.
