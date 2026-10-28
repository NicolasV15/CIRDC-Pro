#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec codex -C "$project" -c 'mcp_servers.cirdc.command="cirdc"' -c 'mcp_servers.cirdc.args=["mcp"]' "$@"
