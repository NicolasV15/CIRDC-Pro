"""Start a project agent with the checked-out CLI, without editing global settings."""
import json
import os
from pathlib import Path
import subprocess
import sys


def command(client, extra):
    root = Path(__file__).resolve().parents[1]
    if client == 'codex':
        options = ['-C', str(root), '-c', 'mcp_servers.cirdc.command="sh"',
                   '-c', 'mcp_servers.cirdc.args=' + json.dumps([str(root / 'tools/cirdc'), 'mcp'])]
        explicit = os.environ.get('CIRDC_CODEX_BIN')
        executable = explicit or 'codex'
        bundled = Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex')
        if not explicit and bundled.is_file():
            # Some older PATH clients cannot parse settings written by the current app.
            # Probe configuration without changing it; use the installed app client if needed.
            try:
                check = subprocess.run([executable, *options, 'mcp', 'get', 'cirdc'],
                                       capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                check = None
            if check is None or check.returncode:
                executable = str(bundled)
        return [executable, *options, *extra]
    return [os.environ.get('CIRDC_CLAUDE_BIN', 'claude'), *extra]


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    raise SystemExit(subprocess.run(command(sys.argv[1], sys.argv[2:]), cwd=root).returncode)
