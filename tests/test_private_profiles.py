import json

import pytest

from cirdc.profiles import save_private, select
from cirdc.config import Config
from test_engine import setup as setup


def test_deployment_profile_is_refused_even_in_an_ignored_git_path(tmp_path):
    root = tmp_path / 'checkout'
    (root / '.git').mkdir(parents=True)
    path = root / 'ignored/private.json'
    with pytest.raises(ValueError, match='outside Git'):
        save_private(path, {'mysql': {'host': 'private-fixture.invalid'}})
    assert not path.exists()


def test_a_profile_cannot_be_loaded_from_a_git_checkout(tmp_path):
    root = tmp_path / 'checkout'
    (root / '.git').mkdir(parents=True)
    path = root / 'config.local.json'
    path.write_text(json.dumps({'mysql': {'host': 'private-fixture.invalid', 'user': 'fixture'}}))
    with pytest.raises(ValueError, match='outside Git'):
        Config.load(path)


def test_selected_project_contains_only_a_profile_pointer(setup, monkeypatch):
    ctx = setup
    project = ctx['config'].state_dir / 'project'
    (project / '.git').mkdir(parents=True)
    (project / 'AGENTS.md').write_text('Fixture')
    (project / 'pyproject.toml').write_text('[project]\nname="fixture"\n')
    path = ctx['config'].state_dir / 'private/target.json'
    value = {'data_root': str(ctx['config'].data_root), 'state_dir': str(ctx['config'].state_dir),
             'mysql': {'host': 'private-fixture.invalid', 'password': 'private-fixture-secret'}}
    save_private(path, value)
    ctx['config'].config_path = path
    class Connection:
        def __init__(self, config):
            pass
        def require_schema(self, force=False):
            return ctx['store'].require_schema(force=force)
        def close(self):
            pass
    monkeypatch.setattr('cirdc.store.Store', Connection)
    result = select(ctx['config'], project)
    assert result['status'] == 'selected'
    pointer = project / '.cirdc/active-target'
    assert pointer.read_text().strip() == str(path)
    assert 'private-fixture.invalid' not in pointer.read_text()
    assert 'private-fixture-secret' not in pointer.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())['database_id'] == ctx['store'].inspect_schema()['identity']['instance_id']
