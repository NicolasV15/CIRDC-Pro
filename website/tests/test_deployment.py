"""Exercise publication failure boundaries with isolated fake services."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux systemd deployment')


@pytest.fixture
def deployment(tmp_path):
    source = tmp_path / 'source'
    target = tmp_path / 'target'
    commands = tmp_path / 'commands'
    commands.mkdir()
    for name in ['src', 'web', 'docs', 'deploy', 'tools', '.agents', '.claude', '.codex']:
        (source / name).mkdir(parents=True)
    for name in ['pyproject.toml', 'uv.lock', 'LICENSE', 'README.md', 'README_CN.md',
                 'AGENTS.md', 'CLAUDE.md', '.mcp.json', 'config.example.json', 'requirements.txt']:
        (source / name).write_text('fixture')
    script = source / 'tools/deploy_web.sh'
    shutil.copyfile(Path(__file__).parents[1] / 'tools/deploy_web.sh', script)
    previous = target / 'releases/previous/dist'
    previous.mkdir(parents=True)
    (previous / 'cirdc_pro-0.3.0-py3-none-any.whl').write_text('previous')
    (target / 'current').symlink_to('releases/previous')
    (target / '.venv/bin').mkdir(parents=True)
    (target / '.runtime/state').mkdir(parents=True)
    for name in ['accounts.sqlite', 'search.sqlite']:
        (target / '.runtime/state' / name).write_text('preserved')
    runner = commands / 'runner'
    runner.write_text('#!' + sys.executable + '\n' + '''
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
log = Path(os.environ['TEST_EVENTS'])
with log.open('a') as stream:
    stream.write(json.dumps([name, *args]) + '\\n')
if name == 'uv' and args[0] == 'build':
    if os.environ.get('FAIL_BUILD'): sys.exit(1)
    out = Path(args[args.index('--out-dir') + 1])
    out.mkdir(parents=True)
    (out / 'cirdc_pro-0.3.0-py3-none-any.whl').write_text('candidate')
if name == 'systemctl' and 'stop' in args and os.environ.get('FAIL_STOP_ONCE'):
    marker = log.with_suffix('.stop')
    if not marker.exists():
        marker.touch(); sys.exit(1)
if name == 'curl' and os.environ.get('FAIL_HEALTH_ONCE'):
    marker = log.with_suffix('.health')
    if not marker.exists():
        marker.touch(); sys.exit(1)
if name == 'python' and os.environ.get('FAIL_STARTUP'): sys.exit(1)
''')
    runner.chmod(0o755)
    for name in ['npm', 'uv', 'systemctl', 'curl']:
        (commands / name).symlink_to(runner)
    (target / '.venv/bin/python').symlink_to(runner)
    env = {**os.environ, 'PATH': str(commands) + os.pathsep + os.environ['PATH'],
           'CIRDC_WEB_ROOT': str(target), 'CIRDC_WEB_STATE': str(target / '.runtime/state'),
           'TEST_EVENTS': str(tmp_path / 'events.jsonl')}
    def publish(**options):
        return subprocess.run(['bash', str(script), 'candidate'], env={**env, **options},
                              text=True, capture_output=True, timeout=10)
    def events():
        log = Path(env['TEST_EVENTS'])
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return target, publish, events


def test_publish_installs_only_the_wheel_and_preserves_configuration(deployment):
    target, publish, events = deployment
    result = publish()
    assert result.returncode == 0, result.stderr
    assert (target / 'current').readlink() == Path('releases/candidate')
    installs = [e for e in events() if e[:3] == ['uv', 'pip', 'install']]
    assert len(installs) == 1
    assert {'--offline', '--no-deps', '--reinstall'} <= set(installs[0])
    assert not any('enable' in e or 'daemon-reload' in e for e in events())
    assert (target / '.runtime/state/accounts.sqlite').read_text() == 'preserved'
    assert (target / '.runtime/state/search.sqlite').read_text() == 'preserved'


def test_build_failure_never_stops_the_running_release(deployment):
    target, publish, events = deployment
    assert publish(FAIL_BUILD='1').returncode != 0
    assert (target / 'current').readlink() == Path('releases/previous')
    assert not any(e[0] == 'systemctl' for e in events())


def test_unavailable_startup_configuration_never_stops_services(deployment):
    target, publish, events = deployment
    assert publish(FAIL_STARTUP='1').returncode != 0
    assert (target / 'current').readlink() == Path('releases/previous')
    assert not any(e[0] == 'systemctl' for e in events())


@pytest.mark.parametrize('failure', ['FAIL_HEALTH_ONCE', 'FAIL_STOP_ONCE'])
def test_activation_failure_restores_previous_release(deployment, failure):
    target, publish, events = deployment
    result = publish(**{failure: '1'})
    assert result.returncode != 0
    assert 'previous release restored' in result.stderr
    assert (target / 'current').readlink() == Path('releases/previous')
    installs = [e for e in events() if e[:3] == ['uv', 'pip', 'install']]
    assert '/releases/previous/' in installs[-1][-1]
    assert any(e[:3] == ['systemctl', '--user', 'start'] for e in events())


def test_missing_rollback_wheel_blocks_publication(deployment):
    target, publish, events = deployment
    next((target / 'releases/previous/dist').glob('*.whl')).unlink()
    assert publish().returncode != 0
    assert not events()


def test_concurrent_publication_is_rejected(deployment):
    import fcntl
    target, publish, events = deployment
    control = target / '.runtime/deployment'
    control.mkdir()
    with (control / 'release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = publish()
    assert result.returncode != 0
    assert 'Another website deployment' in result.stderr
    assert not events()
