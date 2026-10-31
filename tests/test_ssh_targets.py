import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cirdc.config import Config
from cirdc.ssh import SSH, configure_target


def test_target_import_keeps_credentials_private_and_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    private = {'data_root': '/srv/library', 'state_dir': '/srv/runtime', 'database_id': 'test-instance',
               'mysql': {'host': '127.0.0.1', 'database': 'cirdc', 'user': 'app', 'password': 'fixture-private-value'}}
    monkeypatch.setattr(SSH, 'python', lambda *a, **k: json.dumps(private).encode())
    class CheckedStore:
        def __init__(self, config):
            assert config.database_id == private['database_id']
        def inspect_schema(self):
            return {'compatible': True, 'identity': {'instance_id': 'test-instance'}}
        def close(self):
            pass
    monkeypatch.setattr('cirdc.store.Store', CheckedStore)
    target = tmp_path / 'private/target.json'
    response = configure_target('fixture-server', '~/.config/cirdc/config.json', target)
    assert target.stat().st_mode & 0o777 == 0o600
    assert json.loads(target.read_text())['mysql']['password'] == 'fixture-private-value'
    assert 'fixture-private-value' not in json.dumps(response)
    assert response['target']['workers'] == 4
    with pytest.raises(ValueError, match='already exists'):
        configure_target('fixture-server', '~/.config/cirdc/config.json', target)
    assert json.loads(target.read_text())['mysql']['password'] == 'fixture-private-value'


def test_tunnel_binds_only_loopback_and_fails_if_forwarding_cannot_start(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1 if 'check' in command else 0)
    monkeypatch.setattr('cirdc.ssh.subprocess.run', run)
    SSH('fixture-server', {'local_port': 33307, 'remote_port': 3306}).ensure()
    command = commands[-1]
    assert '127.0.0.1:33307:127.0.0.1:3306' in command
    assert 'ExitOnForwardFailure=yes' in command
    assert 'ForwardAgent=no' in command


@pytest.mark.parametrize('host', ['-oProxyCommand=bad', 'server;uname', 'server name'])
def test_ssh_target_cannot_become_an_option_or_shell_command(host):
    with pytest.raises(ValueError):
        SSH(host)


def test_remote_config_separates_server_paths_from_local_runtime(tmp_path):
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps({'data_root': '/srv/library', 'state_dir': str(tmp_path / 'local-state'),
                                'storage': {'ssh_host': 'fixture-server', 'state_dir': '/srv/runtime'},
                                'workers': 4}))
    config = Config.load(path)
    assert str(config.destination('articleInfo/Journals/4/2026.json')).startswith('/srv/library/')
    assert config.state_dir == tmp_path / 'local-state'
    with pytest.raises(ValueError):
        config.destination('../outside.json')


def test_native_windows_transport_avoids_unix_control_sockets(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('cirdc.ssh.WINDOWS', True)
    channel = SSH('fixture-server')
    assert '-S' not in channel.options
    channel.ensure()  # Direct remote commands need no persistent Unix master.


def test_remote_paths_keep_posix_semantics_across_client_platforms(tmp_path):
    from pathlib import PurePosixPath
    path = tmp_path / 'target.json'
    path.write_text(json.dumps({'data_root': '/srv/library',
                                'storage': {'ssh_host': 'fixture-server', 'state_dir': '/srv/runtime'}}))
    config = Config.load(path)
    assert isinstance(config.data_root, PurePosixPath)
    assert str(config.destination('articleInfo/a.json')) == '/srv/library/articleInfo/a.json'


def test_target_import_preserves_gateway_port_and_legacy_lock_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    remote = {'data_root': '/srv/library', 'state_dir': '/srv/runtime', 'database_id': 'fixture-id',
              'mysql': {'host': '127.0.0.1', 'port': 43307, 'database': 'cirdc', 'user': 'app', 'password': 'fixture'},
              'storage': {'legacy_lock_root': '/srv/older-mount'}}
    monkeypatch.setattr(SSH, 'python', lambda *a, **k: json.dumps(remote).encode())
    class Checked:
        def __init__(self, config):
            assert config.ssh_tunnel['remote_port'] == 43307
            assert config.storage['legacy_lock_root'] == '/srv/older-mount'
        def inspect_schema(self):
            return {'compatible': True, 'identity': {'instance_id': 'fixture-id'}}
        def close(self):
            pass
    monkeypatch.setattr('cirdc.store.Store', Checked)
    result = configure_target('fixture-gateway', '~/.config/cirdc/config.json', tmp_path / 'private/profile.json')
    assert result['status'] == 'configured'
