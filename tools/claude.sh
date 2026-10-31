#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$project/.venv/bin/python" "$project/tools/agent_launcher.py" claude "$@"
