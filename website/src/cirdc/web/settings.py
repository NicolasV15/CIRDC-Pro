import os
from pathlib import Path


def state_dir():
    path = Path(os.environ.get('CIRDC_WEB_STATE', Path.home() / '.local/state/cirdc-web')).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def connect(name):
    import sqlite3
    path = state_dir() / name
    db = sqlite3.connect(path, timeout=5)
    path.chmod(0o600)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA busy_timeout=5000')
    if name == 'search.sqlite':
        db.execute('PRAGMA synchronous=NORMAL')
        db.execute('PRAGMA cache_size=-131072')
        db.execute('PRAGMA temp_store=MEMORY')
    return db
