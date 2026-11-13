"""Isolated Skill releases: no database, acquisition, PDF work or shared user state."""
import copy
import json
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError

import pytest
from test_skill_install import SOURCE, load_script

CURRENT_VERSION = json.loads((SOURCE / 'version.json').read_text())['version']
_major, _minor, _patch = map(int, CURRENT_VERSION.split('.'))
NEXT_VERSION = f'{_major}.{_minor}.{_patch + 1}'


@pytest.fixture
def release(tmp_path, monkeypatch):
    module = load_script(SOURCE / 'scripts/install_skill.py')
    manifest = module.read_manifest(SOURCE)
    requests = []
    home = tmp_path / 'home'
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '0')
    monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
    def fetch(origin, name, **kwargs):
        requests.append((name, kwargs))
        return json.dumps(manifest).encode() if name == 'version.json' else (SOURCE / name).read_bytes()
    monkeypatch.setattr(module, 'fetch', fetch)
    monkeypatch.setattr(module, 'check_site', lambda origin: {'api_version': '1'})
    return module, manifest, requests, home


def install(release):
    module, _, _, home = release
    return module.install('https://papers.example.org', ['codex'], home=home)


def contents(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('latest,notice', [('0.9.0', False), (CURRENT_VERSION, False), (NEXT_VERSION, True), ('2.0.0', True), ('10.0.0', True)])
def test_version_comparison_cache_and_once_per_release(release, monkeypatch, capsys, latest, notice):
    m, manifest, requests, home = release
    target = Path(install(release)['source'])
    requests.clear()
    manifest['version'] = latest
    clock = [100000.0]
    monkeypatch.setattr(m.time, 'time', lambda: clock[0])
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
    for _ in range(4):
        m.update_check('https://papers.example.org', target, home)
    output = capsys.readouterr()
    assert not output.out
    assert bool(output.err) == notice
    if notice:
        assert CURRENT_VERSION in output.err and latest in output.err and 'requires_confirmation' in output.err
    assert requests == [('version.json', {'timeout': 2, 'limit': 65536})]
    clock[0] += 86401
    m.update_check('https://papers.example.org', target, home)
    assert len(requests) == 2 and not capsys.readouterr().err
    manifest['version'] = '11.1.0'
    clock[0] += 86401
    m.update_check('https://papers.example.org', target, home)
    assert '11.1.0' in capsys.readouterr().err


@pytest.mark.parametrize('failure', [OSError('offline'), TimeoutError('timeout'), HTTPError('fixture', 404, 'old service', {}, None), ValueError('bad json')])
def test_failures_are_quiet_and_cached(release, monkeypatch, capsys, failure):
    m, _, requests, home = release
    target = Path(install(release)['source'])
    calls = []
    def fail(*a, **kw):
        calls.append(kw)
        raise failure
    monkeypatch.setattr(m, 'fetch', fail)
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
    m.update_check('https://papers.example.org', target, home)
    m.update_check('https://papers.example.org', target, home)
    assert len(calls) == 1
    assert not capsys.readouterr().err


@pytest.mark.parametrize('mode', ['environment', 'configuration'])
def test_opt_out_performs_no_network(release, monkeypatch, mode):
    m, _, requests, home = release
    target = Path(install(release)['source'])
    requests.clear()
    if mode == 'configuration':
        monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
        m.write_config(home / '.config/cirdc/research.json', {'base_url': 'https://papers.example.org', 'check_updates': False})
    m.update_check('https://papers.example.org', target, home)
    assert requests == []


def test_install_records_version_and_preserves_preferences_and_extra_files(release):
    m, _, _, home = release
    config = home / '.config/cirdc/research.json'
    m.write_config(config, {'base_url': 'https://papers.example.org', 'my_setting': [1, 2], 'check_updates': False})
    target = Path(install(release)['source'])
    (target / 'my-notes.txt').write_text('keep me')
    assert install(release)['version'] == CURRENT_VERSION
    assert (target / 'my-notes.txt').read_text() == 'keep me'
    assert json.loads(config.read_text())['my_setting'] == [1, 2]
    saved = json.loads((home / '.config/cirdc/skill-installations.json').read_text())[str(target)]
    assert saved['version'] == CURRENT_VERSION and saved['mode'] == 'download'
    assert saved['files']['agents/openai.yaml'] == m.checksum((target / 'agents/openai.yaml').read_bytes())


def test_known_unversioned_install_migrates_but_unknown_copy_is_preserved(release):
    m, manifest, _, home = release
    target = home / '.local/share/cirdc/skills/cirdc-research'
    target.mkdir(parents=True)
    (target / m.MARKER).write_text(m.NAME + '\n')
    (target / 'SKILL.md').write_text('known legacy release')
    manifest['legacy_files'] = [{'SKILL.md': m.checksum((target / 'SKILL.md').read_bytes())}]
    (target / 'custom.txt').write_text('keep')
    install(release)
    assert m.read_manifest(target)['version'] == CURRENT_VERSION
    assert (target / 'custom.txt').read_text() == 'keep'
    (target / m.MARKER).write_text(m.NAME + '\n')
    (target / 'SKILL.md').write_text('unknown user edit')
    before = contents(home)
    with pytest.raises(m.InstallError, match='Unversioned'):
        install(release)
    assert contents(home) == before


@pytest.mark.parametrize('edit', ['managed', 'manifest', 'file_symlink', 'parent_symlink', 'new_collision'])
def test_modified_files_and_collisions_are_preserved(release, tmp_path, edit):
    m, manifest, _, home = release
    target = Path(install(release)['source'])
    if edit == 'managed':
        (target / 'SKILL.md').write_text('my changes')
    elif edit == 'manifest':
        (target / 'version.json').write_text('{}')
    elif edit == 'file_symlink':
        (target / 'SKILL.md').unlink()
        (target / 'SKILL.md').symlink_to(SOURCE / 'SKILL.md')
    elif edit == 'parent_symlink':
        shutil.rmtree(target / 'scripts')
        (target / 'scripts').symlink_to(SOURCE / 'scripts')
    else:
        (target / 'new.txt').write_text('mine')
        manifest['files']['new.txt'] = m.checksum(b'new content')
    before = contents(home)
    with pytest.raises(m.InstallError):
        install(release)
    assert contents(home) == before


def test_checksum_failure_never_activates_or_changes_config(release, monkeypatch):
    m, _, _, home = release
    install(release)
    before = contents(home)
    fetch = m.fetch
    monkeypatch.setattr(m, 'fetch', lambda origin, name, **kw: b'corrupt' if name == 'SKILL.md' else fetch(origin, name, **kw))
    with pytest.raises(m.InstallError, match='checksum mismatch'):
        install(release)
    assert contents(home) == before


@pytest.mark.parametrize('failure', ['rename', 'settings', 'link'])
def test_activation_failure_rolls_back_files_config_and_links(release, monkeypatch, failure):
    m, _, _, home = release
    target = Path(install(release)['source'])
    before = contents(home)
    if failure == 'rename':
        rename = Path.rename
        def fail(path, dest):
            if path.name == 'cirdc-research' and '.cirdc-download-' in str(path):
                raise OSError('activation fixture failure')
            return rename(path, dest)
        monkeypatch.setattr(Path, 'rename', fail)
    elif failure == 'settings':
        write = m.write_config
        def fail(path, value):
            if path.name == 'skill-installations.json':
                raise OSError('record fixture failure')
            return write(path, value)
        monkeypatch.setattr(m, 'write_config', fail)
    else:
        symlink = Path.symlink_to
        def fail(path, *a, **kw):
            if '.claude' in str(path):
                raise OSError('link fixture failure')
            return symlink(path, *a, **kw)
        monkeypatch.setattr(Path, 'symlink_to', fail)
    with pytest.raises(OSError):
        m.install('https://different.example.org', ['codex', 'claude-code'], home=home)
    assert contents(home) == before
    assert (home / '.agents/skills/cirdc-research').samefile(target)
    assert not (home / '.claude/skills/cirdc-research').is_symlink()


def test_source_link_update_notice_never_modifies_checkout(release, monkeypatch, capsys, tmp_path):
    m, manifest, requests, home = release
    source = tmp_path / 'checkout/Skill'
    shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('__pycache__'))
    before = contents(source)
    m.install('https://papers.example.org', ['codex'], source=source, home=home, skip_check=True)
    manifest['version'] = '2.0.0'
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
    requests.clear()
    m.update_check('https://papers.example.org', source, home)
    message = capsys.readouterr().err
    assert 'source owner' in message and 'source' in message
    assert 'Never run git pull/reset automatically' in message
    assert requests[0][0] == 'version.json' and contents(source) == before
    assert (home / '.agents/skills/cirdc-research').samefile(source)


def test_helper_stdout_json_and_old_service_compatibility(tmp_path):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from test_agent_clients import serve
    m = load_script(SOURCE / 'scripts/install_skill.py')
    manifest = m.read_manifest(SOURCE)
    manifest['version'] = NEXT_VERSION
    home = tmp_path / 'home'
    home.mkdir()
    calls = []
    def version(request):
        calls.append(request.url.path)
        return JSONResponse(manifest)
    app = Starlette(routes=[Route(m.PREFIX + 'version.json', version),
        Route('/api/agent/v1/capabilities', lambda request: JSONResponse({'api_version': '1', 'scope': 'indexed_papers_only'}))])
    import os
    env = {**os.environ, 'HOME': str(home), 'CIRDC_SKILL_UPDATE_CHECK': '1'}
    def call(origin):
        return subprocess.run([__import__('sys').executable, str(SOURCE / 'scripts/cirdc_client.py'), '--base-url', origin, 'capabilities'],
            env=env, capture_output=True, text=True, timeout=8)
    with serve(app) as origin:
        result = call(origin)
        assert result.returncode == 0 and json.loads(result.stdout)['api_version'] == '1'
        assert CURRENT_VERSION in result.stderr and NEXT_VERSION in result.stderr
        assert not call(origin).stderr and len(calls) == 1
    old_app = Starlette(routes=[Route('/api/agent/v1/capabilities', lambda request: JSONResponse({'api_version': '1'}))])
    with serve(old_app) as origin:
        result = call(origin)
        assert result.returncode == 0 and json.loads(result.stdout)['api_version'] == '1' and not result.stderr


def test_manifest_rejects_unsafe_paths_and_incompatible_releases(release):
    m, manifest, _, _ = release
    for name in ['../outside', '/absolute', 'scripts/../../outside', 'version.json']:
        invalid = copy.deepcopy(manifest)
        invalid['files'][name] = m.checksum(b'bad')
        with pytest.raises(m.InstallError):
            m.validate_manifest(invalid)
    for compatibility in [{'api_major': 2}, {'python_min': '99.0'}, {'installer_schema': 2}]:
        invalid = copy.deepcopy(manifest)
        invalid['compatibility'].update(compatibility)
        with pytest.raises(m.InstallError):
            m.validate_manifest(invalid)



def test_startup_checks_never_install_and_leave_business_submission_unchanged(tmp_path):
    import os
    import sys
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from test_agent_clients import serve
    m = load_script(SOURCE / 'scripts/install_skill.py')
    manifest = m.read_manifest(SOURCE)
    manifest['version'] = NEXT_VERSION
    calls = []
    def skill(request):
        calls.append(('GET', 'version.json'))
        return JSONResponse(manifest)
    async def ensure(request):
        calls.append(('POST', request.url.path))
        return JSONResponse({'pending': True, 'request_id': 'f' * 32, 'next_action': 'wait'})
    app = Starlette(routes=[Route(m.PREFIX + 'version.json', skill),
        Route('/api/agent/v1/papers/123/ensure', ensure, methods=['POST'])])
    home = tmp_path / 'home'
    home.mkdir()
    before = contents(SOURCE)
    with serve(app) as origin:
        env = {**os.environ, 'HOME': str(home), 'CIRDC_SKILL_UPDATE_CHECK': '1'}
        result = subprocess.run([sys.executable, str(SOURCE / 'scripts/cirdc_client.py'), '--base-url', origin,
            'ensure', '123', '--wait-seconds', '0'], env=env, capture_output=True, text=True, timeout=8)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['request_id'] == 'f' * 32
        event = json.loads(result.stderr.removeprefix('CIRDC_SKILL_UPDATE '))
        assert event['current'] == CURRENT_VERSION and event['latest'] == NEXT_VERSION
        assert event['notes']['zh'] and event['requires_confirmation'] is True and event['question'] == '是否更新？'
        assert calls == [('GET', 'version.json'), ('POST', '/api/agent/v1/papers/123/ensure')]
        assert contents(SOURCE) == before


def test_snooze_skip_and_disable_use_cache_and_preserve_settings(release, monkeypatch, capsys):
    m, manifest, requests, home = release
    target = Path(install(release)['source'])
    manifest['version'] = NEXT_VERSION
    clock = [100000.0]
    monkeypatch.setattr(m.time, 'time', lambda: clock[0])
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
    first = m.update_check('https://papers.example.org', target, home)
    assert first['status'] == 'available'
    capsys.readouterr()
    count = len(requests)
    assert m.skill_updates('https://papers.example.org', target, home)['latest'] == NEXT_VERSION
    assert len(requests) == count  # A new conversation can read the cached result.
    assert m.skill_updates('https://papers.example.org', target, home, action='snooze', hours=1)['status'] == 'snoozed'
    assert m.update_check('https://papers.example.org', target, home)['status'] == 'snoozed'
    assert not capsys.readouterr().err
    clock[0] += 3601
    assert m.update_check('https://papers.example.org', target, home)['status'] == 'available'
    assert CURRENT_VERSION in capsys.readouterr().err
    assert m.skill_updates('https://papers.example.org', target, home, action='skip', version=NEXT_VERSION)['status'] == 'skipped'
    clock[0] += 86401
    assert m.update_check('https://papers.example.org', target, home)['status'] == 'skipped'
    assert not capsys.readouterr().err
    manifest['version'] = '2.0.0'
    clock[0] += 86401
    assert m.update_check('https://papers.example.org', target, home)['status'] == 'available'
    assert '2.0.0' in capsys.readouterr().err
    config = home / '.config/cirdc/research.json'
    m.write_config(config, {**m.read_config(config), 'my_setting': [1, 2]})
    assert m.skill_updates('https://papers.example.org', target, home, action='disable') == {'status': 'disabled'}
    count = len(requests)
    assert m.update_check('https://papers.example.org', target, home)['status'] == 'disabled'
    assert len(requests) == count
    assert m.read_config(config)['my_setting'] == [1, 2]
    assert m.read_manifest(target)['version'] == CURRENT_VERSION


def test_download_uses_bound_site_and_approved_version(release, monkeypatch, capsys):
    m, manifest, requests, home = release
    target = Path(install(release)['source'])
    manifest['version'] = NEXT_VERSION
    original = m.fetch
    def fetch(origin, *args, **kwargs):
        assert origin == 'https://papers.example.org'
        return original(origin, *args, **kwargs)
    monkeypatch.setattr(m, 'fetch', fetch)
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
    event = m.update_check('https://business-override.example.org', target, home)
    assert event['installer_args'][-2:] == ['--expected-version', NEXT_VERSION]
    assert '--agent' in event['installer_args'] and 'codex' in event['installer_args']
    assert CURRENT_VERSION in capsys.readouterr().err
    before = contents(target)
    # An affirmative decision is a separate installer invocation. A notice never
    # reaches this path. Pinning prevents approval from drifting to another release.
    with pytest.raises(m.InstallError, match='version changed'):
        m.install('https://papers.example.org', ['codex'], home=home, expected_version='1.0.1')
    assert contents(target) == before
    result = m.install('https://papers.example.org', ['codex'], home=home, expected_version=NEXT_VERSION)
    assert result['version'] == NEXT_VERSION and m.read_manifest(target)['version'] == NEXT_VERSION


def test_incompatible_release_is_reported_without_downloading(release, monkeypatch):
    m, manifest, requests, home = release
    target = Path(install(release)['source'])
    manifest['version'] = '2.0.0'
    manifest['compatibility']['api_major'] = 2
    requests.clear()
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
    result = m.skill_updates('https://papers.example.org', target, home)
    assert result['status'] == 'incompatible' and result['compatible'] is False
    assert [name for name, _ in requests] == ['version.json']
    assert m.read_manifest(target)['version'] == CURRENT_VERSION
    with pytest.raises(m.InstallError, match='newer installer'):
        m.install('https://papers.example.org', ['codex'], home=home, expected_version='2.0.0')


def test_cli_preferences_do_not_poll_or_block_for_input(release, monkeypatch, capsys):
    m, manifest, _, home = release
    target = Path(install(release)['source'])
    client = load_script(target / 'scripts/cirdc_client.py')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.setattr('builtins.input', lambda *a: pytest.fail('Update commands must never wait for input'))
    assert client.main(['updates', 'disable']) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == {'status': 'disabled'} and not output.err
    assert json.loads((home / '.config/cirdc/research.json').read_text())['check_updates'] is False


def test_concurrent_checks_share_lock_without_blocking(release, monkeypatch):
    m, manifest, requests, home = release
    target = Path(install(release)['source'])
    manifest['version'] = NEXT_VERSION
    monkeypatch.setenv('CIRDC_SKILL_UPDATE_CHECK', '1')
    original = m.fetch
    nested = []
    def fetch(*a, **kw):
        nested.append(m.skill_updates('https://papers.example.org', target, home))
        return original(*a, **kw)
    monkeypatch.setattr(m, 'fetch', fetch)
    result = m.skill_updates('https://papers.example.org', target, home)
    assert result['status'] == 'available' and nested == [{'status': 'checking', 'current': CURRENT_VERSION}]


def test_real_slow_version_endpoint_times_out_without_blocking_business(tmp_path):
    import asyncio
    import os
    import sys
    import time
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from test_agent_clients import serve
    calls = []
    async def slow(request):
        calls.append('version')
        await asyncio.sleep(2.5)
        return JSONResponse({})
    def business(request):
        calls.append('capabilities')
        return JSONResponse({'api_version': '1'})
    app = Starlette(routes=[Route('/api/agent/v1/skills/cirdc-research/version.json', slow),
        Route('/api/agent/v1/capabilities', business)])
    home = tmp_path / 'home'
    home.mkdir()
    with serve(app) as origin:
        start = time.monotonic()
        result = subprocess.run([sys.executable, str(SOURCE / 'scripts/cirdc_client.py'), '--base-url', origin, 'capabilities'],
            env={**os.environ, 'HOME': str(home), 'CIRDC_SKILL_UPDATE_CHECK': '1'}, capture_output=True, text=True, timeout=6)
        assert result.returncode == 0 and json.loads(result.stdout)['api_version'] == '1' and not result.stderr
        assert time.monotonic() - start < 3.5
        assert calls == ['version', 'capabilities']


def test_stale_release_inventory_blocks_distribution(tmp_path):
    import runpy
    release_tool = runpy.run_path(str(SOURCE.parents[2] / 'tools/skill_release.py'))
    copy = tmp_path / 'skill'
    shutil.copytree(SOURCE, copy, ignore=shutil.ignore_patterns('__pycache__'))
    assert release_tool['check'](copy)['version'] == CURRENT_VERSION
    (copy / 'SKILL.md').write_text('unreleased modification')
    with pytest.raises(ValueError, match='inventory differs'):
        release_tool['check'](copy)
