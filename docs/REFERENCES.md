# Paper references

References are an optional metadata extension, independent of core schema v4.
Only explicit article IDs are collected. There is no catalog scan or periodic job.
Reader database credentials remain SELECT-only.

## Website contract

`GET /api/papers/{number}/references?offset=0&limit=50&version=...` returns:

```json
{
  "number": "123", "state": "complete", "version": "snapshot-id",
  "total": 1, "expected_total": 1, "checked_at": "2026-01-01T00:00:00+00:00",
  "error": null, "offset": 0, "limit": 50, "next_offset": null,
  "items": [{
    "order": 1, "label": "1", "source_id": "ref1", "text": "Full citation",
    "title": "Article title", "target_number": "456", "doi": null,
    "target_kind": "paper", "target_url": "/papers/456"
  }]
}
```

States: `missing`, `queued`, `fetching`, `complete`, `no_data`, `unavailable`,
`partial`, `blocked`, `failed`, `disabled`. Items belong to `version`, even if a
later attempt fails. `total` is the number of saved items; `expected_total` may
be null. Version is null before a snapshot exists. `checked_at` and `error` may
be null. Limit is 1–100. A requested unknown version returns HTTP 404.

`GET /api/papers/{number}/references/{order}?version=...` returns
`{number, version, item}`. Missing papers, versions and items return HTTP 404.

`POST /api/papers/{number}/references/ensure` needs the usual same-origin and
authenticated-reader CSRF checks, or the explicitly enabled anonymous-reader
policy. It takes no article data and returns the list response, HTTP 202 while
queued/fetching, otherwise HTTP 200. It never retries a terminal attempt.
The enabled website calls a configured maintenance executable to enqueue only;
source HTTP and SQL writes run in the existing coordinator, not the reader.

An installation may configure `web.references.read_command` as an argv array for
the maintenance executable, alongside `enqueue_command`. This uses the same
bounded read interface in a separate core environment; its database transaction
is explicitly READ ONLY. It requires no new database grants for the website
reader and never loads maintenance credentials into the website process.

Maintenance commands are `references init`, `references enqueue ID ...`,
`references status [ID ...]`, `references read ID`, and `references publish`.
Enqueue accepts 1–20 explicit IDs. `--retry` on enqueue starts an explicit new
attempt without erasing old snapshots or failures. Only the configured source
coordinator processes pending requests; no command implicitly scans publications.

All identifiers remain strings. An authoritative numeric IEEE ID always links
to `/papers/{id}`, including when its metadata is absent. There is no external
fallback or automatic metadata import. Other items link to
`https://scholar.google.com/scholar?q=...`, using DOI, title, then plain citation
text. The backend constructs these URLs. Citation text is plain display text;
the immutable private snapshot retains original source fields, excluding
session/user information.

## UI integration

The optional citations extension adds independent source availability observations.
Reference pages expose `source_presence`, `empty_reason`,
`availability_checked_at`, and `needs_availability_check`. Publisher-confirmed
absence (`section_absent`) is distinct from an explicitly empty result
(`zero_count`). Missing fields and access errors remain unknown. Opening a legacy
unavailable reference may request one capability-gated availability check; no
history-wide reclassification is performed. See [Citations](CITATIONS.md).

Mount after the document reader and before keywords, including for papers without
a document. Ensure once on opening an existing paper; poll only while queued or
fetching. Reuse completed data and do not repeat terminal failed requests.
Use the snapshot version for subsequent pages and item lookup.

Explicit publisher anchors such as `context_ref_7_1` map to reference order 7.
Clicking reveals/highlights the item and offers return to the citation. Do not
infer links from arbitrary numbers, equations or converted plain text.
Keep citation-format export and existing figure/table navigation intact.

## Delivery boundary

Live acceptance uses an explicit list of at most 20 source article IDs. Navigation
tests use cache/fixtures to avoid cascading collection. No broad backfill or
periodic discovery is started by installation, website publication or acceptance.
