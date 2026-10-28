"""Private deployment profiles and a project-local pointer without credentials."""
import getpass
import json
import os
from pathlib import Path
import tempfile


def private_path(path):
    path = Path(path).expanduser().resolve()
    if any((p / '.git').exists() for p in [path.parent, *path.parents]):
        raise ValueError('Deployment profiles must be saved outside Git checkouts')
    return path


def save_private(path, value, overwrite=False):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists() and not overwrite:
        raise ValueError('Target configuration already exists; select a new output path')
    content = (json.dumps(value, indent=2) + '\n').encode()
    if not overwrite:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
    else:
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return path


def bind(config, identity):
    if not config.config_path or not config.config_path.is_file():
        raise ValueError('Identity binding requires an existing private profile')
    values = json.loads(config.config_path.read_text())
    values['database_id'] = identity['instance_id']
    save_private(config.config_path, values, overwrite=True)
    return str(config.config_path)


def config_init(output):
    """The wizard reads credentials only from the user's terminal."""
    if not os.isatty(0):
        raise ValueError('config-init requires an interactive terminal; use a private profile or environment variables for automation')
    host = input('Database host [127.0.0.1]: ').strip() or '127.0.0.1'
    port = int(input('Database port [3306]: ').strip() or '3306')
    database = input('Database name: ').strip()
    user = input('Application account: ').strip()
    password = getpass.getpass('Application password (saved only in the private profile): ')
    root = Path(input('Absolute JSON data directory: ').strip()).expanduser().resolve()
    if not database or not user or not 1 <= port <= 65535:
        raise ValueError('A database, application account, and valid port are required')
    value = {'data_root': str(root), 'state_dir': str(Path.home() / '.local/state/cirdc'),
             'mysql': {'host': host, 'port': port, 'database': database, 'user': user, 'password': password},
             'workers': 1, 'interval': 1, 'connect_timeout': 5, 'read_timeout': 30, 'retries': 3}
    path = save_private(output, value)
    return {'status': 'configured', 'config_path': str(path), 'next': 'db-check'}


def select(config, project):
    from .store import Store
    store = Store(config)
    try:
        report = store.require_schema(force=True)
    finally:
        store.close()
    if not config.database_id:
        bind(config, report['identity'])
    project = Path(project).expanduser().resolve()
    if not (project / 'AGENTS.md').is_file() or not (project / 'pyproject.toml').is_file():
        raise ValueError('Select the CIRDC-Pro project directory')
    pointer = project / '.cirdc/active-target'
    pointer.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=pointer.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(str(config.config_path) + '\n')
        os.replace(temporary, pointer)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'status': 'selected', 'profile_path': str(config.config_path), 'database_id': report['identity']['instance_id']}
