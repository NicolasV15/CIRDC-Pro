import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'tools/check_release.py'
spec = importlib.util.spec_from_file_location('release_check', SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_deployment_values_are_detected_without_printing_them():
    secret = 'fixture-secret-value'
    assert release.content_failures(secret.encode(), {secret}) == ['private deployment value']
    address = '.'.join(['10', '23', '45', '67'])
    assert 'private network address' in release.content_failures(address.encode(), set())
    location = '/' + '/'.join(['projects', 'fixture', 'runtime'])
    assert 'machine-specific absolute path' in release.content_failures(location.encode(), set())
    assert release.content_failures(b'127.0.0.1 and /path/to/private/profile.json', set()) == []
    assert release.content_failures(b'fixture_alias_extra', {'fixture_alias'}) == []


@pytest.mark.parametrize('address', [':'.join(['fdab', '1234', '', '1']),
    ':'.join(['fe80', '', '1']), '::ffff:' + '.'.join(['10', '23', '45', '67'])])
def test_internal_ipv6_addresses_are_detected(address):
    assert 'private network address' in release.content_failures(address.encode(), set())


def test_generic_loopback_and_dns_placeholders_remain_usable():
    assert release.content_failures(b'localhost ::1 :: https://example.com/', set()) == []
    host = '.'.join(['fixture', 'internal'])
    assert 'internal DNS name' in release.content_failures(('https://' + host + '/').encode(), set())


@pytest.mark.parametrize('where', ['docs', 'website_source', 'website_wheel', 'website_sdist'])
def test_combined_release_checks_cover_docs_and_website(tmp_path, where):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'tools').mkdir()
    shutil.copyfile(SCRIPT, tmp_path / 'tools/check_release.py')
    (tmp_path / '.gitignore').write_text('dist/\n')
    (tmp_path / 'database').mkdir()
    (tmp_path / 'database/schema.sql').write_text('\n'.join(
        f'CREATE TABLE fixture_{i}(id INT);' for i in range(10)))
    for base in [tmp_path, tmp_path / 'website']:
        (base / 'src/cirdc').mkdir(parents=True)
        (base / 'src/cirdc/__init__.py').write_text("__version__ = '1.0'\n")
        for first, second in [('README.md', 'README_CN.md'), ('README_CN.md', 'README.md')]:
            (base / first).write_text(f'[Language]({second})\n')
        (base / 'dist').mkdir()
        with zipfile.ZipFile(base / 'dist/cirdc_pro-1.0-py3-none-any.whl', 'w') as archive:
            archive.writestr('cirdc/__init__.py', '# fixture\n')
        with tarfile.open(base / 'dist/cirdc_pro-1.0.tar.gz', 'w:gz') as archive:
            data = b'# fixture\n'
            member = tarfile.TarInfo('cirdc_pro-1.0/README.md')
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    secret = 'fixture-private-alias'
    values = tmp_path.parent / (tmp_path.name + '-values.json')
    values.write_text(json.dumps({'values': [secret]}))
    command = [sys.executable, str(tmp_path / 'tools/check_release.py'), '--component', 'all',
               '--private-values-file', str(values)]
    assert subprocess.run(command, capture_output=True, text=True).returncode == 0
    if where == 'docs':
        (tmp_path / 'docs').mkdir()
        (tmp_path / 'docs/deployment.md').write_text(secret)
    elif where == 'website_source':
        (tmp_path / 'website/src/cirdc/deployment.py').write_text(secret)
    elif where == 'website_wheel':
        with zipfile.ZipFile(tmp_path / 'website/dist/cirdc_pro-1.0-py3-none-any.whl', 'a') as archive:
            archive.writestr('cirdc/deployment.py', secret)
    else:
        with tarfile.open(tmp_path / 'website/dist/cirdc_pro-1.0.tar.gz', 'w:gz') as archive:
            data = secret.encode()
            member = tarfile.TarInfo('cirdc_pro-1.0/docs/deployment.md')
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'private deployment value' in result.stdout
    assert secret not in result.stdout + result.stderr
