"""Cross-platform environment setup for source checkouts or a transferred wheel."""
import argparse
import json
from pathlib import Path
import os
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--wheel', type=Path)
parser.add_argument('--environment', type=Path, default=Path.cwd() / '.venv')
args = parser.parse_args()
environment = args.environment.expanduser().resolve()
if (environment / '.cirdc-runtime-protected').is_file():
    parser.error('Protected collection runtime; choose a different --environment for development')
subprocess.check_call([sys.executable, '-m', 'venv', str(environment)])
executable = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
target = str(args.wheel.expanduser().resolve()) if args.wheel else str(Path(__file__).resolve().parents[1]) + '[dev]'
subprocess.check_call([str(executable), '-m', 'pip', 'install', '--disable-pip-version-check',
                       '--upgrade', '--force-reinstall', target])
print(json.dumps({'status': 'ready', 'python': str(executable),
                  'entry': str(environment / ('Scripts/cirdc.exe' if os.name == 'nt' else 'bin/cirdc'))}))
