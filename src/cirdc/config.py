import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    data_root: Path
    state_dir: Path
    mysql: dict = field(default_factory=dict, repr=False)
    interval: float = 1.0
    connect_timeout: int = 5
    read_timeout: int = 30
    retries: int = 3
    workers: int = 1
    ssh_tunnel: dict = field(default_factory=dict, repr=False)
    storage: dict = field(default_factory=dict)
    database_id: str | None = None
    config_path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, filename=None):
        path = Path(filename or os.environ.get('CIRDC_CONFIG', Path.home() / '.config/cirdc/config.json')).expanduser()
        if path.exists():
            from .profiles import private_path
            private_path(path)
        values = json.loads(path.read_text()) if path.exists() else {}
        root = values.get('data_root', os.environ.get('CIRDC_DATA_ROOT'))
        if not root:
            here = Path.cwd()
            root = next((p for p in [here, *here.parents] if (p / 'publicationInfo').is_dir()), here)
        db = values.get('mysql', {})
        for name in ['host', 'port', 'database', 'user', 'password']:
            value = os.environ.get('CIRDC_MYSQL_' + name.upper())
            if value is not None:
                db[name] = int(value) if name == 'port' else value
        remote = values.get('storage', {})
        workers = int(values.get('workers', 1))
        if not 1 <= workers <= 8:
            raise ValueError('workers must be between 1 and 8')
        data_root = Path(root) if remote.get('ssh_host') else Path(root).expanduser().resolve()
        if remote.get('ssh_host') and (not data_root.is_absolute() or not remote.get('state_dir')):
            raise ValueError('SSH storage requires an absolute data root and remote state directory')
        return cls(data_root,
                   Path(values.get('state_dir', Path.home() / '.local/state/cirdc')).expanduser(), db,
                   max(1.0, float(values.get('interval', 1))),
                   int(values.get('connect_timeout', 5)), int(values.get('read_timeout', 30)),
                   max(1, min(3, int(values.get('retries', 3)))), workers,
                   values.get('ssh_tunnel', {}), remote, values.get('database_id'), path.expanduser().resolve())

    def destination(self, relative):
        if self.storage.get('ssh_host'):
            from pathlib import PurePosixPath
            part = PurePosixPath(relative)
            if part.is_absolute() or '..' in part.parts or not part.parts:
                raise ValueError('Destination must stay inside the data root')
            return self.data_root / relative
        path = (self.data_root / relative).resolve()
        if not path.is_relative_to(self.data_root) or path == self.data_root:
            raise ValueError('Destination must stay inside the data root')
        return path

    def public(self):
        return {'data_root': str(self.data_root), 'state_dir': str(self.state_dir),
                'database_configured': bool(self.mysql.get('user')), 'interval': self.interval,
                'database_target': {'database': self.mysql.get('database'),
                                    'host': self.ssh_tunnel.get('host', self.mysql.get('host', 'localhost')),
                                    'transport': 'ssh' if self.ssh_tunnel else 'direct',
                                    'identity_pinned': bool(self.database_id)},
                'connect_timeout': self.connect_timeout, 'read_timeout': self.read_timeout,
                'retries': self.retries, 'workers': self.workers,
                'ssh_tunnel': {'enabled': bool(self.ssh_tunnel),
                               'host': self.ssh_tunnel.get('host'),
                               'local_port': self.ssh_tunnel.get('local_port')},
                'storage': {'mode': 'ssh' if self.storage.get('ssh_host') else 'local',
                            'host': self.storage.get('ssh_host')}}
