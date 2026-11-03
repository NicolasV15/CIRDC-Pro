# Patent citations

Patent citations use independent snapshots, state and seven-day visit-triggered
refresh. Paper citations retain their existing two groups and paper-only totals.
There is no patent discovery, history scan, recursive collection or schedule.

## Website contract

`GET /api/papers/{number}/patent-citations?offset=0&limit=50&version=...`
returns `number`, `state`, `version`, `total` (stored), `expected_total` (source,
nullable), `source_presence`, `empty_reason`, `checked_at`, `last_attempt_at`,
`next_check_at`, `stale`, `error`, `offset`, `limit`, `next_offset` and `items`.
Pagination uses a fixed version, independent of either paper-citation group.
Limits are 1–100. A missing old patent snapshot is unconfirmed, never zero.

For compatibility with the citation storage model, the response also includes
`group: "patent"`, `counts: {"patent": null, "total": null}`, `stored_counts`
and `group_states`. These counts only describe patents.

Each item contains `order`, `label`, `source_id`, `text`, `title`,
`publication_number` (nullable), `country` (nullable), `publication_date`
(nullable), `inventors` (array), `assignee` (nullable), `target_kind` and
`target_url`. Valid publication numbers link to Google Patents. Missing or
unrecognized numbers link to Google Patents search using title, then citation
text. Patent identifiers never become local IEEE paper links.

`POST /api/papers/{number}/patent-citations/ensure` accepts `{}` or
`{"refresh": true}`. Fresh results and in-progress tasks are reused. Failure,
confirmed zero and source absence all receive a seven-day revisit interval;
explicit refresh can run earlier. The database reader remains read-only.

## Frontend handoff

Embed patent citations in the **By Patents** tab of the shared Citations panel,
with paper citations in **By Papers**. Use a single collapsed heading and keep
the approved paper-group visibility behavior inside By Papers. Fetch and
ensure once on article open, poll only while queued/fetching, and retain readable
old data during updates. Status refresh only reads. An explicit update action
uses `refresh: true`. Display publisher absence, explicit zero, unknown and
failure separately. Use source counts and stored counts separately when partial.

The frontend owns a new `PaperPatentCitations.tsx`, `patentCitationData.ts`, its
tests, translations, styles and a minimal mount in `main.tsx`. The backend owns
`patent_citation_source.py`, `patent_citations.py`, node capability isolation,
`web/patent_citations.py`, API wiring and bounded acceptance. Preserve existing
uncommitted work and ongoing publication snapshots.

Core schema v4 and the previous extensions remain unchanged. The patent
extension has its own four tables; shared availability uses the independent
`patent_citations` direction. New tasks require `paper_patent_citations_v1`.
Old HTTP nodes keep their original work. Requests use the coordinator's existing
exit budget and existing network bindings.

## Maintenance commands

Use `cirdc --config PROFILE patent-citations init` once after verifying the target
with `db-check` and `doctor`. `enqueue NUMBER [NUMBER ...]` accepts at most 20
explicit existing paper IDs. `read NUMBER --limit 50 --version VERSION` is
read-only. `status`, `publish`, and an explicit `enqueue --retry` reuse the
same persistent queue and publication recovery. Initialization requires the
existing citations extension, which owns the shared availability table.
