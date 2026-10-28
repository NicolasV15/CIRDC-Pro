from datetime import datetime
from . import __version__
from .config import Config
from .engine import Service
from .provider import IEEE
from .store import Store, BusyError, MIGRATION_VERSION
from .provider import UpstreamError
from .storage import Dataset
from .ssh import SSHError
from .schema import SchemaError


def result(value):
    return {'schema_version': 1, 'version': __version__, **value}


def doctor(config, network=False):
    try:
        checks = Dataset(config).probe()
    except SSHError:
        checks = {'data_root_exists': False, 'data_root_writable': False, 'publication_indexes': False}
    database = {'configured': bool(config.mysql.get('user')), 'reachable': False, 'migrated': False}
    try:
        store = Store(config)
        database['reachable'] = True
        try:
            database['schema'] = store.inspect_schema()
            database['migrated'] = database['schema']['compatible']
        finally:
            store.close()
    except Exception as error:
        database['error_type'] = type(error).__name__
    checks['database'] = database['reachable'] and database['migrated']
    probe = None
    if network and checks['database']:
        provider = IEEE(config)
        try:
            page = provider.search_page('4', datetime.now().year)
            _, fields = provider.document('10555121')
            probe = {'status': 'ready', 'search_records': len(page.get('records', [])), 'document_fields': fields}
            checks['network'] = True
        except Exception as error:
            probe = {'status': 'blocked', 'code': getattr(error, 'code', type(error).__name__)}
            checks['network'] = False
    elif network:
        probe = {'status': 'skipped', 'code': 'database_not_ready'}
        checks['network'] = False
    return result({'status': 'ready' if all(checks.values()) else 'not_ready',
                   'checks': checks, 'database': database, 'network': probe, 'config': config.public()})


def _invoke(action, config=None, **params):
    config = config or Config.load()
    if action == 'doctor':
        return doctor(config, params.get('network', False))
    store = Store(config)
    try:
        if action == 'db-check':
            report = store.inspect_schema()
            return result({'status': 'ready' if report['compatible'] else 'not_ready', 'database': report})
        if action == 'db-init':
            if config.config_path:
                from .profiles import private_path
                private_path(config.config_path)
            report = store.migrate(adopt=params.get('adopt', False))
            if config.config_path and config.config_path.is_file():
                from .profiles import bind
                bind(config, report['identity'])
            Dataset(config).initialize()
            return result({'status': 'ready', 'migration_version': MIGRATION_VERSION, 'database': report})
        if action == 'target-bind':
            from .profiles import bind
            report = store.require_schema(force=True)
            return result({'status': 'ready', 'config_path': bind(config, report['identity']), 'database': report})
        store.require_schema(force=True)
        service = Service(config, store=store)
        if action == 'plan':
            value = service.plan(params)
        elif action == 'update':
            foreground = params.pop('foreground', False)
            value = service.start(params, foreground=foreground)
        elif action == 'status':
            value = service.status(params.get('run_id'))
        elif action in ('resume', 'retry'):
            value = service.resume(params['run_id'], retry=action == 'retry',
                                   foreground=params.get('foreground', False), workers=params.get('workers'))
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
        message = str(error) if isinstance(error, (BusyError, UpstreamError, ValueError, SSHError, SchemaError)) else (
            'Operation failed. Run cirdc doctor and inspect the task state.')
        return result({'status': 'error', 'error_type': type(error).__name__,
                       'code': getattr(error, 'code', 'operation_failed'), 'message': message,
                       **({'database': error.report} if isinstance(error, SchemaError) else {})})
