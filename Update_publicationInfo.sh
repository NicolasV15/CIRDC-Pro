#!/bin/sh
set -eu
exec cirdc update --stage catalog "$@"
