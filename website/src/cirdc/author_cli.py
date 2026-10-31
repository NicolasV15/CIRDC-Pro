"""The single-author CLI and MCP operations share this dispatcher."""
import argparse

from .author_profiles import (
    AuthorClient,
    AuthorError,
    AuthorRepository,
    atomic_write,
    identity,
    read_snapshot,
    timestamp,
)


def add_parser(sub):
    author = sub.add_parser('author', help='Explicit single-author profiles; never part of a paper update')
    author.add_argument('--config', default=argparse.SUPPRESS)
    author.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
    actions = author.add_subparsers(dest='action', required=True)
    for name in ('init', 'fetch', 'import', 'update', 'show'):
        child = actions.add_parser(name)
        child.add_argument('--config', default=argparse.SUPPRESS)
        child.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        if name in ('fetch', 'update', 'show'):
            child.add_argument('author_id')
        if name == 'fetch':
            child.add_argument('--output', required=True)
        if name == 'import':
            child.add_argument('path')


def invoke_author(action, config=None, **params):
    from .api import result
    from .config import Config
    from .store import Store
    config = config or Config.load()
    try:
        if action not in ('init', 'fetch', 'import', 'update', 'show'):
            raise AuthorError('invalid_author_action')
        aid = params.get('author_id')
        if action in ('fetch', 'update', 'show'):
            identity(aid)
        if action == 'fetch':
            value = AuthorClient(config).fetch(aid)
            atomic_write(params['output'], value)
            return result({'status': 'fetched', 'source': 'ieee', 'author_id': aid,
                           'completed': 1, 'pending': 0, 'payload_sha256': value['payload_sha256']})
        value = read_snapshot(params['path']) if action == 'import' else None
        store = Store(config)
        try:
            repository = AuthorRepository(store, config.state_dir)
            if action == 'init':
                from .author_schema import initialize
                out = initialize(store)
            elif action == 'show':
                profile = repository.show(aid)
                out = {'status': 'ready' if profile else 'not_fetched', 'author': profile}
            else:
                repository.ready()  # Fail before network if schema is absent or incompatible.
                if action == 'update':
                    attempted = timestamp()
                    try:
                        value = AuthorClient(config).fetch(aid)
                    except AuthorError as error:
                        if error.code != 'author_fetch_busy':
                            repository.failed(aid, error, attempted)
                        raise
                out = repository.save(value)
                out.update(completed=1, pending=0)
            return result(out)
        finally:
            store.close()
    except Exception as error:  # noqa: BLE001 - redact database/transport exceptions at the public boundary
        return result({'status': 'error', 'code': getattr(error, 'code', 'author_operation_failed'),
                       'message': 'Single-author operation failed; previous successful data is retained.',
                       'http_status': getattr(error, 'http_status', None), 'completed': 0, 'pending': 1})
