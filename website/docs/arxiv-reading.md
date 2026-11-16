# arXiv reading integration

The metadata maintenance package owns the independently migrated database and metadata index. The website reads those through `CIRDC_ARXIV_READER_CONFIG`, a private JSON profile containing `mysql`, `database_id`, and `index_path`. Use a SELECT-only account. The adapter also opens a read-only transaction and validates database/index identity. No website operation imports or synchronizes metadata. The index may still be unavailable during initialization; this returns 503, never an upstream search.

The frontend uses `/?source=arxiv&q=...` and `/arxiv/papers/INTERNAL_ID?v=VERSION`. IEEE remains the default. Opening a page, selecting versions and polling are read-only. The explicit acquisition button requests all three formats and reading preparation. The metadata schema's current title and abstract do not represent historical per-version snapshots.

## Interfaces

All routes below are relative to `/api/arxiv`:

- GET `papers?q=...&limit=20&cursor=...`: local metadata search; cursor is bound to the query, default 20, maximum page size 100. Rankings can change between pages during index updates.
- GET `resolve?id=...`: new/old identifiers and official links; no acquisition.
- GET `papers/ID`, `papers/ID/versions`: metadata and observed version list.
- GET `papers/ID/versions/V/resources` and `document`: independent original/reading status.
- POST `papers/ID/versions/V/ensure`, JSON `{}` or `{"retry":true}`: deduplicated acquisition receipt. Retry retains successful originals and confirmed absence.
- GET `requests/REQUEST_ID`: receipt; `reading_ready` and `acquisition_complete` are independent.
- GET/HEAD `papers/ID/versions/V/files/pdf|source|html`: cached original only; source and raw HTML are attachments.
- GET `papers/ID/versions/V/body?render_id=HASH` and `assets/ASSET_ID?render_id=HASH`: immutable version-bound sanitized rendering and raster assets.

The separate, explicitly configured resource provider supplies acquisition and file routes. Without a provider only metadata routes are available. Existing Agent v1 routes remain intact; when the reader profile is configured, MCP additionally exposes source-specific arXiv search, metadata, ensure and receipt tools. These reuse the same interfaces. No authentication is added for the agreed internal reader deployment.

## Storage and operation

Keep `metadata/` managed by metadata maintenance. On-demand files live under sibling `papers/ARXIV_ID/vN/original/` and `derived/RENDER_ID/`; old identifiers encode `/` as `%2F`. Originals retain source bytes. A version manifest records SHA-256, URL, timestamps, actual format and reading provenance. Queue databases, locks and temporary conversion workspaces must reside on local storage, never NFS.

The acquisition worker shares the metadata request-budget lock and cooldown file, not its whole-run lock. File requests reserve a 15-second cooldown; explicit Retry-After can extend it. Do not run another acquisition worker with a separate budget. One local worker lock enforces a single active publisher; crash recovery reuses published receipts and reclaims unfinished work. This implementation is a single-host worker, not a distributed lease scheduler.

The requested order is official HTML, PDF, source. HTML reading is adapted before remaining acquisition; only referenced image assets are queued, no linked papers are crawled. Original acquisition continues after reading succeeds. Images update progressively. SVG originals are retained when downloaded but are not served as active images; unsupported images degrade visibly. Source rendering uses a digest-pinned LaTeXML 0.8.8 container with no network, limited memory/CPU/time and bounded archive extraction. MinerU is used only when HTML and source conversion fail; request IDs and service instance are persisted before submission. A failed parser does not invalidate an acquired PDF.

Resource-specific acquisition errors have three automatic attempts with persisted retry dates. Confirmed missing and restricted responses remain distinct. Temporary network failures are not missing-data observations. Partial files are not exposed; range resume requires matching URL/ETag and Content-Range. File receipts permit recovery after publication before queue registration.

## Verification and handoff

The implementation's tests distinguish fixture transport/browser behavior from real export and converter acceptance. Read the task's private verification records for actual source requests, converter images and input hashes. Production deployment is separate; source changes do not restart IEEE services or metadata jobs.

Current integration entrypoints: website module `cirdc.web.arxiv`, source-specific `/api/arxiv/` routes, and the existing resource plugin registry. Run website pytest, frontend tests/build and `web/tests/arxiv.browser.cjs`; private worker tests run in its owning repository. Do not install maintenance and website packages into one environment.

## HTML typography

The shared reader marks the document container with its source. For arXiv HTML and LaTeXML output, public `ltx_*` roles determine presentation: document titles use the site's serif title face, abstract titles share the existing section-heading specification even when the source element is `h6`, and author/date/keyword/caption roles use smaller supporting text. Existing section and body typography, reader font scaling, anchors and formula copying remain shared with the IEEE reader. Publisher stylesheets are not loaded into the host page. Cached HTML and original TeX are not rewritten; this also styles previously cached documents without reacquisition or conversion.

## Search and batch actions

The arXiv browse page shares the IEEE search controls, result/page-size/selection
styles and export dialogs. It omits circuit-curation, journal/conference selectors,
IEEE author identities and the IEEE body-index controls. Supported fields are
`all`, `title`, `authors`, `abstract`, and `categories`; publication years are not
invented for preprints. The `year` field and year filters represent first-submission
year derived from the official base arXiv identifier (`year_source=arxiv_identifier`),
not a replacement version date, journal publication year or OAI modification date.

GET `/api/arxiv/papers` additionally accepts `field`, `sort=relevance|year`,
`view=top`, `k=10|20|50|100`, `terms=exact|expand`, `category`, `year_from`, and
`year_to`. Empty queries browse indexed papers. Category filtering matches whole
category codes. Supply comma-separated codes to match **any** selected category (at most 32 distinct codes, 64 characters per code); cross-listed papers appear once. The query cursor binds the complete selection and counts use the same union. Existing single-code URLs remain valid. An archive code with dotted subject classes (`astro-ph`, `cond-mat`,
`cs`, `econ`, `eess`, `math`, `nlin`, `physics`, `q-bio`, `q-fin`, `stat`) matches
every class in that archive, so `eess` matches `eess.SP` and `eess.SY` while `math`
does not match `math-ph`. Equivalent-term expansion reuses the IEEE query interpreter.
arXiv metadata spells many accented names with TeX macros (`Bal\'azs`, `Dim\v{s}a`), which
the index splits into separate words. A query word with accented Latin letters therefore
also matches its TeX spellings, braced or not: `Balázs` and `"C. Balázs"` find
`C. Bal\'azs`, and `Martín` finds `Mart\'{\i}n`. An unaccented query (`Balazs`) still
matches only unaccented metadata, because the index does not record where an accent was.
Cursors bind all active search options. `totals=defer` returns rows first;
`totals=only` computes the exact matching count separately. Failed/timed-out counts
remain unavailable, never zero. Queries have an execution budget and use only the
existing read-only metadata index. GET `/api/arxiv/overview` reports indexed-paper
count and the usable submission-year range, not a claim of complete OAI verification.

Selections belong only to the loaded results; new searches/filters clear selection.
ArXiv citations use arXiv identities and selected versions, never IEEE Xplore URLs
or keys. The batch PDF dialog uses version-bound cache aliases under
`/api/resources/arxiv/`, validates cached files with HEAD, and groups at most 100
files per package/version. Preparing a ZIP is an explicit POST; it reuses the
existing bounded streaming archive machinery with an arXiv file resolver. It does
not acquire missing PDFs, parse PDFs or write metadata. Missing files are reported,
original bytes remain unchanged, and download filenames contain the arXiv ID/version.
The metadata worker/index owner is unchanged; preview configuration can select its
existing full index without rebuilding or changing it.

## Browsing and reading pages

The search page offers circuit-related subject classes as one-click filters and names
every category with the official arXiv taxonomy (`web/src/arxivTaxonomy.ts`; names
stay in English as source terms). Category tags in result rows filter by that exact
class; the free-text category field accepts comma-separated codes, including obsolete ones. The circuit-related shortcuts are multi-select and no longer include an `eess` archive shortcut; archive filters remain supported by the API and explicit category field. An information button beside the heading opens an IEEE-styled guide for all seven shortcuts, with bilingual scope summaries, separate CIRDC reading tips and links to the official taxonomy (reviewed 2026-11-14).

The detail page shows every observed version with its date. Choosing a version pushes
a history entry, so back/forward restore it, and clears the previous version's status
and body before the new version's requests return. An unknown `v` in a link is
reported and replaced by the latest version. Older versions state that the title,
authors and abstract are current metadata. Author names search the authors field;
category labels open the category browse page. License URLs are shortened to their
names (for example `CC BY 4.0`); comments, journal reference, report number and
MSC/ACM classes appear only when the metadata record contains them; comments link their
web addresses. The submitter is shown when recorded. TeX text accents in titles, abstracts,
raw author lists and citations are displayed as letters (`moir\'e` as `moiré`), and copied
titles and abstracts contain the same letters. Math segments and their copied TeX are unchanged.

Each version lists HTML, PDF and TeX source originals plus the reading text with their
own state: cached, queued, fetching, not requested, not offered by arXiv, access
restricted or failed (the offline demo adds "not packaged"). Reads repeat while the version
or any of its files is queued or fetching. Cached originals download through the read-only
file routes. The page offers
at most one upstream action: `ensure` for a version that was never requested, and an
explicit retry for a partial version with failed/restricted originals or a failed
reading conversion. Confirmed absence is final, so a version whose remaining items
are all unavailable offers no action. Polling never submits a request. The shared reader labels reading text by its
provenance: arXiv HTML, converted from TeX source, or converted from PDF.

### Reading paths

arXiv reading text arrives on three paths: official arXiv HTML (`arxiv_html`), LaTeXML
conversion of the TeX source (`arxiv_source`) and PDF conversion (`pdf_parse`). The last
uses the same source value as IEEE PDF conversion, so the detail page tells the shared
reader that the paper is from arXiv (`paperSource`), and the body carries
`data-paper-source="arxiv"` whatever the path. arXiv presentation follows that attribute
(`web/src/arxivReader.css`); IEEE text keeps the shared rules. Nothing in the cached HTML,
TeX, formula copy values or original files changes; all adaptations are display rules:

- LaTeXML equation tables are laid out without grid lines, centred, with the number at the
  right edge; aligned multi-line equations keep their columns.
- `ltx_tabular` tables draw only the rules LaTeXML recorded (`ltx_border_t/tt/b/bb/l/r`).
- Sub-figures sit side by side when there is room; captions use the supporting face.
- Footnotes keep their marker in the sentence and read as an aside below it; theorems,
  itemize/enumerate lists, algorithm listings and references get their own layout.
- The table of contents leaves out the repeated document title and lists the abstract as
  a section.

PDF-converted text has no LaTeXML roles; it keeps the shared paragraph, image, table and
display-math rules. The offline demo serves the two cached HTML bodies and two labelled
representative fixtures for the TeX and PDF paths (see the demo README); no real TeX or
PDF conversion output was available for verification.

## Frontend continuation

For the current IEEE-aligned frontend polish scope, source baseline, behavior
boundaries and validation matrix, use [arXiv frontend handoff](../ARXIV_FRONTEND_HANDOFF.md).

Category-only browsing with no search text follows the newest-indexed order (or
the explicitly selected year order). It does not compute a text-relevance score
for every matching paper. This keeps broad archive browsing within the existing
query budget; text searches retain their relevance ranking.
