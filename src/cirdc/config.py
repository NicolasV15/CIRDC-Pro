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

    @classmethod
    def load(cls, filename=None):
        path = Path(filename or os.environ.get('CIRDC_CONFIG', Path.home() / '.config/cirdc/config.json'))
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
        return cls(Path(root).expanduser().resolve(),
                   Path(values.get('state_dir', Path.home() / '.local/state/cirdc')).expanduser(), db,
                   max(1.0, float(values.get('interval', 1))),
                   int(values.get('connect_timeout', 5)), int(values.get('read_timeout', 30)),
                   max(1, min(3, int(values.get('retries', 3)))))

    def destination(self, relative):
        path = (self.data_root / relative).resolve()
        if not path.is_relative_to(self.data_root) or path == self.data_root:
            raise ValueError('Destination must stay inside the data root')
        return path

    def public(self):
        return {'data_root': str(self.data_root), 'state_dir': str(self.state_dir),
                'database_configured': bool(self.mysql.get('user')), 'interval': self.interval,
                'connect_timeout': self.connect_timeout, 'read_timeout': self.read_timeout,
                'retries': self.retries}
