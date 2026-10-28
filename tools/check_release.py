"""Check distributable code for deployment leaks and an empty schema example."""
import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile


def private_values(profiles):
    values = set()
    for profile in profiles:
        data = json.loads(Path(profile).expanduser().read_text())
        for section, keys in [('mysql', ['host', 'user', 'password']), ('ssh_tunnel', ['host', 'remote_host']),
                              ('storage', ['ssh_host', 'state_dir'])]:
            for key in keys:
                value = data.get(section, {}).get(key)
                if isinstance(value, str) and value not in ('127.0.0.1', 'localhost', 'root', 'cirdc_agent', 'app'):
                    values.add(value)
        for key in ('data_root', 'state_dir', 'database_id'):
            if data.get(key):
                values.add(data[key])
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-profile', action='append', default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protected = private_values(args.private_profile)
    paths = ['src', 'tools', 'tests', 'database', '.agents', '.claude', '.codex', '.mcp.json',
             'AGENTS.md', 'CLAUDE.md', 'README.md', 'README_CN.md', 'pyproject.toml',
             'config.example.json', 'config.ssh.example.json', '.gitignore']
    listed = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *paths],
                            cwd=root, capture_output=True, check=True).stdout.decode().split('\0')
    failures = []
    def check(name, content):
        if any(v.encode() in content for v in protected):
            failures.append((name, 'private deployment value'))
        if re.search(rb'/(?:Users|home)/[A-Za-z0-9_.-]+/(?:Project|mnt|\.config|\.local)', content):
            failures.append((name, 'personal deployment path'))
        if (b'p' + b'df') in content.lower():
            failures.append((name, 'out-of-scope distribution content'))
    for name in sorted(set(listed) - {''}):
        path = root / name
        if path.is_file():
            check(name, path.read_bytes())
    template = (root / 'database/schema.sql').read_text()
    sql = re.sub(r'--[^\n]*', '', template)
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    if len(statements) != 10 or any(not s.upper().startswith('CREATE TABLE ') for s in statements):
        failures.append(('database/schema.sql', 'template contains data or unexpected statements'))
    for first, second in [('README.md', 'README_CN.md'), ('README_CN.md', 'README.md')]:
        if f']({second})' not in (root / first).read_text():
            failures.append((first, 'missing language jump link'))
    tree = ast.parse((root / 'src/cirdc/__init__.py').read_text())
    version = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    artifacts = list((root / 'dist').glob(f'cirdc_pro-{version}*'))
    if len(artifacts) != 2:
        failures.append(('dist', 'build the current wheel and source distribution first'))
    for path in artifacts:
        if path.suffix == '.whl':
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    check(path.name + ':' + name, archive.read(name))
        else:
            with tarfile.open(path) as archive:
                for member in archive.getmembers():
                    if member.isfile():
                        check(path.name + ':' + member.name, archive.extractfile(member).read())
    if failures:
        for path, reason in failures:
            print(path + ': ' + reason)
        raise SystemExit(1)
    print(json.dumps({'status': 'passed', 'source_files': len(set(listed) - {''}),
                      'artifacts': [p.name for p in artifacts], 'empty_schema_tables': len(statements)}))


if __name__ == '__main__':
    main()
