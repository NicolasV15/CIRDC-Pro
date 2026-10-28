"""Compatibility entry: use the structured cirdc command for new workflows."""
import sys
from cirdc.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["update", "--stage", 'enrich', *sys.argv[1:]]))
