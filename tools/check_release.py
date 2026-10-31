"""Check public source and distributions for deployment leaks."""
import argparse
import ast
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile


ROOT_PATHS = ['.', ':(exclude)website', ':(exclude)articleInfo', ':(exclude)publicationInfo']
PHASE_MODULES = {'collector.py', 'cooperation.py', 'selection.py', 'monitor.py'}
PRIVATE_DIRECTORIES = {'.venv', '.venv-dev', '.runtime', '.workspace', '.cirdc', 'node_modules'}
GENERIC_VALUES = {'127.0.0.1', 'localhost', 'root', 'cirdc_agent', 'app', 'admin', 'reader'}


def private_address(address):
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return private_address(address.ipv4_mapped)
        return address.packed[0] & 254 == 252 or address.is_link_local
    octets = address.packed
    return (octets[0] == 10 or (octets[0] == 172 and 16 <= octets[1] <= 31)
            or octets[:2] == bytes([192, 168]) or address.is_link_local)


def private_values(profiles):
    values = set()
    for profile in profiles:
        data = json.loads(Path(profile).expanduser().read_text())
        for section, keys in [('mysql', ['host', 'user', 'password']),
                              ('ssh_tunnel', ['host', 'remote_host']),
                              ('storage', ['ssh_host', 'state_dir'])]:
            for key in keys:
                value = data.get(section, {}).get(key)
                if isinstance(value, str) and value and value not in GENERIC_VALUES:
                    values.add(value)
        for key in ('data_root', 'state_dir', 'database_id'):
            if data.get(key):
                values.add(data[key])
        for user in data.get('web', {}).get('bootstrap_users', []):
            if user.get('username') and user['username'] not in GENERIC_VALUES:
                values.add(user['username'])
    return values


def content_failures(content, protected, maintenance=True):
    reasons = []
    for value in protected:
        encoded = value.encode()
        if re.fullmatch(rb'[A-Za-z0-9_-]+', encoded):
            found = re.search(rb'(?<![A-Za-z0-9_-])' + re.escape(encoded)
                              + rb'(?![A-Za-z0-9_-])', content)
        else:
            found = encoded in content
        if found:
            reasons.append('private deployment value')
            break
    if re.search(rb'/(?:Users|home|projects)/[A-Za-z0-9_.-]+/', content):
        reasons.append('machine-specific absolute path')
    for match in re.finditer(rb'(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])', content):
        try:
            address = ipaddress.IPv4Address(match[0].decode())
        except ipaddress.AddressValueError:
            continue
        if private_address(address):
            reasons.append('private network address')
            break
    for match in re.finditer(rb'(?<![A-Za-z0-9_:])(?:[A-Fa-f0-9]{0,4}:){2,}[A-Fa-f0-9]{0,4}(?![A-Za-z0-9_:])', content):
        try:
            address = ipaddress.IPv6Address(match[0].decode())
        except ipaddress.AddressValueError:
            continue
        if private_address(address):
            reasons.append('private network address')
            break
    if re.search(rb'(?<![A-Za-z0-9_.-])(?:[A-Za-z0-9-]+\.)+(?:internal|lan|local)(?=[:/\s\x22\x27])', content):
        reasons.append('internal DNS name')
    if (re.search(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----', content)
            or re.search(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b', content)
            or re.search(rb'https?://[^\s/:]+:[^\s/@]+@', content)):
        reasons.append('credential material')
    if maintenance and (b'p' + b'df') in content.lower():
        reasons.append('out-of-scope distribution content')
    return reasons


def package_version(base):
    tree = ast.parse((base / 'src/cirdc/__init__.py').read_text())
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=['maintenance', 'website', 'all'], default='maintenance')
    parser.add_argument('--private-profile', action='append', default=[])
    parser.add_argument('--private-values-file', action='append', default=[],
                        help='Private JSON list, or object with a values list, of deployment-specific values')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protected = private_values(args.private_profile)
    for filename in args.private_values_file:
        data = json.loads(Path(filename).expanduser().read_text())
        values = data.get('values') if isinstance(data, dict) else data
        if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
            parser.error('Private redaction values must be a list of nonempty strings')
        protected.update(values)
    maintenance = args.component in ('maintenance', 'all')
    website = args.component in ('website', 'all')
    paths = (['.', ':(exclude)articleInfo', ':(exclude)publicationInfo'] if maintenance and website
             else ROOT_PATHS if maintenance else ['website'])
    listed = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *paths],
                            cwd=root, capture_output=True, check=True).stdout.decode().split('\0')
    listed = sorted(set(listed) - {''})
    failures = []

    def check(name, content, is_maintenance, archive=False):
        if archive and PRIVATE_DIRECTORIES.intersection(Path(name).parts):
            failures.append((name, 'private runtime or build directory in distribution'))
        if is_maintenance and any(name.endswith('/cirdc/' + module) for module in PHASE_MODULES):
            failures.append((name, 'historical repair module in maintenance package'))
        failures.extend((name, reason) for reason in content_failures(content, protected, is_maintenance))

    for name in listed:
        path = root / name
        if path.is_file():
            check(name, path.read_bytes(), not name.startswith('website/'))
    if maintenance:
        for name in PHASE_MODULES:
            if (root / 'src/cirdc' / name).exists():
                failures.append(('src/cirdc/' + name, 'historical repair module in maintenance package'))
        template = (root / 'database/schema.sql').read_text()
        statements = [part.strip() for part in re.sub(r'--[^\n]*', '', template).split(';') if part.strip()]
        if len(statements) != 10 or any(not statement.upper().startswith('CREATE TABLE ') for statement in statements):
            failures.append(('database/schema.sql', 'template contains data or unexpected statements'))
    components = ([root] if maintenance else []) + ([root / 'website'] if website else [])
    artifacts = []
    for base in components:
        for first, second in [('README.md', 'README_CN.md'), ('README_CN.md', 'README.md')]:
            if f']({second})' not in (base / first).read_text():
                failures.append((str((base / first).relative_to(root)), 'missing language jump link'))
        version = package_version(base)
        built = list((base / 'dist').glob(f'cirdc_pro-{version}*'))
        if len(built) != 2 or {path.suffix for path in built} != {'.whl', '.gz'}:
            failures.append((str((base / 'dist').relative_to(root)), 'build the current wheel and source distribution first'))
        artifacts.extend(built)
        for path in built:
            prefix = str(path.relative_to(root))
            if path.suffix == '.whl':
                with zipfile.ZipFile(path) as archive:
                    for name in archive.namelist():
                        check(prefix + ':' + name, archive.read(name), base == root, archive=True)
            elif path.name.endswith('.tar.gz'):
                with tarfile.open(path) as archive:
                    for member in archive.getmembers():
                        if member.isfile():
                            check(prefix + ':' + member.name, archive.extractfile(member).read(),
                                  base == root, archive=True)
    if failures:
        for path, reason in failures:
            print(path + ': ' + reason)
        raise SystemExit(1)
    print(json.dumps({'status': 'passed', 'component': args.component, 'source_files': len(listed),
                      'artifacts': [str(path.relative_to(root)) for path in artifacts],
                      **({'empty_schema_tables': len(statements)} if maintenance else {})}))


if __name__ == '__main__':
    main()
