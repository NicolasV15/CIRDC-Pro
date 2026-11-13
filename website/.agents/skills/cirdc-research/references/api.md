# Direct HTTP and remote MCP usage

Set `CIRDC_BASE_URL` to the site origin, for example `https://papers.example.org`.
No database, API key or browser session is needed. IEEE paths below are relative
to `/api/agent/v1`. arXiv uses `/api/arxiv`; see [arXiv access](arxiv.md). The reader process itself serves HTTP, remote MCP and this
online Skill; callers need no archive or local CIRDC installation.

## Remote MCP

In an AI host supporting remote MCP, add this service URL using Streamable HTTP:
`https://papers.example.org/api/agent/v1/mcp`. The site's `/developers/ai` page
generates the address for the current site. For hosts using JSON MCP settings,
the equivalent configuration is:

```json
{
  "mcpServers": {
    "cirdc-research": {
      "type": "http",
      "url": "https://papers.example.org/api/agent/v1/mcp"
    }
  }
}
```

Use the URL field provided by the particular host; configuration formats vary.
IEEE tools: `capabilities`, `search_papers`, `get_paper`,
`ensure_resources`, `get_request`, `read_content`, `get_pdf`. Only resource ensure
and PDF acquisition can create work. The backend may automatically recover execution failures. Follow `next_action` and the existing receipt;
ordinary client polling does not create additional attempts or reset retry limits.

The server supplies its workflow in initialization instructions and the
`cirdc://research/skill` resource. Resource requests are durable CIRDC receipts,
independent of the MCP connection; reconnect and call `get_request` with the
saved request ID. No additional listener, local Python process or API key is needed.

When arXiv is configured, the same MCP connection also advertises `search_arxiv`,
`resolve_arxiv`, `get_arxiv_paper`, `get_arxiv_resources`, `ensure_arxiv_resources`,
`get_arxiv_request` and `read_arxiv_content`. Discover tools at runtime rather than
assuming every site supports arXiv. See [arXiv examples and states](arxiv.md).

## Online Skill

An AI with HTTP access can read `/llms.txt` and
`/api/agent/v1/skills/cirdc-research/SKILL.md`, then follow the public API examples.
The reference link inside the Skill resolves to this document on the same site.
Reading the URL provides instructions; it does not automatically install a native
Skill into the AI host. Native installation is optional; the installer below supports a local source
checkout or a download from the running site, without an archive.

## Direct API

The capabilities response advertises resource_contract_version=2. Resource ensure has no per-IP attempt or frequency quota. Source requests retain per-egress spacing and shared capacity; use GET receipt polling after admission.

```sh
curl "$CIRDC_BASE_URL/api/agent/v1/papers?q=ring%20amplifier&limit=20"
curl -X POST "$CIRDC_BASE_URL/api/agent/v1/papers/ARTICLE_NUMBER/ensure" \
  -H 'Content-Type: application/json' \
  -d '{"resources":["content","pdf"],"wait_seconds":10,"retry":false}'
curl "$CIRDC_BASE_URL/api/agent/v1/requests/REQUEST_ID"
curl "$CIRDC_BASE_URL/api/agent/v1/papers/ARTICLE_NUMBER/content?format=markdown"
```

Replace `ARTICLE_NUMBER` and `REQUEST_ID` with actual returned values. Download
PDF bytes from the response's resource URL only after its state is `ready`.

Fetch `/api/agent/v1/openapi.json` for the complete interface. `GET /capabilities`
describes available providers; installation alone does not configure a source.

PDF states are `missing`, `pending`, `ready`, and `unavailable`. A confirmed
`institution_not_licensed` outcome completes normally with no download link.
`complete=true` means every requested resource is ready or has the confirmed
`institution_not_licensed` outcome; always check PDF state before downloading.
Content can additionally be partial or failed. Pending responses include
acquisition_id, phase and next_action=wait. Ordinary source errors recover across
eligible nodes without an attempt cap; PDF-to-text conversion uses a separate
bounded recovery policy. GET remains read-only.

Interpret receipt flags and each resource's next_action together:

| Response | Client action |
| --- | --- |
| `pending=true`, resource `next_action=wait` | Poll the saved receipt within the caller's wait budget. |
| `pending=false`, `complete=true` | Report each outcome; download only a PDF whose own state is ready. |
| `pending=false`, `complete=false`, resource `next_action=contact_administrator` or `stop` | Terminal failure, even with HTTP 200. Report the resource message and retain the receipt; do not poll or resubmit it automatically. |
| One resource terminal and another still pending | Report the failed branch and keep usable resources; poll the same receipt only for the branch still waiting. |

A partial body can remain readable after conversion or image recovery stops.
Its partial state alone does not authorize more polling or another ensure.
Ensure creates or joins durable work and accepts optional client_id, channel
(browser/api), and automatic (background prefetch). Explicit requests promote
existing background work. HTTP waits remain 0-30 seconds and do not limit task life.

Content responses include `version`, `source`, `toc`, `blocks`, `content`, image
counts, `warnings` and `next_cursor`. Subsequent cursors select the original version
even when newer content is published. The page target is 12,000 characters (range
1,000–48,000); a single larger block stays intact with a warning. Use block and
section IDs for navigation. Source HTML remains available with `format=html`.
PDF and versioned asset links are ordinary public HTTP downloads. Relative URLs
are resolved against the configured site origin; helper responses include absolute
URL fields. Never interpret receipt IDs as secrets or authentication tokens.

## Optional command-line helper

Developers already using this source checkout can run
`scripts/cirdc_client.py` from the Skill directory with Python 3.10+. It uses the
standard library and is optional for both direct HTTP and hosted MCP:

```sh
python scripts/cirdc_client.py --base-url "$CIRDC_BASE_URL" capabilities
python scripts/cirdc_client.py search 'ring amplifier' --year-from 2020 --limit 20
python scripts/cirdc_client.py ensure ARTICLE_NUMBER --resources content pdf --wait-seconds 10
python scripts/cirdc_client.py status REQUEST_ID --wait-seconds 10
python scripts/cirdc_client.py read ARTICLE_NUMBER --cursor NEXT_CURSOR
python scripts/cirdc_client.py pdf ARTICLE_NUMBER --output article.pdf
```

The helper only saves a ready PDF and refuses to overwrite an existing file.

## Native Skill installation

Codex and Claude Code can discover the same Skill through local folder symlinks.
The installer runs with Python 3.10+ and only its standard library (macOS/Linux).
Use your actual site origin in place of the example. From a local terminal:

```sh
curl --fail --location --silent --show-error \
  https://papers.example.org/api/agent/v1/skills/cirdc-research/scripts/install_skill.py \
  --output cirdc-install-skill.py
python3 cirdc-install-skill.py --base-url https://papers.example.org --agent codex
# For Claude Code, choose --agent claude-code; --agent all installs both links.
```

This creates one maintained local copy and the selected symlink(s):

| Location | Purpose |
| --- | --- |
| `~/.local/share/cirdc/skills/cirdc-research/` | Downloaded Skill, API reference and standard-library scripts |
| `~/.agents/skills/cirdc-research` | Codex user Skill symlink |
| `~/.claude/skills/cirdc-research` | Claude Code personal Skill symlink |
| `~/.config/cirdc/research.json` | Current site origin, outside the Skill and source repository |

Open a new Codex session and invoke `$cirdc-research`, or run `/reload-skills` in
Claude Code and invoke `/cirdc-research`. The Skill can also be selected by relevance.
Explicit site arguments and `CIRDC_BASE_URL` override the saved origin. Both hosts
share the current saved site; rerunning with another origin changes that choice.
The installer checks the site's research capabilities before saving configuration
or publishing links. These commands already select the site, so no URL prompt is
needed during installation or subsequent Skill use.
No agent settings or MCP configuration are edited. For remote MCP tools, configure
the connection separately as described above. A successful connection check proves
research API access at setup time, not future availability or resource completeness.

To update a downloaded Skill, download the current installer and rerun the same
command. Downloads finish and validate before the maintained copy is replaced;
the symlinks continue to point to that copy. See the version, checksum and modification protections below. An existing unrelated folder or link
is refused, including a broken link to another target. Move it explicitly before
installing. The installer updates only its marked local cache.

### Install from source or an SSH checkout

From a full repository checkout, use the root entrypoint. It automatically locates
the canonical Skill folder and completes site configuration without backend setup:

```sh
sh tools/install-skill --agent codex
sh tools/install-skill --agent claude-code
# Both hosts, also supported from outside the checkout:
sh /path/to/CIRDC-Pro/tools/install-skill --agent all
```

On first installation in a terminal, choose the site when prompted; pressing Enter
selects `http://127.0.0.1:18088` on the machine executing the helper. Enter the
reachable remote origin when the reader runs on a different machine. Existing
configuration is reused on updates. To supply the choice without a prompt, add
`--base-url https://papers.example.org` or set `CIRDC_BASE_URL`. Without a terminal,
the installer checks the saved or local default site; a failure ends installation
with a setup command, rather than deferring configuration to first use.

The research API is checked and `~/.config/cirdc/research.json` is written before
installation is reported complete. This source mode does not download or modify
the Skill. Source updates are visible through the links; keep the checkout at its
installed path. For intentional offline setup, use an explicit or saved address
with `--skip-check`; the output records that connectivity was not verified.

### Reconfigure without reinstalling

Run the same setup program when choosing or changing the site:

```sh
sh tools/install-skill --configure
# Supply a remote address directly, including from scripts:
sh tools/install-skill --configure --base-url https://papers.example.org
# Or from a downloaded/installed Skill:
python3 ~/.agents/skills/cirdc-research/scripts/install_skill.py --configure
```

`--configure` does not need `--agent` and does not change any Skill symlink or MCP
configuration. Additional existing JSON preferences are preserved. During research,
the helper never prompts for a URL: a missing configuration reports incomplete
installation, while an unavailable configured site reports a connection error.

If an agent accesses a source checkout over SSH while its AI host discovers Skills
on another computer, run the following on the **AI host computer**, substituting
your source SSH host and repository path. Only this self-contained Skill is copied:

```sh
mkdir -p "$HOME/.local/share/cirdc/source-skills"
scp -r developer@source-host:/path/to/CIRDC-Pro/website/.agents/skills/cirdc-research \
  "$HOME/.local/share/cirdc/source-skills/"
python3 "$HOME/.local/share/cirdc/source-skills/cirdc-research/scripts/install_skill.py" \
  --source "$HOME/.local/share/cirdc/source-skills/cirdc-research" --agent all
```

The Skill files come from the local copy, not the website. Site selection and the
connection check still happen during installation; for intentional offline setup,
pass `--base-url` with `--skip-check`. To update the transferred copy, copy the
source Skill again; the local symlinks stay valid.
A remote filesystem path or HTTP URL cannot be a local symlink target. An AI host
executing on the source computer can link that checkout directly; installing in a
remote user's home does not configure a local AI application. Other Agent Skills
hosts can link the same local folder into their documented discovery directory.

Remove only an installer's matching symlink with:

```sh
python3 cirdc-install-skill.py --agent codex --uninstall
# For a source checkout, run: sh tools/install-skill --agent codex --uninstall
# For a copied Skill, use its installer with the same --source directory.
```

Removal retains the Skill copy and site configuration for other clients. To switch
between a download and a checkout installation, remove the old matching link first.
The local HTTP helper automatically reads the saved site and can be run from any
project by its full installed path, for example:

```sh
python3 ~/.agents/skills/cirdc-research/scripts/cirdc_client.py capabilities
```

The discovery directories and symlink behavior follow the official
[Codex Skill documentation](https://developers.openai.com/codex/skills/) and
[Claude Code Skill documentation](https://code.claude.com/docs/en/skills).

## Skill version and updates

`version.json` is the sole release manifest. Its independent stable SemVer
`MAJOR.MINOR.PATCH` is unrelated to API v1 or the website Python package. The first
version is **1.0.0**: the established research workflow now has a verified release
contract. Breaking workflow/installer changes increment MAJOR; compatible features
increment MINOR; fixes and instruction/reference/UI metadata changes increment PATCH.
Any changed distributed file needs a new version after publication; development
edits may share an unreleased version. Website-only changes need no Skill bump.
The manifest holds short bilingual notes, Python/API/installer compatibility, and
SHA-256 plus byte length for every distributed file (including host UI metadata).
The manifest excludes its own checksum; the installed managed record checks it.
Maintainers edit version/notes/compatibility here and regenerate the inventory with
`python3 website/tools/skill_release.py --write`; the default command and package
build refuse stale hashes. The same bytes are packaged and served online.
Checksums detect inconsistent or incomplete delivery; they are not a signature.
Use a trusted site and HTTPS when available.

The local helper checks once on client initialization, and the installer checks
after successful installation. Checks access **only** this site's `version.json`,
with a 2-second socket timeout and 64 KiB response limit. Both successes and
failures are cached for 24 hours per site/Skill location/current version under
`~/.cache/cirdc/skill-updates/`; concurrent invocations share a lock. Status polling
and individual API requests do not check again. There are no scheduled jobs or
resident processes. Offline, timeout, malformed or missing manifests (old servers)
leave normal research calls working.

Checks do not install anything. There is no verified host startup hook; the
trigger is **first Skill use in a conversation** (`updates status`) or local
helper startup, never a promise that opening the AI application triggers a check.
Normal helper startup emits a `CIRDC_SKILL_UPDATE` event only on **stderr**, leaving
stdout business JSON unchanged. The event includes current/latest versions,
bilingual short notes, compatibility, update method and confirmation question.
The Agent shows these details and asks “是否更新？” / “Would you like to update?”.
Only explicit agreement permits running the official installer, pinned with
`--expected-version <approved version>`; a changed server version stops the install
and needs a fresh decision. No reply or a deferral means continuing normal work on
the old release. Accepted resource requests are never replayed for an update.

Cached releases remain available to `updates status` without another network
request. The Skill asks at most once per conversation and normal helper startup
announces a particular version once per local cache. These local commands can be
called by the Agent after the user's choice (substitute the actual installed path):

```sh
python3 ~/.agents/skills/cirdc-research/scripts/cirdc_client.py updates status
python3 ~/.agents/skills/cirdc-research/scripts/cirdc_client.py updates snooze --hours 24
python3 ~/.agents/skills/cirdc-research/scripts/cirdc_client.py updates skip --version 1.0.0
python3 ~/.agents/skills/cirdc-research/scripts/cirdc_client.py updates disable
```

Snoozing delays reminders (1–720 hours); skipping suppresses that exact release,
not later ones. Update preference commands intentionally return their own JSON;
normal research commands retain their original JSON schema. No helper calls
`input()` to wait for an update answer. Set `CIRDC_SKILL_UPDATE_CHECK=0`, or preserve
other preferences and add `"check_updates": false` in
`~/.config/cirdc/research.json` to disable checks. To re-enable, remove the environment
override and set `check_updates` to true. Deleting the cache resets notice/skip
history. `--skip-check` suppresses the installer's automatic connectivity/update
checks for intentional offline **source** setup.

After an approved update, subsequent helper processes use the complete new code.
An already imported client/module finishes on its loaded code; restart/reimport
before using the new code. AI sessions cannot reliably hot-reload instructions:
reload Skills or start a new session. The updater never interrupts an in-flight
request, switches its code, or repeats a previously accepted operation.

After a successful install, `~/.config/cirdc/skill-installations.json` records the
actual version, install mode and file hashes by installation path. Installer JSON also lists `modified_files`
when a source working copy differs from its declared release; it is preserved,
not represented as byte-identical to that published release. Downloaded
copies also carry a `.cirdc-managed` record. Source links read the current source
manifest when used, so changing checkout versions is visible immediately; the
installation registry remains the last successful installer observation. Source
working edits are not a published release; regenerate/check before distribution.

For downloads, rerun the current official installer with the same `--agent` choice
and saved site (or use the AI dialog's online installation prompt). It downloads
and verifies every file into staging, then replaces the managed directory on the
same filesystem with rollback on activation failure. Site settings and unrelated
files are retained. Modified managed files, path collisions, unmanaged folders or
internal symlinks are refused: review/move your changes explicitly and rerun.
There is no force-overwrite option. Known unversioned copies can migrate only
when every file matches a frozen known release checksum; unknown copies are
preserved for manual review. Servers without a manifest cannot provide a verified
new download; existing helpers keep working, or use a verified source checkout.
For source links (including SSH-transferred source copies), update that particular
checkout/copy through its normal owner workflow, then rerun `tools/install-skill`
or the copied installer's `--source` command. The helper never runs `git pull`,
`reset` or modifies a shared checkout. Do not replace a source link with a download.

### Forwardable update notice / 可转发更新通知

CIRDC-Pro now distributes an independently versioned research Skill. **Local
Skill users with an older copy must manually update once**, using this site's AI
access dialog → online installation prompt; preserve site settings and local
edits. For source-linked installs, ask the checkout owner to update the source and
rerun the source installer instead. Subsequent local helper/installer invocations
check on first use/helper startup and cache results for a day. The Agent shows versions and notes, asks whether to update, and installs only after explicit agreement. No reply means continuing with the old version. Snooze, skip-release and opt-out controls are available. **Remote
MCP/HTTP-only users** need no local installation update: online guidance comes
from the site; they receive no local-version reminder. **Ordinary website users**
need no Skill update. The webpage shows the available release, never whether a
particular computer is current.

CIRDC-Pro research Skill 已增加独立版本和更新提醒。**已安装本地 Skill 的旧用户需先手动更新一次**：
进入所用站点的「AI 接入」弹窗，使用在线安装 prompt，保留站点设置及本地修改。
源码软链接用户请由源码维护者更新对应 checkout 或复制目录，再重跑源码安装器。
此后首次使用 Skill 或 helper 启动时轻量检查，结果缓存 24 小时。Agent 展示当前／最新版本和说明并询问“是否更新？”，只有明确同意才升级；未回复或暂不更新继续旧版。支持稍后提醒、跳过此版本及关闭检查，源码软链接不自动修改 Git。没有保证打开 AI 工具就触发的启动钩子；更新后需重新加载 Skill 或开启新会话。
**仅用远程 MCP／HTTP 的用户**不必更新本地 Skill，在线说明随站点提供，也没有本机版本提醒；
**普通网页用户**无需安装或更新 Skill。网页只展示本站可安装版本，不能判断本机是否最新。

## Busy responses and time budgets

Read cached content first. Only `409 content_not_ready` permits ensure; if the
response supplies a receipt, query that receipt instead. A 503 is a service error,
not evidence of missing content. Preserve `message`, `next_action`,
`retry_after_seconds`, `request_id` and `status_url`. HTTP `Retry-After` matches
the JSON interval. A 429 interval reflects the remaining rate-limit window.
A confirmed unavailable PDF is terminal; pending acquisition continues through its receipt.

Ensure's processing budget is `wait_seconds + 10` seconds from validated parameters,
including metadata lookup and submission; `wait_seconds=0` has a ten-second budget
and does not wait for resource completion. Receipt/capabilities reads have a
ten-second budget; content JSON has ten seconds. These budgets exclude network
transfer and do not limit PDF/image streaming. Capabilities reports budgets and
internal bounded execution pools with queued admission. Resource ensure has no per-IP quota. Local execution pools are not acquisition-attempt limits.

The local helper's `status --wait-seconds N` polls within its own wait budget.
When that budget expires after a successful pending read, it returns the last
receipt, still pending, without another poll or resubmission. This does not cancel
the acquisition or claim that it has completed. Real HTTP errors and connection
failures remain errors; a timeout before any receipt is read remains an error too.
With `--wait-seconds 0`, the helper reads once with its normal transport timeout;
zero disables repeated polling, not the server's ten-second processing budget.

On ensure errors, `accepted=true` means submission was confirmed, `false` means
not submitted, and `null` means unknown. Only a committed receipt is returned as a
receipt. When submission times out, the synchronous hook can still finish and save
its receipt; it retains its execution slot until completion. Without a receipt,
back off, read first, then resume an ordinary ensure with `retry=false` if needed.
Ensure is idempotent and needs no retry flag. Polling never submits work. Preserve usable content and original failure history.

`/healthz` checks website liveness; it does not report resource worker capacity.


## Durable resource acquisition

Ordinary source acquisition survives disconnects and restarts; individual source
attempt failures remain diagnostics while next_action=wait. PDF-to-text conversion
can terminate under its independent recovery policy. Follow the receipt decision
table above instead of treating every incomplete result as pending. PDF ready and
confirmed institutional non-entitlement are normal terminal outcomes. Use
wait_seconds=0 for submission bursts. Stable client_id and channel provide fair
scheduling between API callers and browser users.
