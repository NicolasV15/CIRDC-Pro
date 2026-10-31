# Browser deployment

The optional website reads the configured local metadata database. The reader and
administrator applications have separate route tables and sessions. The reader
application never registers administration routes.

Build the frontend with `npm ci && npm run build` in `web/`, then install the
package with its `web` extra. Built assets are included in the wheel. Node.js is
only needed for the build.

```
cirdc web init-users --username admin
cirdc web index
cirdc web serve --interface reader --host 0.0.0.0 --port 18088
cirdc web serve --interface admin --host 127.0.0.1 --port 18089
```

Account initialization prompts for the initial password. It never changes an
existing account, Linux password, or database administrator password. Use
`cirdc web passwd --username <name>` locally to reset a website password. The
new password must be changed at the next login. Initial accounts come from private `web.bootstrap_users` configuration, or
`init-users --username NAME` creates an explicitly named administrator.
Account initialization is independent of operating-system authentication. Passwords, session tokens, and database credentials must not enter
source control or logs.

For a versioned deployment, run `sh tools/web deploy <release-id>`
from the unified repository root (or `bash tools/deploy_web.sh <release-id>`
from this website directory). Set `CIRDC_WEB_ROOT` explicitly to the existing deployment;
`CIRDC_WEB_STATE` defaults to its `.runtime/state`. The script requires existing
accounts and index state, and never initializes accounts or migrates the database.
It takes a deployment lock, builds a candidate source snapshot and assets before
stopping services, then installs only the built wheel offline into the existing
website environment. Dependency and private-provider versions, service units and
drop-ins are retained. It switches `current` and checks both listeners, restoring
the previous wheel and link on activation failure. A rollback wheel and a successful
bounded configuration-load check are required before any service is stopped.
Unresponsive remote storage therefore blocks publication while the current services
remain running. It never resumes a maintenance job. The existing
firewall rule for TCP 18088 is managed separately from application releases.

## Deployment-specific configuration

Public documentation uses configurable roots, loopback examples and SSH placeholders.
Keep actual listener addresses, SSH aliases, dataset mounts, account lists and service
environment in private profiles and runtime records outside Git. An ignored
`.cirdc/local-workspace` pointer and the website's ignored `.workspace/` records
can locate those details on an installed server.

For remote administration, use your configured SSH host:
`ssh -N -L 18089:127.0.0.1:18089 YOUR_SSH_ALIAS`, then open
`http://127.0.0.1:18089/admin/`. The reader listener and firewall policy are
selected by the deployment. Use an appropriate protected transport for authenticated access.

Releases live under `<web-root>/releases`; `current` selects the active release.
Keep the environment, accounts, local SQLite index and logs in their configured
private locations. `CIRDC_WEB_STATE` selects website state; directories use mode
0700 and database files use 0600. Service templates are provided in `deploy/`;
render placeholders privately and retain the installed environment during releases.

## Search and consistency

The FTS5 index uses SQLite's Unicode tokenizer and searches title, ordered author
names, classified keywords, and abstract text. BM25 weights are 8/3/5/1.
Searches match all entered words; raw FTS expressions are not accepted. Filter
parameters and DOI lookups are bound SQL values. Conference-series filters
include individual editions from publication history.

Article numbers remain strings. Detail pages read MySQL directly, including
ordered authors, keyword classes, field states, and the record update time.
Search pagination selects identifiers before reading full records, forces that
join order for SQLite 3.34, and uses covering indexes for publication, year, and
field-state filters. Periodical filters include magazines and early access.
Repeated queries share a bounded 30-second in-process result cache and a single
in-flight computation. A committed index-file version change immediately
invalidates cached pages; detail reads are never cached. Health and coverage
metadata are refreshed for every response.
Search projections and counts have separate synchronization timestamps; field
content is not proof that the latest maintenance run fetched it.

`GET /api/overview` includes `index.year_range` (`min` and `max`, nullable),
read from the current search index with indexed boundary lookups. The reader's
descending year selectors include indexed future publication years, alongside
the current year and any selected URL bounds. They update with the existing
60-second overview refresh after metadata changes reach the search index;
no index rebuild or frontend release is needed to expose a newly indexed year.
Missing and out-of-range publication years do not expand the selectors.
Year bounds are inclusive and may be left unlimited individually. The selectors
disable choices that would put the start after the end; inverted URL bounds are
reported before searching. The API rejects inverted ranges with HTTP 422,
including exact article-number lookups.

Migration 3 adds an optional index activation setting and a per-article queue.
The separately versioned web capture migration installs conditional row triggers
in the application database, so older clients and direct SQL writers are captured
in their own transactions too. Installing capture on an existing index performs
a one-time non-locking reconciliation from the original backfill start time.
The metadata engine updates queue versions in the same transaction as records
and field states. The indexer commits SQLite before acknowledging the exact
MySQL queue version; newer concurrent versions survive. Recovery may replay an
event and is idempotent. Queue creation alone does not enable indexing.

Initial backfill scans the primary key in batches with transactional checkpoints,
then drains changes accumulated during backfill. `cirdc web index --max-rows
100000` builds a bounded sample and exits; a normal invocation continues from its
checkpoint. Only after all rows and pending events have been processed does the
index become ready. A process lock prevents duplicate indexers. SQLite uses
rollback journaling, not WAL, for the installed SQLite 3.34 runtime. Insufficient
disk space pauses progress without deleting the index. Details remain available
by article number during backfill; partial search coverage is labeled.

## Administration and verification

Update previews and actions call the existing engine. Starts return a run ID;
workers continue independently of the browser. Scope conflicts are rejected,
matching jobs are reused, and retries retain the existing attempt limit. HTTP
access challenges stay blocked and never become empty results. Deployment does
not resume blocked jobs. There is no scheduled collection job.

Management writes require the loopback application, administrator authentication,
same-origin requests, and a session-bound CSRF token. Account resets and disables
revoke sessions. Audit entries contain actor/action/target, never passwords.
Only bounded, redacted log tails are returned; filenames are derived from a
validated job identifier.

Run `CIRDC_INTEGRATION=1 pytest` with a verified isolated test profile for unit and MySQL integration tests.
The integration fixture uses connection-local temporary tables to isolate the
existing corpus and jobs. Build and inspect both wheel and source distribution.
Verify login boundaries, first-use password changes, index crash recovery,
conference-series mapping, short-word/abstract searches, and full-corpus search
performance before marking deployment accepted.

## Optional related-reading providers

`CIRDC_WEB_RESOURCE_PROVIDERS` is an explicit comma-separated allowlist of local
entry-point names from `cirdc.web_resources`. No provider is loaded by default,
even if additional packages are installed. Providers add related-resource links
and authenticated reader routes under `/api/resources/`; first-use password
changes and normal session checks apply to these routes too. Storage failures
do not prevent metadata browsing. Installed providers are trusted application code.

Install or update providers separately through their authorized deployment workflow.
Ordinary website releases preserve the installed providers and dependencies.
Keep site-specific dependency locations and configuration out of the public repository.

## Source-scoped author identities

Author identity is `(source, author_id)`, initially `source=ieee`. IDs are opaque
strings, including in browser-facing references; never convert them to JavaScript
numbers or merge distinct IDs by name. Names observed for the same source ID are
aliases. Source IDs can still represent unresolved upstream identity issues; any
future cross-ID or cross-source consolidation must be explicit and auditable.

`author_entities`, `author_names`, and ordered `paper_authors` in the derived
SQLite index provide identity discovery and exact-ID paper filtering. Missing
IDs are signature/name buckets, not identified people. Original author order is
preserved. Author-name search matches the words within a single signature,
avoiding false matches that combine different coauthors' names. Selecting a
source ID includes its observed name variants and excludes same-name identities.

The existing indexer updates author relations before acknowledging the canonical
change queue. A resumable one-time relationship backfill runs between event
batches; collection and name consolidation have separate checkpoints. Name FTS postings
are rebuilt atomically after bulk consolidation, then row triggers resume normal
incremental insertion. An interrupted rebuild retries from the saved phase. Author
search reports partial coverage until both stages finish. No outside author
profiles are fetched.

Authenticated interfaces: `GET /api/authors?q=<name-or-id>` lists matching source
identities with paper counts, year ranges, observed names, and separate missing-ID
counts. `GET /api/authors/ieee/<id>` returns basic identity information and
`profile_ref={source,author_id}`. `GET /api/papers` accepts `author_source`,
`author_id`, and `author_unidentified=1`. In the author search mode, a selected
identity defines the paper set independently of name spelling. Other search
fields can be combined with an explicit author filter.

A future author-information database can join on the string pair in `profile_ref`;
keep name, affiliation, ORCID, research interests, source URL, and observation
time as sourced profile attributes rather than identity keys. No personal details
are inferred from a name or claimed without a supporting source. The profile
database is not required for current identity-based discovery.

## Display-only circuit publication families

The browser's `web/src/venueFamilies.ts` is the only source of abbreviations,
full names, source IDs, aliases and historical label rules. Its 22 families cover
11 journal IDs and 14 conference series from the existing selected-publication
folders. They describe publication sources, not an article's technical topic or
quality. The old article lists and their year ranges never limit the selection.

- Journal families: JSSC, LSSC (SSCL alias), TCAS, TCAS-I, TCAS-II, TVLSI, TCAD,
  Proc. IEEE and J-TCAD. J-TCAD is a local display alias for the separate Journal
  of Technology Computer Aided Design TCAD, not the IEEE TCAD journal.
- Conference families: A-SSCC (ASSCC alias), ASYNC, CICC, DAC, DATE,
  ESSERC / ESSCIRC, ICCAD, IEDM, ISCA, ISCAS, ISSCC, MEMS and VLSI.
- TCAS-I IDs 81/8919 and TCAS-II IDs 82/8920 share family filters. IDs 31, 81,
  82 and 6414145 receive Old labels. ESSCIRC and pre-merger VLSI-C / VLSI-T
  receive Old according to the edition name, with merged VLSI names checked
  first. Publication year alone never makes an article Old. An unknown edition
  name is not guessed to be historical.

Selected family keys live in the browser URL's `venue_tags` parameter. Tags
apply immediately; multiple families form a union and combine with other filters
by intersection. Default browsing still covers all IEEE records. Publication
badges beside papers are non-interactive labels with a subtle theme-aware fill;
family filtering uses the dedicated controls. Returning from detail preserves
applied filters.

`GET /api/papers` accepts generic `venue_any` (up to 32 comma-separated numeric
publication/series identifiers, preserved as strings). The server expands series
through existing `venue_members` before ranking or cursor pagination. The legacy
`venue` parameter remains supported and intersects with `venue_any` when both are
present. Invalid or oversized lists return 422, including on exact-number lookups.
All paper list paths and details include `venue_series: string[]`, resolved with a
read-only SQLite connection. This metadata contains source identifiers, not the
frontend's family labels.

This feature requires no migration, index rebuild, extra index, metadata update
or collection job. Deploy the built web application and restart the reader/admin
services; the existing index worker may remain running. Run backend tests and
`node --experimental-strip-types --test tests/venueFamilies.test.ts` in `web/`,
in addition to the frontend build and browser checks.

## Interface languages

Reader and administrator pages provide Chinese and English UI text through the
header language buttons. The browser remembers the preference for the current
origin in `localStorage["cirdc.ui.language"]`; other open tabs update too.
Switching retains the current page, drafts, filters, venue selections, session
and expanded abstracts. Paper titles, abstracts, author names, keywords,
publication names, raw JSON and technical logs retain their source content.
Dates, statuses, validation messages and accessible labels use the selected
language. Reading-resource providers may supply optional `label_i18n` and
`note_i18n` objects containing `zh` and `en` strings. Source-specific labels stay
with the provider. The default language is Chinese. Run `npm test` in `web/`
for translation coverage, language persistence, error handling and venue tests.

## Author links and confirmed identities

Paper-list responses include ordered `author_refs` from the existing derived
author relation index; direct-number results use the canonical record. Names
with source IDs link to exact-ID paper searches, including on paper details.
Unidentified signatures are not linked by a guessed name or identifier.

A confirmed identity is fetched directly by source and ID and pinned above the
results. Other candidates are collapsed by default, even when the selected ID
is absent from the first discovery page. The user may expand other matches,
page through them and select a different identity. Selecting an identity closes
the candidate list; unscoped author searches retain the discovery list. Language
switching preserves the selected identity and disclosure state.

## Reserved local-file annotations

Migration 4 adds exactly two nullable columns to the existing `papers` table:
`has_pdf TINYINT(1) DEFAULT NULL` and `pdf_path TEXT DEFAULT NULL`. A public
installation leaves them empty. They are outside the article JSON; ordinary
metadata imports and enrichment never populate, reset or export them. An
independent deployment adapter may fill them without changing metadata content.
The intended flag semantics are NULL=unscanned, 0=checked absent, 1=present.
Paths are relative to a separately configured server root. No file scanning,
downloading or processing command is added to the public engine.

Configured resource providers may optionally implement `describe_settings()`
and `configure(values)`. Administrator settings are explicitly enabled through
`CIRDC_WEB_ADMIN_RESOURCE_PROVIDERS`, independently of reader providers.
`GET /api/admin/resources` and authenticated, CSRF-protected
`POST /api/admin/resources/{identifier}` are administrator-only; the latter is
audited. Default public installations expose no configured storage forms.
Changing a root does not rewrite paper rows or start collection.

## Original IEEE author pages

Author identity cards include an independent IEEE Xplore link opening a new tab.
Paper details group original-author links in a collapsed disclosure. Internal
author-name links continue to search this database by the exact source ID.
External links are created only for IEEE references with a numeric string ID;
unknown identities are not guessed and no browser request collects profile data.
The source links do not select another identity or expand author candidates.

## Temporarily opening the reader without account sign-in

`CIRDC_WEB_READER_AUTH=public` opens the **reader** as anonymous, read-only access.
The default is `required`. Administrator authentication is always required,
even if the environment variable is public. Keep the administrator listener on
loopback and use its existing SSH tunnel.

The session endpoint reports `authentication_required` and `access_mode`; public
responses contain no user identity, CSRF token or pre-login cookie. The browser
then hides the sign-in/password/sign-out interface. Reader account APIs are
inactive in public mode, and public API requests allow only GET/HEAD. This also
applies to installed reading-resource routes. Search retains a per-peer-IP limit;
forwarded client-address headers are not trusted and limiter memory is bounded.

Account hashes, existing users, login/password/session code and administrator
account management remain intact. The flag does not alter paper or author data,
start collection, rebuild indexes, or run database migrations.

Deployment switch (reader service only):
`~/.config/systemd/user/cirdc-web.service.d/40-reader-access.conf`

```ini
[Service]
Environment=CIRDC_WEB_READER_AUTH=public
```

To restore sign-in, change that value to `required`, then run:

```sh
systemctl --user daemon-reload
systemctl --user restart cirdc-web.service
```

The same installed frontend restores its existing login and password-change
workflow after refresh; no rebuild or account recreation is needed.

## Document chapter navigation

Cached article bodies show a sticky chapter sidebar outside the article panel
on wide screens. The contents, body and publication sidebar share a centered
reading area with balanced outer spacing. Reading layout controls adjust the
maximum page width (1280–2200 px), contents width (180–280 px) and publication
sidebar width (180–280 px), with a font-size slider (80%–150%) that scales article text, abstracts and formulas. Its default 100% preserves the existing sizes on desktop and mobile. The publication sidebar defaults to 220 px and can
collapse to a narrow right-side tab. Preferences use `cirdc.reader.layout.v1`
for the current browser origin and can be reset to defaults. Narrower screens use a collapsible sticky
contents bar that closes after a chapter is selected. No chapter is highlighted before its heading is reached. The current chapter
is highlighted as the page scrolls, and scrolling back above the first heading
clears the highlight; image loading and viewport changes refresh that position. Long chapter lists scroll independently
inside the navigation while the article keeps normal page scrolling.
Standalone publisher section labels (for example `SECTION II.`) are grouped
with their headings, and the outline includes the original number (`II. Title`).
This also applies to cached articles; numbering is never inferred from anchor IDs.
Figure and Table references jump to matching local targets, including cached
articles whose original links lost their addresses. Ambiguous or missing targets
are not inferred.

## Compact reader overview and optional document coverage

The reader places its compact overview next to the page title on wide screens,
with responsive stacking on narrow screens. `/api/overview` may include
`overview.resource_coverage` and the same value under `index.overview`.

Enabled resource providers can implement `coverage()` to return a localized
label, a known numerator, status and source sampling time. A provider may supply an explicit `denominator` for a fixed registered scope;
otherwise the denominator is the whole-database count. An explicitly unknown
scoped denominator never falls back to the global count. Coverage is independent
of current search filters. Unknown, incomplete or inconsistent counts display as unknown,
not zero. Provider configuration is excluded from the response. This projection
is response-only and does not rewrite the search index or article metadata.

Scientific notation in paper-list titles, detail headings and citation-dialog headings uses the existing KaTeX engine. Explicit TeX delimiters and `tex-math` source tags render inline; ordinary text and unsupported formulas remain readable. The renderer loads on demand, keeps theme colors and does not alter source metadata or exported citation text.

## Citation export

Each paper in the browsing results has a **Cite** button. The dialog reads the existing paper detail record and generates BibTeX, IEEE plain text, or GB/T 7714-2025 (numeric order). It does not mount the document reader or request content collection. Copy the current format or download it as a UTF-8 `.bib` / `.txt` file. Direct HTTP readers use the selected-text clipboard fallback; if the browser rejects copying, the dialog keeps the text selected for manual copying.

Author order and source titles are preserved. Missing fields are identified rather than invented. Early Access references omit provisional volume `PP`, issue `99`, and provisional pages; a missing online publication date remains visibly incomplete. IEEE Xplore document numbers are used only for the citation key and source URL, never as publisher article numbers. Plain-text entries omit reference-list numbering.

Formatting references: [BibTeXing](https://ctan.net/biblio/bibtex/base/btxdoc.pdf), [IEEE Author Center reference guide](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/ieee-editorial-style-manual/), and [GB/T 7714-2025 status](https://openstd.samr.gov.cn/bzgk/std/std_list?p.p1=0&p.p2=GB+T+7714&p.p90=circulation_date&p.p91=desc). The formatter covers journal articles and conference papers, and leaves publisher-specific verification to the reader.

## Batch selection and downloads

Use checkboxes directly on the loaded result rows. Select all toggles every loaded row, including results appended with Load more; newly appended rows start unchecked. Changing the page size, search, sorting or filters resets the rows and selection together. Refresh starts unchecked; returning from a detail page keeps the existing rows and checks. There is no separate selection basket or hidden selection. Bulk citations use result-list order and bounded metadata readers; they do not silently truncate at 100. Plain-text formats number the entries and identify failed metadata reads separately.

The optional download dialog uses explicitly advertised resource-provider archive capabilities. Filename templates accept `{id}`, `{title}`, `{year}` and `{abbr}` in arbitrary order, with literal separators. Abbreviations come exclusively from the existing curated-venue mapping. Empty fields, unsafe filename characters, reserved names, UTF-8 length limits and name collisions are handled in the download copy. The chosen template stays in this browser’s local settings. Before previewing availability, the dialog sends bounded HEAD requests to the advertised local PDF links and verifies a successful PDF response with a nonempty length. Missing, unreadable and unverified files have distinct states and cannot be offered as available. Archive creation rechecks files; skipped files update the preview. Missing resources are reported and never trigger source collection. More than 100 loaded selections are split into explicit ZIP buttons of at most 100 items; a single click never silently discards the remaining records. An enabled provider can prepare and stream an archive; the default public installation does not gain a storage backend from this UI. Download initiation is distinct from browser completion.

The paper detail header also provides **Cite**, opening the same citation dialog and copy/download actions as the result list. List spacing is compact while selection controls, author links and action buttons retain their existing touch-target sizes.

Paper details initially show the first three author names as compact links. Expand the author list to see every ordered signature, its existing IEEE ID and the original-author-link disclosure. Long expanded lists have their own scroll area. Short lists can expand their ID details as well. Expanding performs no author collection, and citation export continues to use the complete stored author array.

The record row above the paper title groups **Cite** and **Read PDF** together. The PDF control is an enabled reader link when a PDF descriptor is available; otherwise it is a grey native disabled button with the missing/unavailable reason. Unrelated resources do not enable it. Other local resources remain in the publication sidebar when present; the PDF entry is not duplicated there.

Paper details use the same 1800 px maximum workspace width and responsive outer padding as the search page, including full available width for the paper title.

Search results offer 25, 50, 100 or a custom 1–100 records per page. Presets apply immediately; custom values apply on Enter or with Apply. The setting is stored in the browser and the `limit` URL parameter, survives returning from a paper, and remains when other filters are cleared. A size change replaces the current result batch and resets its cursor and clears row selections. Load more continues to append the chosen batch size. The existing API limit and schema remain unchanged.


## Appearance themes

The Appearance control offers six presets and a system option. System is the default,
using Plain white for light mode and Graphite for dark mode. The preference is stored
locally as `cirdc.ui.theme.v1`; tabs on the same origin synchronize without reloading.
Reader and admin origins remember their preferences separately. The palette catalog
builds `/assets/themes.css` and the blocking, independent `/assets/theme-init.js`.
Related reading pages may load these same resources without loading the React app;
the initializer never changes document titles. Document bytes and source images retain
their original colors. Stable theme assets use revalidation caching.
