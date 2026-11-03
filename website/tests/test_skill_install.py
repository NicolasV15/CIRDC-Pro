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
    installer.install('https://papers.example.org', ['codex', 'claude-code'], source, home)
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
    with pytest.raises(OSError):
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


def test_source_cli_installs_without_a_site_or_backend_from_any_directory(tmp_path, monkeypatch, capsys, installer):
    home = tmp_path / 'user'
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.delenv('CIRDC_BASE_URL', raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(installer, 'urlopen', lambda *a, **kw: pytest.fail('Source install must be offline'))
    assert installer.main(['--source', str(SOURCE), '--agent', 'all']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['base_url'] is None and result['config'] is None
    assert not (home / '.config').exists()
    assert all(Path(p).samefile(SOURCE) for p in result['links'])
    assert installer.main(['--source', str(SOURCE), '--agent', 'all', '--uninstall']) == 0
    assert not any(Path(p).is_symlink() for p in result['links'])


def test_repository_entrypoint_resolves_its_source_from_another_directory(tmp_path):
    entrypoint = SOURCE.parents[3] / 'tools/install-skill'
    if not entrypoint.exists():
        pytest.skip('Root entrypoint belongs to the full repository checkout')
    result = subprocess.run(['sh', str(entrypoint), '--help'], check=False, cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--agent' in result.stdout and '--source' in result.stdout
