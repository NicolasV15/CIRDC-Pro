"""Install the CIRDC research Skill with native Codex / Claude Code symlinks.

Python 3.10+, standard library only. Run --help for download and checkout modes.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, urlopen

NAME = 'cirdc-research'
PREFIX = '/api/agent/v1/skills/' + NAME + '/'
FILES = ('SKILL.md', 'references/api.md', 'scripts/cirdc_client.py', 'scripts/install_skill.py')
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


def download_skill(origin, source):
    if source.is_symlink() or source.exists() and not (source / MARKER).is_file():
        raise InstallError(f'Local Skill cache is not managed by this installer: {source}')
    source.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=source.parent, prefix='.cirdc-download-') as temporary:
        stage = Path(temporary) / NAME
        for name in FILES:
            with urlopen(origin + PREFIX + name, timeout=30) as response:
                if urlsplit(response.url).netloc != urlsplit(origin).netloc:
                    raise InstallError('Skill download redirected to a different site.')
                content = response.read(2_000_001)
            if len(content) > 2_000_000:
                raise InstallError('Skill file is unexpectedly large.')
            text = content.decode('utf-8')
            if name == 'SKILL.md' and not text.startswith('---\nname: cirdc-research\n'):
                raise InstallError('The site did not return the CIRDC research Skill.')
            if name.endswith('.py'):
                compile(text, name, 'exec')
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (stage / MARKER).write_text(NAME + '\n', encoding='utf-8')
        previous = Path(temporary) / 'previous'
        if source.exists():
            source.rename(previous)
        try:
            stage.rename(source)
        except OSError:
            if previous.exists():
                previous.rename(source)
            raise


def install(base_url, agents, source=None, home=None, uninstall=False, *,
            skip_check=False, interactive=False, configure_only=False):
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
        if not all((checkout / name).is_file() for name in FILES):
            raise InstallError('--source must be the complete local cirdc-research Skill directory.')
    if not checkout and not configure_only and (target.is_symlink() or target.exists() and not (target / MARKER).is_file()):
        raise InstallError(f'Local Skill cache is not managed by this installer: {target}')
    origin = select_origin(base_url, value, interactive=interactive, configure_only=configure_only, skip_check=skip_check)
    capabilities = None if skip_check else check_site(origin)
    if not checkout and not configure_only:
        download_skill(origin, target)
    write_config(config, {**value, 'base_url': origin})
    for link in links:
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.is_symlink():
            link.symlink_to(target, target_is_directory=True)
    return {'status': 'configured' if configure_only else 'installed', 'source': str(target) if not configure_only else None,
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
    parser.add_argument('--non-interactive', action='store_true', help='Use explicit, environment, saved or local default address without prompting')
    parser.add_argument('--skip-check', action='store_true', help='Save an explicit/existing site without checking connectivity, for offline setup')
    args = parser.parse_args(argv)
    if not args.agent and not args.configure:
        parser.error('--agent is required unless using --configure')
    agents = list(HOSTS) if args.agent == 'all' else [args.agent] if args.agent else []
    try:
        result = install(args.base_url, agents, args.source, uninstall=args.uninstall,
                         skip_check=args.skip_check, interactive=not args.non_interactive and sys.stdin.isatty(),
                         configure_only=args.configure)
    except (OSError, ValueError, SyntaxError, EOFError) as error:
        parser.exit(1, f'Installation failed: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
