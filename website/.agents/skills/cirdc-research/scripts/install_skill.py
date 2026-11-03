"""Install the CIRDC research Skill with native Codex / Claude Code symlinks.

Python 3.10+, standard library only. Run --help for download and checkout modes.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

NAME = 'cirdc-research'
PREFIX = '/api/agent/v1/skills/' + NAME + '/'
FILES = ('SKILL.md', 'references/api.md', 'scripts/cirdc_client.py', 'scripts/install_skill.py')
MARKER = '.cirdc-managed'
HOSTS = {'codex': '.agents/skills', 'claude-code': '.claude/skills'}


class InstallError(ValueError):
    pass


def site_origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or any(c.isspace() for c in value)):
        raise InstallError('Use --base-url with an http(s) site origin, without credentials or an API path.')
    _ = parsed.port  # Reject invalid port syntax before changing local files.
    return parsed.scheme + '://' + parsed.netloc


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


def install(base_url, agents, source=None, home=None, uninstall=False):
    home = Path.home() if home is None else Path(home)
    checkout = Path(source).expanduser().resolve() if source is not None else None
    target = checkout or home / '.local/share/cirdc/skills' / NAME
    links = check_links(home, agents, target)
    if uninstall:
        for link in links:
            if link.is_symlink():
                link.unlink()
        return {'status': 'uninstalled', 'links': [str(p) for p in links],
                'note': 'Skill files and site configuration are retained for other clients.'}
    origin = site_origin(base_url) if base_url else None
    if not checkout and not origin:
        raise InstallError('Use --source for an offline checkout install, or --base-url to download from a site.')
    config = home / '.config/cirdc/research.json'
    value = {}
    if origin and config.exists():
        value = json.loads(config.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise InstallError('Existing research configuration must be a JSON object.')
    if checkout:
        if not all((checkout / name).is_file() for name in FILES):
            raise InstallError('--source must be the complete local cirdc-research Skill directory.')
    else:
        download_skill(origin, target)
    if origin:
        write_config(config, {**value, 'base_url': origin})
    for link in links:
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.is_symlink():
            link.symlink_to(target, target_is_directory=True)
    return {'status': 'installed', 'source': str(target), 'links': [str(p) for p in links],
            'config': str(config) if config.exists() else None, 'base_url': origin,
            'next': 'Open a new Codex session, or run /reload-skills in Claude Code. No MCP settings were changed.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', required=True, choices=[*HOSTS, 'all'])
    parser.add_argument('--base-url', default=os.environ.get('CIRDC_BASE_URL', ''), help='CIRDC site origin; optional for --source installation')
    parser.add_argument('--source', type=Path, help='Link an existing local Skill folder instead of downloading')
    parser.add_argument('--uninstall', action='store_true', help='Remove only the selected, matching Skill symlinks')
    args = parser.parse_args(argv)
    agents = list(HOSTS) if args.agent == 'all' else [args.agent]
    try:
        result = install(args.base_url, agents, args.source, uninstall=args.uninstall)
    except (OSError, ValueError, SyntaxError) as error:
        parser.exit(1, f'Installation failed: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
