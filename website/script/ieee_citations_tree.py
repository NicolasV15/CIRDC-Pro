import sys
from cirdc.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["analyze", 'tree', *sys.argv[1:]]))
