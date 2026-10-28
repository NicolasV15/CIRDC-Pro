from datetime import datetime
import os
from . import __version__
from .config import Config
from .engine import Service
from .provider import IEEE
from .store import Store, BusyError, MIGRATION_VERSION
from .provider import UpstreamError


def result(value):
    return {'schema_version': 1, 'version': __version__, **value}


def doctor(config, network=False):
    checks = {'data_root_exists': config.data_root.is_dir(),
              'data_root_writable': os.access(config.data_root, os.W_OK),
              'publication_indexes': all((config.data_root / 'publicationInfo' / name).exists()
                                         for name in ('all_journals.json', 'all_conferences.json'))}
    database = {'configured': bool(config.mysql.get('user')), 'reachable': False, 'migrated': False}
    try:
        store = Store(config)
        database['reachable'] = True
        try:
            database['migrated'] = bool(store.execute('SELECT version FROM schema_migrations WHERE version=%s', (MIGRATION_VERSION,)))
        finally:
            store.close()
    except Exception as error:
        database['error_type'] = type(error).__name__
    checks['database'] = database['reachable'] and database['migrated']
    probe = None
    if network:
        provider = IEEE(config)
        try:
            page = provider.search_page('4', datetime.now().year)
            _, fields = provider.document('10555121')
            probe = {'status': 'ready', 'search_records': len(page.get('records', [])), 'document_fields': fields}
            checks['network'] = True
        except Exception as error:
            probe = {'status': 'blocked', 'code': getattr(error, 'code', type(error).__name__)}
            checks['network'] = False
    return result({'status': 'ready' if all(checks.values()) else 'not_ready',
                   'checks': checks, 'database': database, 'network': probe, 'config': config.public()})


def _invoke(action, config=None, **params):
    config = config or Config.load()
    if action == 'doctor':
        return doctor(config, params.get('network', False))
    store = Store(config)
    try:
        if action in ('db-init', 'update'):
            store.migrate()
        service = Service(config, store=store)
        if action == 'db-init':
            value = {'status': 'ready', 'migration_version': MIGRATION_VERSION}
        elif action == 'plan':
            value = service.plan(params)
        elif action == 'update':
            foreground = params.pop('foreground', False)
            value = service.start(params, foreground=foreground)
        elif action == 'status':
            value = service.status(params.get('run_id'))
        elif action in ('resume', 'retry'):
            value = service.resume(params['run_id'], retry=action == 'retry',
                                   foreground=params.get('foreground', False))
        elif action == 'paper':
            value = {'paper': store.paper(params['number'])}
        else:
            raise ValueError('Unknown operation')
        return result(value)
    finally:
        store.close()


def invoke(action, config=None, **params):
    try:
        return _invoke(action, config, **params)
    except Exception as error:
        message = str(error) if isinstance(error, (BusyError, UpstreamError, ValueError)) else (
            'Operation failed. Run cirdc doctor and inspect the task state.')
        return result({'status': 'error', 'error_type': type(error).__name__,
                       'code': getattr(error, 'code', 'operation_failed'), 'message': message})
