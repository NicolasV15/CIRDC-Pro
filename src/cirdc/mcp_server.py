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


def serve():
    server.run(transport='stdio')
