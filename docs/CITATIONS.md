# Paper citations and independent availability

The optional citations extension preserves core schema v4 and references v1.
Only explicit IDs and on-demand requests are accepted; no discovery or schedule.
Groups are `ieee` and `nonIeee`. Patent citations use the separate
[patent citations extension](PATENT_CITATIONS.md), preserving paper-only totals.
Availability reads the verified document-page metadata and each relationship
endpoint. It never requests the full-text REST document endpoint. Missing fields
or a page shell without authoritative section evidence remain unknown.
The publisher's `metadata.sections.references` and `metadata.sections.citedby`
use explicit `"true"` / `"false"` values. They are interpreted independently;
missing, malformed, or conflicting flags do not establish section absence.

## Website contract

`GET /api/papers/{number}/citations?group=ieee&offset=0&limit=50&version=...`:

```json
{
  "number": "123", "state": "complete", "version": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "group": "ieee", "total": 5, "expected_total": 5,
  "counts": {"ieee": 5, "nonIeee": 3, "total": 8},
  "stored_counts": {"ieee": 5, "nonIeee": 3, "total": 8},
  "group_states": {"ieee": "complete", "nonIeee": "complete"},
  "source_presence": "present", "empty_reason": null,
  "checked_at": "2026-01-01T00:00:00Z", "last_attempt_at": "2026-01-01T00:00:00Z",
  "next_check_at": "2026-01-08T00:00:00Z", "stale": false, "error": null,
  "offset": 0, "limit": 50, "next_offset": null,
  "items": [{"group": "ieee", "order": 1, "label": "1", "source_id": "",
    "text": "Full citation", "title": "Article title", "target_number": "456",
    "doi": null, "target_kind": "paper", "target_url": "/papers/456"}]
}
```

States match references: missing, queued, fetching, complete, no_data,
unavailable, partial, blocked, failed, disabled. Counts are source counts and may
be null individually; total is null until both groups are known. Stored counts
count actual saved rows. `total` and `expected_total` refer to the selected group.
Groups have separate source-order spaces. Pin `version` on subsequent page reads;
unknown versions return 404. Old successful items may remain readable after a
failed refresh. `checked_at` describes the displayed snapshot; last_attempt_at,
next_check_at and error describe the latest attempt. Limit is 1–100.

`POST /api/papers/{number}/citations/ensure` accepts `{}` or
`{"refresh":true}`. It returns the same page (default group ieee), HTTP 202 while
queued/fetching, otherwise 200. Default ensure is eligible once every seven days,
including confirmed empties and unsuccessful terminal attempts. Explicit refresh
may run earlier, subject to deduplication and rate limiting. Refreshing status is
a GET and does not collect data. Usual same-origin, reader-authentication and CSRF
policy applies. The database reader retains its existing privileges.

References pages add `source_presence`, `empty_reason`,
`availability_checked_at`, and `needs_availability_check` without changing their
existing fields. Presence is `present`, `absent`, or `unknown`. Empty reasons are
`section_absent`, `zero_count`, or null. An old unavailable reference may request
one new availability check via its existing ensure endpoint. Failed/blocked
references do not get a new automatic retry policy.

## UI

Mount Citations after References and before keywords. Both sections remain
independent and visible, collapsed initially, using the current title/arrow style.
Unknown, pending and failed states must not be labeled zero. Confirmed absence
shows publisher-not-provided; confirmed zero shows zero. Citations has independent
group selection and paging, source counts, check time, update status, read-only
status refresh and explicit update actions. Ensure once on opening; poll only
while queued/fetching. Do not connect citations to inline bibliography anchors.
Keep existing references/body navigation and citation-format export unchanged.

Use the existing safe paper/Scholar link rules. Numeric IEEE IDs always open
local paper pages. Missing paper metadata remains a local error; no recursive
collection. Other rows use the backend Scholar search URL.
