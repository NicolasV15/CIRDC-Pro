from typing import Any
from mcp.server.fastmcp import FastMCP
from .api import invoke, result

server = FastMCP('cirdc')


@server.tool(structured_output=True)
def doctor(network: bool = False) -> dict[str, Any]:
    """Inspect storage, database readiness, and optionally metadata source access."""
    return invoke('doctor', network=network)


@server.tool(structured_output=True)
def plan_update(publication: str | None = None, year: int | None = None) -> dict[str, Any]:
    """Inspect the all-publication metadata update scope without starting a job."""
    return invoke('plan', publication=publication, year=year)


@server.tool(structured_output=True)
def start_update(publication: str | None = None, year: int | None = None) -> dict[str, Any]:
    """Start or reuse a resumable bibliographic, abstract, and keyword update job."""
    return invoke('update', publication=publication, year=year)


@server.tool(structured_output=True)
def run_status(run_id: str | None = None) -> dict[str, Any]:
    """Read completion counts, outstanding work, and failures for a metadata job."""
    return invoke('status', run_id=run_id)


@server.tool(structured_output=True)
def resume_update(run_id: str) -> dict[str, Any]:
    """Resume an interrupted or paused job from persisted checkpoints."""
    return invoke('resume', run_id=run_id)


@server.tool(structured_output=True)
def retry_update(run_id: str) -> dict[str, Any]:
    """Retry failed work within its bounded task-attempt limit."""
    return invoke('retry', run_id=run_id)


@server.tool(structured_output=True)
def get_paper(article_number: str) -> dict[str, Any]:
    """Read one locally indexed article and its field coverage states."""
    return invoke('paper', number=article_number)


@server.tool(structured_output=True)
def analyze_relations(article_number: str, direction: str = 'references', depth: int = 3) -> dict[str, Any]:
    """Explicitly analyze article relationships; never part of a default update."""
    from .analysis import analyze
    from .config import Config
    return result(analyze(Config.load(), article_number, direction, depth))


@server.tool(structured_output=True)
def author_init() -> dict[str, Any]:
    """Initialize only the optional empty author schema; no network collection."""
    from .author_cli import invoke_author
    return invoke_author('init')


@server.tool(structured_output=True)
def author_fetch(author_id: str, output: str) -> dict[str, Any]:
    """Fetch exactly one IEEE author to a portable sanitized JSON file; no database needed."""
    from .author_cli import invoke_author
    return invoke_author('fetch', author_id=author_id, output=output)


@server.tool(structured_output=True)
def author_import(path: str) -> dict[str, Any]:
    """Import one sanitized author JSON snapshot without contacting IEEE."""
    from .author_cli import invoke_author
    return invoke_author('import', path=path)


@server.tool(structured_output=True)
def author_update(author_id: str) -> dict[str, Any]:
    """Explicitly fetch and save one IEEE author. Never traverse coauthors or all paper authors."""
    from .author_cli import invoke_author
    return invoke_author('update', author_id=author_id)


@server.tool(structured_output=True)
def author_show(author_id: str) -> dict[str, Any]:
    """Read one stored author profile and its latest attempt status without network access."""
    from .author_cli import invoke_author
    return invoke_author('show', author_id=author_id)


def serve():
    server.run(transport='stdio')
