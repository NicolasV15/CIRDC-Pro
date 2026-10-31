#!/bin/sh
set -eu
project=$(CDPATH= cd -P -- "$(dirname -- "$0")" && cd .. && pwd -P)
exec sh "$project/../tools/claude.sh" "$@"
