"""Native Skill installation against a real fixture site and isolated user directories."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_agent import agent_site, website  # noqa: F401
from test_agent_clients import serve

from cirdc.web.app import create_app

SOURCE = Path(__file__).parents[1] / '.agents/skills/cirdc-research'


def load_script(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installer():
    return load_script(SOURCE / 'scripts/install_skill.py')


def test_download_install_update_and_saved_site_work_from_another_project(agent_site, tmp_path, monkeypatch, installer):  # noqa: F811
    config, provider, resources = agent_site
    home = tmp_path / 'user'
    with serve(create_app(config, resource_providers=resources, reader_auth='required')) as origin:
        result = installer.install(origin, ['codex', 'claude-code'], home=home)
        cache = Path(result['source'])
        for link in result['links']:
            assert Path(link).is_symlink() and Path(link).samefile(cache)
        assert all((cache / name).read_bytes() == (SOURCE / name).read_bytes() for name in installer.FILES)
        assert json.loads(Path(result['config']).read_text()) == {'base_url': origin}
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
        monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
        another_project = tmp_path / 'another-project'
        another_project.mkdir()
        monkeypatch.chdir(another_project)
        client = load_script(cache / 'scripts/cirdc_client.py').Client()
        assert client.search('RF')['items']
        assert client.capabilities()['authentication'] == 'none'
        (cache / 'SKILL.md').write_text('old cached content')
        assert installer.install(origin, ['codex'], home=home)['status'] == 'installed'
        assert (cache / 'SKILL.md').read_bytes() == (SOURCE / 'SKILL.md').read_bytes()
        installer.install('', ['codex'], home=home, uninstall=True)
        assert not (home / '.agents/skills/cirdc-research').is_symlink()
        assert (home / '.claude/skills/cirdc-research').is_symlink()
        assert cache.exists() and Path(result['config']).exists()
        assert not provider.calls


def test_checkout_install_does_not_download_or_modify_source(tmp_path, monkeypatch, installer):
    source = tmp_path / 'checkout with spaces' / 'cirdc-research'
    shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('__pycache__'))
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    monkeypatch.setattr(installer, 'urlopen', lambda *a, **kw: pytest.fail('Checkout installation must be offline'))
    home = tmp_path / 'user'
    result = installer.install('https://papers.example.org', ['codex', 'claude-code'], source, home, skip_check=True)
    assert result['connection_verified'] is False
    assert (home / '.agents/skills/cirdc-research').samefile(source)
    assert (home / '.claude/skills/cirdc-research').samefile(source)
    assert {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()} == before
    installer.install('', ['codex', 'claude-code'], source, home, uninstall=True)
    assert source.exists()
    assert not (home / '.claude/skills/cirdc-research').is_symlink()


@pytest.mark.parametrize('kind', ['directory', 'symlink', 'broken-symlink'])
def test_conflicts_are_preserved_before_any_install_or_uninstall(tmp_path, installer, kind):
    home = tmp_path / 'user'
    conflict = home / '.claude/skills/cirdc-research'
    conflict.parent.mkdir(parents=True)
    if kind == 'directory':
        conflict.mkdir()
        (conflict / 'mine').write_text('keep')
    else:
        other = tmp_path / 'other'
        if kind == 'symlink':
            other.mkdir()
        conflict.symlink_to(other)
    for uninstall in (False, True):
        with pytest.raises(installer.InstallError):
            installer.install('https://papers.example.org', ['codex', 'claude-code'], SOURCE, home, uninstall)
        assert not (home / '.agents').exists()
        assert not (home / '.config').exists()
        assert conflict.is_symlink() if kind != 'directory' else (conflict / 'mine').read_text() == 'keep'


def test_failed_update_retains_previous_skill_and_site(tmp_path, monkeypatch, installer):
    home = tmp_path / 'user'
    cache = home / '.local/share/cirdc/skills/cirdc-research'
    cache.mkdir(parents=True)
    (cache / installer.MARKER).write_text(installer.NAME)
    (cache / 'SKILL.md').write_text('previous valid version')
    config = home / '.config/cirdc/research.json'
    config.parent.mkdir(parents=True)
    config.write_text('{"base_url":"https://previous.example.org"}')
    def fail(*args, **kwargs):
        raise OSError('fixture unavailable')
    monkeypatch.setattr(installer, 'urlopen', fail)
    with pytest.raises(installer.InstallError, match='Cannot verify'):
        installer.install('https://papers.example.org', ['codex'], home=home)
    assert (cache / 'SKILL.md').read_text() == 'previous valid version'
    assert json.loads(config.read_text())['base_url'] == 'https://previous.example.org'
    assert not (home / '.agents').exists()


def test_unmanaged_cache_and_invalid_origin_are_not_modified(tmp_path, installer):
    home = tmp_path / 'user'
    cache = home / '.local/share/cirdc/skills/cirdc-research'
    cache.mkdir(parents=True)
    (cache / 'mine').write_text('keep')
    for url in ['https://papers.example.org', 'https://example-user@papers.example.org',
                'https://papers.example.org/api/agent/v1', 'file:///tmp/skill']:
        with pytest.raises(installer.InstallError):
            installer.install(url, ['codex'], home=home)
        assert (cache / 'mine').read_text() == 'keep'
        assert not (home / '.config').exists()


def test_offline_source_cli_saves_an_explicit_site_from_any_directory(tmp_path, monkeypatch, capsys, installer):
    home = tmp_path / 'user'
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(installer, 'urlopen', lambda *a, **kw: pytest.fail('Source install must be offline'))
    assert installer.main(['--source', str(SOURCE), '--agent', 'all', '--base-url', 'https://papers.example.org', '--skip-check']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['base_url'] == 'https://papers.example.org'
    assert json.loads(Path(result['config']).read_text()) == {'base_url': result['base_url']}
    assert result['connection_verified'] is False
    assert all(Path(p).samefile(SOURCE) for p in result['links'])
    assert installer.main(['--source', str(SOURCE), '--agent', 'all', '--uninstall']) == 0
    assert not any(Path(p).is_symlink() for p in result['links'])


def test_first_source_install_defaults_to_local_and_saves_verified_site(agent_site, tmp_path, monkeypatch, installer):
    config, provider, resources = agent_site
    with serve(create_app(config, resource_providers=resources)) as origin:
        monkeypatch.setattr(installer, 'DEFAULT_SITE', origin)
        monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
        home = tmp_path / 'new-user'
        result = installer.install(None, ['codex'], SOURCE, home)
        assert result['base_url'] == origin and result['connection_verified']
        assert json.loads(Path(result['config']).read_text())['base_url'] == origin
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
        assert load_script(SOURCE / 'scripts/cirdc_client.py').Client().capabilities()['api_version'] == '1'
        assert not provider.calls


def test_interactive_install_asks_once_and_configure_changes_only_saved_site(agent_site, tmp_path, monkeypatch, installer):
    config, provider, resources = agent_site
    home = tmp_path / 'new-user'
    questions = []
    with serve(create_app(config, resource_providers=resources)) as origin:
        def reply(prompt):
            questions.append(prompt)
            return origin
        monkeypatch.setattr('builtins.input', reply)
        monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
        installed = installer.install(None, ['codex'], SOURCE, home, interactive=True)
        assert installed['connection_verified'] and len(questions) == 1
        installer.install(None, ['codex'], SOURCE, home, interactive=True)
        assert len(questions) == 1  # Updates retain a previously selected site.
        saved = Path(installed['config'])
        saved.write_text(json.dumps({'base_url': origin, 'keep': 'preference'}))
        configured = installer.install(None, [], home=home, configure_only=True, interactive=True)
        assert configured['status'] == 'configured' and len(questions) == 2
        assert configured['links'] == [] and json.loads(saved.read_text())['keep'] == 'preference'
        assert Path(installed['links'][0]).samefile(SOURCE)
        assert not provider.calls


def test_unreachable_or_wrong_site_cannot_finish_installation(tmp_path, monkeypatch, installer):
    home = tmp_path / 'new-user'
    def fail(origin):
        raise installer.InstallError('Cannot verify fixture site')
    monkeypatch.setattr(installer, 'check_site', fail)
    with pytest.raises(installer.InstallError, match='Cannot verify'):
        installer.install('https://papers.example.org', ['codex'], SOURCE, home)
    assert not (home / '.agents').exists() and not (home / '.config').exists()
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    monkeypatch.undo()
    wrong_site = Starlette(routes=[Route('/api/agent/v1/capabilities', lambda request: JSONResponse({'status': 'ok'}))])
    with serve(wrong_site) as origin:
        with pytest.raises(installer.InstallError, match='Cannot verify'):
            installer.install(origin, ['codex'], SOURCE, home)
    assert not (home / '.agents').exists() and not (home / '.config').exists()


def test_setup_precedence_explicit_environment_saved_then_local(tmp_path, monkeypatch, installer):
    home = tmp_path / 'user'
    checked = []
    monkeypatch.setattr(installer, 'check_site', lambda url: checked.append(url) or {'api_version': '1'})
    monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
    installer.install(None, [], home=home, configure_only=True)
    assert checked[-1] == installer.DEFAULT_SITE
    installer.install('https://saved.example.org', [], home=home, configure_only=True)
    installer.install(None, [], home=home, configure_only=True)
    assert checked[-1] == 'https://saved.example.org'
    monkeypatch.setenv('CIRDC_BASE_URL', 'https://environment.example.org')
    installer.install(None, [], home=home, configure_only=True)
    assert checked[-1] == 'https://environment.example.org'
    installer.install('https://explicit.example.org', [], home=home, configure_only=True)
    assert checked[-1] == 'https://explicit.example.org'


def test_missing_runtime_configuration_never_prompts_or_probes(tmp_path, monkeypatch):
    client = load_script(SOURCE / 'scripts/cirdc_client.py')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path / 'user'))
    monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
    monkeypatch.setattr('builtins.input', lambda *args: pytest.fail('Research use must never ask for configuration'))
    monkeypatch.setattr(client, 'urlopen', lambda *args, **kwargs: pytest.fail('Research use must not guess a site'))
    with pytest.raises(client.ClientError) as caught:
        client.Client()
    assert caught.value.value['error'] == 'site_not_configured'


def test_configure_cli_does_not_require_an_agent_or_create_links(tmp_path, monkeypatch, capsys, installer):
    home = tmp_path / 'user'
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    assert installer.main(['--configure', '--base-url', 'https://papers.example.org', '--skip-check']) == 0
    value = json.loads(capsys.readouterr().out)
    assert value['status'] == 'configured' and value['links'] == []
    assert value['connection_verified'] is False and not (home / '.agents').exists()
    assert json.loads(Path(value['config']).read_text())['base_url'] == 'https://papers.example.org'


def test_repository_entrypoint_resolves_its_source_from_another_directory(tmp_path):
    entrypoint = SOURCE.parents[3] / 'tools/install-skill'
    if not entrypoint.exists():
        pytest.skip('Root entrypoint belongs to the full repository checkout')
    result = subprocess.run(['sh', str(entrypoint), '--help'], check=False, cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--agent' in result.stdout and '--source' in result.stdout
