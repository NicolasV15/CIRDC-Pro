import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import socket
import time

from .process_lock import file_lock

WINDOWS = os.name == 'nt'


class SSHError(RuntimeError):
    code = 'ssh_transport_error'


class SSH:
    def __init__(self, host, tunnel=None):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*', host):
            raise ValueError('Use a configured SSH host alias or hostname')
        self.host = host
        self.tunnel = tunnel or {}
        identifier = hashlib.sha256(json.dumps([host, self.tunnel], sort_keys=True).encode()).hexdigest()[:20]
        folder = Path.home() / '.cache/cirdc/ssh'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.control = folder / identifier
        self.options = ['ssh', *([] if WINDOWS else ['-S', str(self.control)]), '-o', 'BatchMode=yes',
                        '-o', 'ConnectTimeout=12', '-o', 'ServerAliveInterval=15',
                        '-o', 'ServerAliveCountMax=3', '-o', 'ForwardAgent=no']

    def ensure(self):
        with file_lock(self.control.with_suffix('.lock')):
            if WINDOWS:
                return self._windows_forward()
            check = subprocess.run([*self.options, '-O', 'check', self.host], capture_output=True, timeout=15)
            if check.returncode == 0:
                return
            command = [*self.options, '-M', '-o', 'ControlMaster=auto', '-o', 'ControlPersist=600',
                       '-o', 'ExitOnForwardFailure=yes', '-N', '-f']
            if self.tunnel:
                local = int(self.tunnel['local_port'])
                remote = int(self.tunnel.get('remote_port', 3306))
                if not 1024 <= local <= 65535 or not 1 <= remote <= 65535:
                    raise ValueError('Invalid SSH forwarding port')
                address = self.tunnel.get('remote_host', '127.0.0.1')
                if not re.fullmatch(r'[A-Za-z0-9_.-]+', address):
                    raise ValueError('Invalid database forwarding address')
                command += ['-L', f'127.0.0.1:{local}:{address}:{remote}']
            completed = subprocess.run([*command, self.host], capture_output=True, timeout=25)
            if completed.returncode:
                raise SSHError('SSH connection or loopback forwarding could not be established')

    def _windows_forward(self):
        # Native OpenSSH on Windows has no Unix control socket or forked master.
        if not self.tunnel:
            return
        local = int(self.tunnel['local_port'])
        remote = int(self.tunnel.get('remote_port', 3306))
        address = self.tunnel.get('remote_host', '127.0.0.1')
        if not 1024 <= local <= 65535 or not 1 <= remote <= 65535 or not re.fullmatch(r'[A-Za-z0-9_.-]+', address):
            raise ValueError('Invalid SSH forwarding endpoint')
        marker = self.control.with_suffix('.forward.json')
        def listening():
            try:
                with socket.create_connection(('127.0.0.1', local), timeout=0.2):
                    return True
            except OSError:
                return False
        if listening():
            if marker.exists() and json.loads(marker.read_text()).get('target') == str(self.control):
                return
            raise SSHError('The local forwarding port is already in use; select another private target port')
        command = [*self.options, '-N', '-T', '-o', 'ExitOnForwardFailure=yes',
                   '-L', f'127.0.0.1:{local}:{address}:{remote}', self.host]
        flags = getattr(subprocess, 'DETACHED_PROCESS', 8) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 512)
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        deadline = time.monotonic() + 20
        while process.poll() is None and time.monotonic() < deadline:
            if listening():
                from .profiles import save_private
                save_private(marker, {'target': str(self.control), 'pid': process.pid}, overwrite=True)
                return
            time.sleep(0.1)
        if process.poll() is None:
            process.terminate()
        raise SSHError('SSH loopback forwarding could not be established')

    def python(self, source, payload=None, executable='python3.12'):
        self.ensure()
        command = shlex.join([executable, '-c', source])
        try:
            value = subprocess.run([*self.options, '-T', self.host, command],
                                   input=json.dumps(payload or {}).encode(), capture_output=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            raise SSHError('Remote storage connection failed') from None
        if value.returncode:
            raise SSHError('Remote storage operation failed; source data was retained')
        return value.stdout


def configure_target(host, remote_config, output, workers=4, local_port=33307):
    if not 1 <= workers <= 8:
        raise ValueError('workers must be between 1 and 8')
    channel = SSH(host)
    source = ('import json,sys; from pathlib import Path; '
              'p=json.load(sys.stdin); print(Path(p["path"]).expanduser().read_text())')
    values = json.loads(channel.python(source, {'path': remote_config}))
    remote_db = values['mysql']
    # The socket on the SSH server connects to its private database listener.
    tunnel = {'host': host, 'local_port': local_port,
              'remote_host': remote_db.get('host', '127.0.0.1'), 'remote_port': remote_db.get('port', 3306)}
    database = {k: remote_db[k] for k in ('database', 'user', 'password') if k in remote_db}
    database.update(host='127.0.0.1', port=local_port)
    destination = Path(output).expanduser().resolve()
    if destination.exists():
        raise ValueError('Target configuration already exists; select a new output path')
    profile = {'data_root': values['data_root'],
               'state_dir': str(Path.home() / '.local/state/cirdc-targets' / destination.stem),
               'database_id': values.get('database_id'),
               'mysql': database, 'ssh_tunnel': tunnel,
               'storage': {'ssh_host': host, 'state_dir': values['state_dir'], 'python': 'python3.12'},
               'workers': workers, 'interval': max(1, values.get('interval', 1)),
               'connect_timeout': 5, 'read_timeout': 30, 'retries': 3}
    if values.get('storage', {}).get('legacy_lock_root'):
        profile['storage']['legacy_lock_root'] = values['storage']['legacy_lock_root']
    from .profiles import save_private, bind
    save_private(destination, profile)
    from .config import Config
    from .store import Store
    config = Config.load(destination)
    store = Store(config)
    try:
        report = store.inspect_schema()
    finally:
        store.close()
    if report['compatible']:
        bind(config, report['identity'])
    return {'status': 'configured' if report['compatible'] else 'not_ready', 'config_path': str(destination),
            'target': Config.load(destination).public(), 'database': report}
