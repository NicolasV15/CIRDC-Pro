"""Install the CIRDC research Skill with native Codex / Claude Code symlinks.

Python 3.10+, standard library only. Run --help for download and checkout modes.
"""
import argparse
import hashlib
import re
import shlex
import shutil
import time
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, urlopen

NAME = 'cirdc-research'
PREFIX = '/api/agent/v1/skills/' + NAME + '/'
MARKER = '.cirdc-managed'
HOSTS = {'codex': '.agents/skills', 'claude-code': '.claude/skills'}
DEFAULT_SITE = 'http://127.0.0.1:18088'


class InstallError(ValueError):
    pass


def site_origin(value):
    if not isinstance(value, str) or not value:
        raise InstallError('The site origin must be a nonempty string.')
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or any(c.isspace() for c in value)):
        raise InstallError('Use --base-url with an http(s) site origin, without credentials or an API path.')
    _ = parsed.port  # Reject invalid port syntax before changing local files.
    return parsed.scheme + '://' + parsed.netloc


def read_config(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise InstallError(f'Cannot read site configuration: {path}') from error
    if not isinstance(value, dict):
        raise InstallError('Existing research configuration must be a JSON object.')
    return value


def select_origin(base_url, saved, *, interactive=False, configure_only=False, skip_check=False):
    explicit = base_url or os.environ.get('CIRDC_BASE_URL', '')
    previous = saved.get('base_url')
    selected = explicit or previous or DEFAULT_SITE
    if not explicit and interactive and (configure_only or not previous):
        entered = input(f'CIRDC site URL [{selected}] (enter a remote site URL when needed): ').strip()
        selected = entered or selected
    elif skip_check and not explicit and not previous:
        raise InstallError('Offline setup needs --base-url. Site configuration must be completed during installation.')
    return site_origin(selected)


def check_site(origin):
    url = origin + '/api/agent/v1/capabilities'
    # Local discovery must reach this computer, not a proxy's loopback listener.
    open_url = build_opener(ProxyHandler({})).open if urlsplit(origin).hostname in ('127.0.0.1', 'localhost', '::1') else urlopen
    try:
        with open_url(url, timeout=5) as response:
            if urlsplit(response.url).netloc != urlsplit(origin).netloc:
                raise InstallError('The capability check redirected to another site.')
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError('oversized response')
        value = json.loads(raw)
        if (not isinstance(value, dict) or value.get('api_version') != '1'
                or value.get('scope') != 'indexed_papers_only'
                or not isinstance(value.get('resources'), dict)):
            raise ValueError('not a CIRDC research API')
    except (OSError, ValueError) as error:
        raise InstallError('Cannot verify the CIRDC research API at ' + origin + '. '
                           'Choose the correct site during installation with --base-url, or use '
                           '--base-url with --skip-check for intentional offline setup. Existing setup was not changed.') from error
    return {'api_version': value['api_version'], 'resources': value['resources']}


def check_links(home, agents, source):
    links = [home / HOSTS[agent] / NAME for agent in agents]
    for link in links:
        if link.is_symlink():
            if link.resolve() != source.resolve():
                raise InstallError(f'Existing Skill link points elsewhere: {link}. Remove it explicitly first.')
        elif link.exists():
            raise InstallError(f'Existing Skill is not a symlink: {link}. Move it explicitly first.')
    return links


def write_config(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix='.research-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


# Skill release metadata is independent of API and Python package versions.
MANIFEST = 'version.json'
UPDATE_INTERVAL = 86400
UPDATE_TIMEOUT = 2


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
        raise InstallError('Unsupported Skill version; expected stable MAJOR.MINOR.PATCH.')
    return tuple(map(int, value.split('.')))


def validate_manifest(value, check_runtime=True):
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('name') != NAME:
        raise InstallError('Unsupported Skill manifest.')
    version_tuple(value.get('version'))
    files = value.get('files')
    if not isinstance(files, dict) or not 1 <= len(files) <= 64:
        raise InstallError('Invalid Skill file inventory.')
    for name, item in files.items():
        parts = name.split('/')
        if (any(not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', part) for part in parts)
                or name == MANIFEST or not isinstance(item, dict)
                or not re.fullmatch('[a-f0-9]{64}', str(item.get('sha256', '')))
                or type(item.get('bytes')) is not int or not 0 <= item['bytes'] <= 2_000_000):
            raise InstallError('Invalid Skill file checksum entry.')
    if not {'SKILL.md', 'scripts/install_skill.py', 'scripts/cirdc_client.py'} <= files.keys():
        raise InstallError('Incomplete Skill release.')
    notes = value.get('notes')
    if not isinstance(notes, dict) or any(not isinstance(notes.get(language), str) or not 1 <= len(notes[language]) <= 1000 for language in ('zh', 'en')):
        raise InstallError('Skill release needs short bilingual notes.')
    compatibility = value.get('compatibility', {})
    if not isinstance(compatibility, dict):
        raise InstallError('Invalid release compatibility metadata.')
    if check_runtime and (compatibility.get('api_major') != 1 or compatibility.get('installer_schema') != 1):
        raise InstallError('This Skill release needs a newer installer.')
    minimum = compatibility.get('python_min', '')
    if not re.fullmatch(r'[0-9]+\.[0-9]+', minimum) or check_runtime and tuple(map(int, minimum.split('.'))) > sys.version_info[:2]:
        raise InstallError('This Skill release requires a newer Python.')
    return value


def read_manifest(source):
    return validate_manifest(json.loads((source / MANIFEST).read_text(encoding='utf-8')))


def checksum(content):
    return {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}


def fetch(origin, name, *, timeout=5, limit=2_000_000):
    url = origin + PREFIX + name
    opener = build_opener(ProxyHandler({})).open if urlsplit(origin).hostname in ('127.0.0.1', 'localhost', '::1') else urlopen
    with opener(url, timeout=timeout) as response:
        final = urlsplit(response.url)
        initial = urlsplit(origin)
        if (final.scheme, final.netloc) != (initial.scheme, initial.netloc):
            raise InstallError('Skill download redirected to a different origin.')
        content = response.read(limit + 1)
    if len(content) > limit:
        raise InstallError('Skill response is unexpectedly large.')
    return content


def skill_updates(origin, source=None, home=None, *, action='status', hours=24, version=None, notify=False):
    """Cache discovery only. Updating requires a separate, user-approved installer."""
    home = Path.home() if home is None else Path(home)
    source = Path(__file__).resolve().parents[1] if source is None else Path(source).resolve()
    try:
        config = home / '.config/cirdc/research.json'
        settings = read_config(config)
        if action == 'disable':
            write_config(config, {**settings, 'check_updates': False})
            return {'status': 'disabled'}
        if (os.environ.get('CIRDC_SKILL_UPDATE_CHECK', '').lower() in ('0', 'false', 'off')
                or settings.get('check_updates') is False):
            return {'status': 'disabled'}
        saved = read_config(home / '.config/cirdc/skill-installations.json').get(str(source), {})
        try:
            record = json.loads((source / MARKER).read_text())
        except (OSError, ValueError):
            record = saved
        if not isinstance(record, dict):
            record = saved
        downloaded = record.get('mode') == 'download'
        # A business --base-url override never redirects the release source.
        origin = site_origin(record.get('origin') or settings.get('base_url') or origin)
        current = record.get('version') if downloaded else read_manifest(source)['version']
        version_tuple(current)
        key = hashlib.sha256((origin + '\n' + str(source)).encode()).hexdigest()
        cache = home / '.cache/cirdc/skill-updates' / (key + '.json')
        cache.parent.mkdir(parents=True, exist_ok=True)
        lock = cache.with_suffix('.lock')
        try:
            lock.mkdir()
        except FileExistsError:
            if time.time() - lock.stat().st_mtime > 60:
                lock.rmdir()
            return {'status': 'checking', 'current': current}
        try:
            state = read_config(cache)
            now = time.time()
            if action == 'snooze':
                if not 1 <= hours <= 720:
                    raise InstallError('Snooze hours must be between 1 and 720.')
                state['snooze_until'] = now + hours * 3600
            elif action == 'skip':
                selected = version or (state.get('latest') or {}).get('version')
                version_tuple(selected)
                skipped = state.get('skipped_versions', [])
                state['skipped_versions'] = list(dict.fromkeys([*skipped, selected]))
            elif action != 'status':
                raise InstallError('Unknown update preference.')
            if action == 'status' and (state.get('current') != current
                    or not 0 <= now - float(state.get('checked_at', 0)) < UPDATE_INTERVAL):
                state.update(current=current, checked_at=now)
                write_config(cache, state)  # Cache failures, offline and old services.
                try:
                    latest = validate_manifest(json.loads(fetch(origin, MANIFEST, timeout=UPDATE_TIMEOUT, limit=65536)), check_runtime=False)
                    try:
                        validate_manifest(latest)
                        compatible = True
                    except InstallError:
                        compatible = False
                    state['latest'] = {key: latest[key] for key in ('version', 'notes', 'compatibility')}
                    state['compatible'] = compatible
                    state.pop('error', None)
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    state['error'] = 'version_check_unavailable'
            write_config(cache, state)
            latest = state.get('latest')
            result = {'status': 'unavailable', 'current': current, 'site': origin, 'mode': 'download' if downloaded else 'source', 'source': str(source),
                      'cached': now != state.get('checked_at'), 'checked_at': state.get('checked_at'), 'check_error': state.get('error')}
            if not latest:
                return result
            result.update(latest=latest['version'], notes=latest['notes'], compatibility=latest['compatibility'], compatible=state['compatible'])
            if version_tuple(latest['version']) <= version_tuple(current):
                result['status'] = 'current'
            elif latest['version'] in state.get('skipped_versions', []):
                result['status'] = 'skipped'
            elif now < state.get('snooze_until', 0):
                result['status'] = 'snoozed'
            else:
                result['status'] = 'available' if state['compatible'] else 'incompatible'
            agents = [agent for agent, directory in HOSTS.items()
                      if (home / directory / NAME).is_symlink() and (home / directory / NAME).resolve() == source]
            result['installer_args'] = ([sys.executable, str(source / 'scripts/install_skill.py'), '--agent',
                'all' if len(agents) > 1 else agents[0], '--base-url', origin, '--expected-version', latest['version']]
                if downloaded and agents else None)
            result['update_method'] = ('After explicit user agreement, run the official installer with the original --agent choice '
                'and --expected-version ' + latest['version'] + '. Preserve local edits; do not force overwrite.' if downloaded else
                'Ask the source owner to synchronize this checkout/copy, then rerun its source installer. Never run git pull/reset automatically.')
            result['question'] = '是否更新？'
            result['requires_confirmation'] = True
            if notify and result['status'] in ('available', 'incompatible') and (state.get('notified_version') != latest['version']
                    or state.get('notified_at', 0) < state.get('snooze_until', 0) <= now):
                state.update(notified_version=latest['version'], notified_at=now)
                write_config(cache, state)
                print('CIRDC_SKILL_UPDATE ' + json.dumps(result, ensure_ascii=False), file=sys.stderr)
            return result
        finally:
            lock.rmdir()
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {'status': 'unavailable'}  # Never block research or change stdout JSON.


def update_check(origin, source=None, home=None):
    return skill_updates(origin, source, home, notify=True)


def protected_install(source, manifest):
    """Return previous managed hashes; refuse modified files or unknown collisions."""
    if not source.exists():
        return {}
    try:
        record = json.loads((source / MARKER).read_text())
    except ValueError:
        record = None  # The original installer wrote a plain-text marker.
    if isinstance(record, dict) and record.get('schema_version') == 1:
        previous = record.get('files')
        if not isinstance(previous, dict) or not previous:
            raise InstallError('Invalid installed file record; preserve this copy for manual review.')
    else:
        # A legacy copy has no trustworthy local baseline. Only known shipped
        # file sets are eligible; unknown or user-edited copies need manual review.
        previous = next((items for items in manifest.get('legacy_files', [])
                         if all((source / name).is_file() and not (source / name).is_symlink()
                                and checksum((source / name).read_bytes()) == item
                                for name, item in items.items())), None)
        if not previous:
            raise InstallError('Unversioned Skill differs from known releases. Preserve it and review/move it manually before installing.')
    for name in set(previous) | set(manifest['files']) | {MANIFEST}:
        path = source / name
        if any(p.is_symlink() for p in [path, *path.parents] if p != source.parent and source in [p, *p.parents]):
            raise InstallError(f'Refusing to replace a symlink inside the Skill: {name}')
        if name in previous and not path.exists():
            raise InstallError(f'Locally removed Skill file preserved: {name}')
        if path.exists():
            if name not in previous or not path.is_file() or checksum(path.read_bytes()) != previous[name]:
                raise InstallError(f'User-modified or unmanaged Skill file preserved: {name}')
    return previous


def download_skill(origin, source, activate=None, *, expected_version=None):
    source.parent.mkdir(parents=True, exist_ok=True)
    lock = source.parent / '.cirdc-research.install-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise InstallError('Another Skill installation is active; existing files retained.') from None
    try:
        return _download_skill(origin, source, activate, expected_version=expected_version)
    finally:
        lock.rmdir()


def _download_skill(origin, source, activate=None, *, expected_version=None):
    if source.is_symlink() or source.exists() and not (source / MARKER).is_file():
        raise InstallError(f'Local Skill cache is not managed by this installer: {source}')
    raw = fetch(origin, MANIFEST, limit=65536)
    manifest = validate_manifest(json.loads(raw))
    if expected_version is not None and manifest['version'] != expected_version:
        raise InstallError('Available Skill version changed; check the release and ask the user again.')
    previous_files = protected_install(source, manifest)
    def snapshot():
        return {str(p.relative_to(source)): (p.lstat().st_mode, p.lstat().st_size, p.lstat().st_mtime_ns)
                for p in source.rglob('*')} if source.exists() else {}
    before = snapshot()
    source.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=source.parent, prefix='.cirdc-download-') as temporary:
        stage = Path(temporary) / NAME
        if source.exists():
            shutil.copytree(source, stage, symlinks=True)  # Preserve unrelated user files.
        else:
            stage.mkdir()
        for name in previous_files.keys() - manifest['files'].keys() - {MANIFEST}:
            (stage / name).unlink()
        for name, expected in manifest['files'].items():
            content = fetch(origin, name)
            if checksum(content) != expected:
                raise InstallError(f'Skill checksum mismatch: {name}. Existing installation retained.')
            text = content.decode('utf-8')
            if name.endswith('.py'):
                compile(text, name, 'exec')
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (stage / MANIFEST).write_bytes(raw)
        record = {'schema_version': 1, 'version': manifest['version'], 'mode': 'download', 'origin': origin,
                  'files': {**manifest['files'], MANIFEST: checksum(raw)}}
        (stage / MARKER).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        # Recheck just before activation in case files changed during download.
        protected_install(source, manifest)
        if snapshot() != before:
            raise InstallError('Skill directory changed during download; existing files retained.')
        previous = Path(temporary) / 'previous'
        if source.exists():
            source.rename(previous)
        try:
            stage.rename(source)
            if activate:
                activate(manifest)
        except (OSError, ValueError):
            if not stage.exists() and source.exists():
                shutil.rmtree(source)
            if previous.exists():
                previous.rename(source)
            raise
    return manifest


def install(base_url, agents, source=None, home=None, uninstall=False, *,
            skip_check=False, interactive=False, configure_only=False, expected_version=None):
    home = Path.home() if home is None else Path(home)
    checkout = Path(source).expanduser().resolve() if source is not None else None
    target = checkout or home / '.local/share/cirdc/skills' / NAME
    links = [] if configure_only else check_links(home, agents, target)
    if uninstall:
        for link in links:
            if link.is_symlink():
                link.unlink()
        return {'status': 'uninstalled', 'links': [str(p) for p in links],
                'note': 'Skill files and site configuration are retained for other clients.'}
    config = home / '.config/cirdc/research.json'
    value = read_config(config)
    if checkout and not configure_only:
        if not all((checkout / name).is_file() for name in read_manifest(checkout)['files']):
            raise InstallError('--source must be the complete local cirdc-research Skill directory.')
    if not checkout and not configure_only and (target.is_symlink() or target.exists() and not (target / MARKER).is_file()):
        raise InstallError(f'Local Skill cache is not managed by this installer: {target}')
    origin = select_origin(base_url, value, interactive=interactive, configure_only=configure_only, skip_check=skip_check)
    capabilities = None if skip_check else check_site(origin)
    records = home / '.config/cirdc/skill-installations.json'
    old_config = config.read_bytes() if config.exists() else None
    old_records = records.read_bytes() if records.exists() else None
    added_links = []

    def activate(manifest):
        try:
            write_config(config, {**value, 'base_url': origin})
            for link in links:
                link.parent.mkdir(parents=True, exist_ok=True)
                if not link.is_symlink():
                    link.symlink_to(target, target_is_directory=True)
                    added_links.append(link)
            if manifest:
                installed = read_config(records)
                installed[str(target)] = {'version': manifest['version'], 'mode': 'source' if checkout else 'download', 'origin': origin,
                    'files': {name: checksum((target / name).read_bytes()) for name in manifest['files']}}
                write_config(records, installed)
        except (OSError, ValueError):
            for link in added_links:
                link.unlink()
            for path, old in [(config, old_config), (records, old_records)]:
                if old is None:
                    path.unlink(missing_ok=True)
                elif not path.exists() or path.read_bytes() != old:
                    path.write_bytes(old)
            raise

    manifest = None
    if checkout and not configure_only:
        manifest = read_manifest(checkout)
        if expected_version is not None and manifest['version'] != expected_version:
            raise InstallError('Source version differs from the approved release.')
        activate(manifest)
    elif not configure_only:
        manifest = download_skill(origin, target, activate, expected_version=expected_version)
    else:
        activate(None)
    if manifest and not skip_check:
        update_check(origin, target, home)
    modified = [name for name, expected in manifest['files'].items() if checksum((target / name).read_bytes()) != expected] if manifest else []
    return {'modified_files': modified, 'version': manifest['version'] if manifest else None, 'status': 'configured' if configure_only else 'installed', 'source': str(target) if not configure_only else None,
            'links': [str(p) for p in links], 'config': str(config), 'base_url': origin,
            'connection_verified': capabilities is not None,
            'next': 'Site configuration is saved; research use will not ask for a URL. '
                    + ('No Skill links or MCP settings were changed.' if configure_only else
                       'Open a new Codex session, or run /reload-skills in Claude Code. No MCP settings were changed.')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=[*HOSTS, 'all'], help='Required for installation or removal; optional with --configure')
    parser.add_argument('--base-url', help='Select and save a site during setup; overrides CIRDC_BASE_URL and saved configuration')
    parser.add_argument('--source', type=Path, help='Link an existing local Skill folder instead of downloading')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--uninstall', action='store_true', help='Remove only the selected, matching Skill symlinks')
    mode.add_argument('--configure', action='store_true', help='Select, verify and save a site without changing Skill links')
    parser.add_argument('--expected-version', help='Install only the release version explicitly approved by the user')
    parser.add_argument('--non-interactive', action='store_true', help='Use explicit, environment, saved or local default address without prompting')
    parser.add_argument('--skip-check', action='store_true', help='Save an explicit/existing site without checking connectivity, for offline setup')
    args = parser.parse_args(argv)
    if not args.agent and not args.configure:
        parser.error('--agent is required unless using --configure')
    agents = list(HOSTS) if args.agent == 'all' else [args.agent] if args.agent else []
    try:
        result = install(args.base_url, agents, args.source, uninstall=args.uninstall,
                         skip_check=args.skip_check, interactive=not args.non_interactive and sys.stdin.isatty(),
                         configure_only=args.configure, expected_version=args.expected_version)
    except (OSError, ValueError, SyntaxError, EOFError) as error:
        parser.exit(1, f'Installation failed: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
