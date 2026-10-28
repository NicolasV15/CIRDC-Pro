"""Filesystem-only SSH protocol. This module makes no source HTTP requests."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def confined(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path leaves the configured storage root')
    return path


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def operation(request):
    root = Path(request['root']).expanduser().resolve()
    state = Path(request['state']).expanduser().resolve()
    action = request['action']
    if action == 'probe':
        return {'data_root_exists': root.is_dir(), 'data_root_writable': os.access(root, os.W_OK),
                'publication_indexes': all((root / 'publicationInfo' / n).is_file()
                                           for n in ('all_journals.json', 'all_conferences.json'))}
    if action == 'initialize':
        for name in ('all_journals.json', 'all_conferences.json'):
            path = confined(root, 'publicationInfo/' + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            except FileExistsError:
                continue
            with os.fdopen(fd, 'w') as stream:
                stream.write('{}\n')
        return {'initialized': True}
    if action == 'article_paths':
        return sorted(str(p.relative_to(root)) for p in (root / 'articleInfo').rglob('*.json'))
    if action == 'years':
        kind = request['kind']
        if kind not in ('Journals', 'Conferences'):
            raise ValueError('Invalid publication kind')
        folder = root / 'publicationInfo' / kind
        return sorted(int(p.name) for p in folder.iterdir() if p.is_dir() and p.name.isdigit()) if folder.exists() else []
    if action == 'read':
        path = confined(root, request['path'])
        return base64.b64encode(path.read_bytes()).decode() if path.exists() else None
    run = request.get('run_id', '')
    if not re.fullmatch(r'[a-f0-9]{32}', run):
        raise ValueError('Invalid run identifier')
    relative = request['path']
    target = confined(root, relative)
    if action == 'stage':
        content = base64.b64decode(request['content'], validate=True)
        path = confined(state, 'staging/' + run + '/' + hashlib.sha256(relative.encode()).hexdigest() + '.json')
        atomic(path, content)
        return str(path)
    if action == 'publish':
        staged = Path(request['staged_path']).resolve()
        if not staged.is_relative_to(state / 'staging'):
            raise ValueError('Staged path leaves the configured state root')
        content = staged.read_bytes()
        if hashlib.sha256(content).hexdigest() != request['digest']:
            raise ValueError('Staged digest does not match')
        old = target.read_bytes() if target.exists() else None
        if old != content:
            backup = confined(state, 'backups/' + run + '/' + relative)
            if old is not None and not backup.exists():
                atomic(backup, old)
            atomic(target, content)
        return {'published': True, 'digest': request['digest']}
    raise ValueError('Unsupported filesystem operation')


def main():
    try:
        print(json.dumps({'ok': True, 'value': operation(json.load(sys.stdin))}))
    except Exception as error:
        print(json.dumps({'ok': False, 'error_type': type(error).__name__}))


if __name__ == '__main__':
    main()
