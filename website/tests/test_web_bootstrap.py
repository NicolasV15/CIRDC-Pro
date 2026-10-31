import json

import pytest

from cirdc.config import Config
from cirdc.web.auth import Accounts
from cirdc.web.cli import run


def test_private_bootstrap_config_preserves_existing_accounts(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'web'))
    users = [{'username': 'fixture_admin', 'role': 'admin'},
             {'username': 'fixture_reader', 'role': 'reader'}]
    profile = tmp_path / 'profile.json'
    profile.write_text(json.dumps({'data_root': str(tmp_path), 'web': {'bootstrap_users': users}}))
    config = Config.load(profile)
    assert config.web['bootstrap_users'] == users
    assert 'web' not in config.public()
    assert 'fixture_admin' not in repr(config)
    monkeypatch.setattr('cirdc.web.cli.getpass.getpass', lambda _: 'fixture-original-password')
    run(config, 'init-users')
    monkeypatch.setattr('cirdc.web.cli.getpass.getpass', lambda _: 'fixture-replacement-password')
    run(config, 'init-users')
    accounts = Accounts()
    _, admin = accounts.login('fixture_admin', 'fixture-original-password', 'admin', 'fixture-ip')
    assert admin['role'] == 'admin'
    _, reader = accounts.login('fixture_reader', 'fixture-original-password', 'reader', 'fixture-ip')
    assert reader['role'] == 'reader'
    with pytest.raises(ValueError):
        accounts.login('fixture_reader', 'fixture-original-password', 'admin', 'fixture-ip')


def test_explicit_initial_administrator(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'web'))
    monkeypatch.setattr('cirdc.web.cli.getpass.getpass', lambda _: 'fixture-initial-password')
    run(Config(tmp_path, tmp_path / 'state'), 'init-users', username='fixture_admin')
    _, user = Accounts().login('fixture_admin', 'fixture-initial-password', 'admin', 'fixture-ip')
    assert user['role'] == 'admin'


@pytest.mark.parametrize('users', [None, {}, [],
    [{'username': 'invalid name', 'role': 'admin'}],
    [{'username': 'fixture_admin', 'role': 'owner'}],
    [{'username': 'fixture_reader', 'role': 'reader'}],
    [{'username': 'fixture_admin', 'role': 'admin'}, {'username': 'fixture_admin', 'role': 'reader'}]])
def test_invalid_bootstrap_has_no_side_effects(tmp_path, monkeypatch, users):
    state = tmp_path / 'web'
    monkeypatch.setenv('CIRDC_WEB_STATE', str(state))
    monkeypatch.setattr('cirdc.web.cli.getpass.getpass', lambda _: pytest.fail('Unexpected password prompt'))
    with pytest.raises(ValueError):
        run(Config(tmp_path, tmp_path / 'state', web={'bootstrap_users': users}), 'init-users')
    assert not state.exists()


def test_password_reset_requires_explicit_account(tmp_path, monkeypatch):
    state = tmp_path / 'web'
    monkeypatch.setenv('CIRDC_WEB_STATE', str(state))
    with pytest.raises(ValueError, match='--username'):
        run(Config(tmp_path, tmp_path / 'state'), 'passwd')
    assert not state.exists()
