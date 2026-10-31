import base64
import json
import os
from pathlib import Path

from . import remote_io
from .ssh import SSH, SSHError


class Dataset:
    def __init__(self, config):
        self.config = config
        self.remote = bool(config.storage.get('ssh_host'))
        self.channel = None
        if self.remote:
            tunnel = config.ssh_tunnel if config.ssh_tunnel.get('host') == config.storage['ssh_host'] else None
            self.channel = SSH(config.storage['ssh_host'], tunnel)

    def call(self, action, **params):
        payload = {'root': str(self.config.data_root), 'state': self.config.storage['state_dir'],
                   'action': action, **params}
        source = Path(remote_io.__file__).read_text()
        result = json.loads(self.channel.python(source, payload, self.config.storage.get('python', 'python3.12')))
        if not result.get('ok'):
            raise SSHError('Remote filesystem operation failed; staging and database checkpoints were retained')
        return result['value']

    def probe(self):
        if self.remote:
            return self.call('probe')
        root = self.config.data_root
        return {'data_root_exists': root.is_dir(), 'data_root_writable': os.access(root, os.W_OK),
                'publication_indexes': all((root / 'publicationInfo' / n).exists()
                                           for n in ('all_journals.json', 'all_conferences.json'))}

    def initialize(self):
        if self.remote:
            return self.call('initialize')
        return remote_io.operation({'root': str(self.config.data_root), 'state': str(self.config.state_dir),
                                    'action': 'initialize'})

    def read_bytes(self, relative):
        self.config.destination(relative)
        if self.remote:
            value = self.call('read', path=relative)
            return base64.b64decode(value) if value is not None else None
        path = self.config.destination(relative)
        return path.read_bytes() if path.exists() else None

    def read_json(self, relative, default=None):
        content = self.read_bytes(relative)
        return json.loads(content) if content is not None else ({} if default is None else default)

    def article_paths(self):
        if self.remote:
            return self.call('article_paths')
        return sorted(str(p.relative_to(self.config.data_root))
                      for p in (self.config.data_root / 'articleInfo').rglob('*.json'))

    def years(self, kind):
        if self.remote:
            return self.call('years', kind=kind)
        folder = self.config.data_root / 'publicationInfo' / kind
        return [int(p.name) for p in folder.iterdir() if p.is_dir() and p.name.isdigit()] if folder.exists() else []

    def stage(self, run_id, relative, content):
        return self.call('stage', run_id=run_id, path=relative, content=base64.b64encode(content).decode())

    def stage_patch(self, run_id, relative, updates):
        self.config.destination(relative)
        return self.call('stage_patch', run_id=run_id, path=relative, updates=updates)

    def publish(self, export):
        return self.call('publish', run_id=export['run_id'], path=export['path'],
                         staged_path=export['staged_path'], digest=export['digest'])
