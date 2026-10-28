#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v uv >/dev/null 2>&1; then
  cirdc_uv=$(command -v uv)
else
  cirdc_tools="${XDG_DATA_HOME:-$HOME/.local/share}/cirdc/tools"
  cirdc_uv="$cirdc_tools/uv"
  if [ ! -x "$cirdc_uv" ]; then
    cirdc_installer=$(mktemp)
    trap 'rm -f "$cirdc_installer"' EXIT HUP INT TERM
    curl --fail --location --silent --show-error --connect-timeout 15 --max-time 120 https://astral.sh/uv/install.sh -o "$cirdc_installer"
    UV_UNMANAGED_INSTALL="$cirdc_tools" sh "$cirdc_installer"
  fi
fi
if [ ! -x "$project/.venv/bin/python" ]; then
  "$cirdc_uv" venv --python 3.12 "$project/.venv"
fi
"$cirdc_uv" pip install --python "$project/.venv/bin/python" --reinstall-package cirdc-pro "$project[dev]"
printf '%s\n' 'CIRDC_ENVIRONMENT_READY' 'Next: sh tools/cirdc --help; configure a private target, then db-check.'
