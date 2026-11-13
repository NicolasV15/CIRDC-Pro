"""Refresh/check the single Skill release manifest (no network or package imports)."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / '.agents/skills/cirdc-research'


def check(source=SOURCE, write=False):
    manifest = source / 'version.json'
    value = json.loads(manifest.read_text())
    files = {}
    for path in sorted(source.rglob('*')):
        if not path.is_file() or path == manifest or '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        content = path.read_bytes()
        files[path.relative_to(source).as_posix()] = {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
    if write:
        value['files'] = files
        manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    elif files != value['files']:
        raise ValueError('Skill release inventory differs: bump version for a published change, then run website/tools/skill_release.py --write')
    # Validate using the very same standard-library installer shipped to users.
    namespace = {'__name__': 'skill_release_validation', '__file__': str(source / 'scripts/install_skill.py')}
    exec(compile((source / 'scripts/install_skill.py').read_text(), namespace['__file__'], 'exec'), namespace)
    namespace['validate_manifest'](value, check_runtime=False)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Regenerate checksums after selecting release metadata/version in version.json')
    args = parser.parse_args()
    release = check(write=args.write)
    print(json.dumps({'version': release['version'], 'files': len(release['files']), 'status': 'passed'}))
