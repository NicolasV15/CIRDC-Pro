import base64
import json
from pathlib import Path

import pytest

from cirdc.model import digest, encoded
from cirdc.remote_io import operation
from cirdc.storage import Dataset
from test_engine import setup as setup, run_id


def request(tmp_path, action, **values):
    return {'root': str(tmp_path / 'data'), 'state': str(tmp_path / 'state'),
            'action': action, **values}


def test_remote_publish_is_atomic_idempotent_and_preserves_backup(tmp_path):
    target = tmp_path / 'data/articleInfo/Journals/4/2026.json'
    target.parent.mkdir(parents=True)
    target.write_text('[{"old":true}]')
    old = target.read_bytes()
    run = 'a' * 32
    content = encoded([{'articleNumber': '7'}])
    staged = operation(request(tmp_path, 'stage', run_id=run, path='articleInfo/Journals/4/2026.json',
                               content=base64.b64encode(content).decode()))
    publish = request(tmp_path, 'publish', run_id=run, path='articleInfo/Journals/4/2026.json',
                      staged_path=staged, digest=digest(content))
    assert operation(publish)['published']
    assert operation(publish)['published']
    assert target.read_bytes() == content
    assert (tmp_path / 'state/backups' / run / 'articleInfo/Journals/4/2026.json').read_bytes() == old
    assert Path(staged).read_bytes() == content


def test_empty_dataset_initialization_never_overwrites_catalogs(tmp_path):
    assert operation(request(tmp_path, 'initialize'))['initialized']
    root = tmp_path / 'data/publicationInfo'
    assert json.loads((root / 'all_journals.json').read_text()) == {}
    content = '{"4":{"title":"Fixture journal"}}'
    (root / 'all_journals.json').write_text(content)
    assert operation(request(tmp_path, 'initialize'))['initialized']
    assert (root / 'all_journals.json').read_text() == content


@pytest.mark.parametrize('path', ['../outside.json', '/etc/passwd', '.'])
def test_remote_paths_cannot_escape_the_data_root(tmp_path, path):
    with pytest.raises(ValueError):
        operation(request(tmp_path, 'read', path=path))


def test_remote_symlink_cannot_expand_shared_scope(tmp_path):
    root = tmp_path / 'data'
    root.mkdir()
    outside = tmp_path / 'private'
    outside.mkdir()
    (outside / 'secret.json').write_text('{}')
    (root / 'parsed_markdown').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        operation(request(tmp_path, 'read', path='parsed_markdown/secret.json'))


def test_remote_digest_failure_preserves_the_previous_file(tmp_path):
    target = tmp_path / 'data/old.json'
    target.parent.mkdir()
    target.write_text('old')
    staged = tmp_path / 'state/staging/a.json'
    staged.parent.mkdir(parents=True)
    staged.write_text('new')
    with pytest.raises(ValueError):
        operation(request(tmp_path, 'publish', run_id='a' * 32, path='old.json',
                          staged_path=str(staged), digest='0' * 64))
    assert target.read_text() == 'old'


def test_remote_export_ack_failure_recovers_from_shared_staging(setup, monkeypatch):
    ctx = setup
    ctx['config'].storage = {'ssh_host': 'fixture', 'state_dir': str(ctx['config'].state_dir)}
    def local_protocol(self, action, **values):
        return operation({'root': str(self.config.data_root), 'state': self.config.storage['state_dir'],
                          'action': action, **values})
    monkeypatch.setattr(Dataset, 'call', local_protocol)
    ctx['service'].storage = Dataset(ctx['config'])
    run = run_id(ctx)
    values = [{**r, 'abstract': 'Remote recovery'} for r in ctx['rows']]
    ctx['store'].stage_export(run, ctx['relative'], values)
    ctx['store'].db.commit()
    execute = ctx['store'].execute
    def broken_ack(sql, params=()):
        if sql.startswith('UPDATE exports SET status'):
            raise RuntimeError('Fixture acknowledgement failure')
        return execute(sql, params)
    monkeypatch.setattr(ctx['store'], 'execute', broken_ack)
    with pytest.raises(RuntimeError):
        ctx['service'].flush_exports(run)
    ctx['store'].db.rollback()
    monkeypatch.setattr(ctx['store'], 'execute', execute)
    assert ctx['store'].counts(run)['exports_pending'] == 1
    ctx['service'].flush_exports(run)
    assert ctx['store'].counts(run)['exports_pending'] == 0
    assert json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]['abstract'] == 'Remote recovery'
