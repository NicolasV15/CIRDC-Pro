# Direct HTTP and remote MCP usage

Set `CIRDC_BASE_URL` to the site origin, for example `https://papers.example.org`.
No database, API key or browser session is needed. All paths below are relative
to `/api/agent/v1`. The reader process itself serves HTTP, remote MCP and this
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
Tools: `capabilities`, `search_papers`, `get_paper`,
`ensure_resources`, `get_request`, `read_content`, `get_pdf`. Only resource ensure
and PDF acquisition can create work. Explicit retry is an additional attempt;
ordinary tools do not automatically retry failures.

The server supplies its workflow in initialization instructions and the
`cirdc://research/skill` resource. Resource requests are durable CIRDC receipts,
independent of the MCP connection; reconnect and call `get_request` with the
saved request ID. No additional listener, local Python process or API key is needed.

## Online Skill

An AI with HTTP access can read `/llms.txt` and
`/api/agent/v1/skills/cirdc-research/SKILL.md`, then follow the public API examples.
The reference link inside the Skill resolves to this document on the same site.
Reading the URL provides instructions; it does not automatically install a native
Skill into the AI host. Native installation is optional; the installer below supports a local source
checkout or a download from the running site, without an archive.

## Direct API

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

Resources have independent `missing`, `pending`, `ready`, `partial`, `unavailable`
or `failed` states. `complete=true` means every requested resource is ready.
`202` carries a durable `request_id`, `status_url` and `Retry-After`; continue with
GET, not repeated POST. A partial body can be read even when images or PDF fail.
`200` with `complete=false` is not full success. `404` means the paper, request or
version is unknown; `409` means content/file is not ready; `422` is invalid input;
`429` asks you to reduce request frequency; `503` is a service/storage problem.

Requests for the same paper and resource set share a receipt and active work.
Explicit retry updates that receipt's references and preserves prior attempts.
Receipt reads follow recorded task dependencies rather than whichever task most
recently happened to share the article number. HTTP/client timeouts do not cancel
accepted work. After an ambiguous initial timeout, repeat ensure with retry=false.

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
the symlinks continue to point to that copy. An existing unrelated folder or link
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
