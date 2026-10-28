"""Read-only database recognition and the explicit initialization boundary."""
import json
from pathlib import Path
import re
import uuid

from .schema_ddl import SCHEMA

CONTRACT = json.loads(Path(__file__).with_name('schema_contract.json').read_text())
MIGRATION_VERSION = CONTRACT['schema_version']
CORE_TABLES = tuple(n for n in CONTRACT['tables'] if n != 'cirdc_identity')
BUSINESS_TABLES = tuple(n for n in CORE_TABLES if n != 'schema_migrations')


class SchemaError(RuntimeError):
    code = 'schema_mismatch'

    def __init__(self, report):
        self.report = report
        super().__init__('Target database is not writable: ' + report['state'] + '. Run db-check; initialize or adopt only an identified compatible database.')


def column_type(value):
    return re.sub(r'\b(tinyint|smallint|mediumint|int|bigint)\(\d+\)', r'\1', value.lower())


def inspect(store):
    rows = store.execute('SHOW FULL TABLES')
    names = {next(v for k, v in r.items() if k != 'Table_type') for r in rows if r['Table_type'] == 'BASE TABLE'}
    views = [next(v for k, v in r.items() if k != 'Table_type') for r in rows if r['Table_type'] != 'BASE TABLE']
    issues = []
    structures = {}
    for name, expected in CONTRACT['tables'].items():
        if name not in names:
            continue
        columns = {r['Field']: r for r in store.execute('SHOW COLUMNS FROM `' + name + '`')}
        structures[name] = columns
        for key, definition in expected['columns'].items():
            actual = columns.get(key)
            if actual is None:
                issues.append({'table': name, 'column': key, 'rule': 'missing_column'})
                continue
            if (column_type(actual['Type']) != definition['type']
                    or (actual['Null'] == 'YES') not in definition.get('nullable_variants', [definition['nullable']])
                    or ('auto_increment' in actual['Extra']) != definition['auto_increment']):
                issues.append({'table': name, 'column': key, 'rule': 'column_definition'})
            if 'default' in definition:
                value = str(actual['Default']).strip("'").lower().replace('()', '')
                if value != definition['default']:
                    issues.append({'table': name, 'column': key, 'rule': 'column_default'})
        for key, actual in columns.items():
            if (key not in expected['columns'] and actual['Null'] == 'NO' and actual['Default'] is None
                    and not any(x in actual['Extra'].lower() for x in ('generated', 'auto_increment'))):
                issues.append({'table': name, 'column': key, 'rule': 'extra_required_column'})
        indexes = {}
        for row in sorted(store.execute('SHOW INDEX FROM `' + name + '`'), key=lambda r: (r['Key_name'], r['Seq_in_index'])):
            item = indexes.setdefault(row['Key_name'], {'unique': not bool(row['Non_unique']), 'columns': [], 'prefixes': []})
            item['columns'].append(row['Column_name'])
            item['prefixes'].append(row['Sub_part'])
        for key, definition in expected['indexes'].items():
            if indexes.get(key) != definition:
                issues.append({'table': name, 'index': key, 'rule': 'index_definition'})
        expected_unique = [v for v in expected['indexes'].values() if v['unique']]
        for key, actual in indexes.items():
            if actual['unique'] and actual not in expected_unique:
                issues.append({'table': name, 'index': key, 'rule': 'unexpected_unique_constraint'})
        ddl = store.execute('SHOW CREATE TABLE `' + name + '`')[0]['Create Table'].lower()
        if 'engine=innodb' not in ddl or 'charset=utf8mb4' not in ddl:
            issues.append({'table': name, 'rule': 'transactional_utf8mb4_storage'})

    missing_core = sorted(set(CORE_TABLES) - names)
    versions = []
    identity = None
    if 'schema_migrations' in structures and not any(i['table'] == 'schema_migrations' for i in issues):
        versions = [r['version'] for r in store.execute('SELECT version FROM schema_migrations ORDER BY version')]
    if 'cirdc_identity' in structures and not any(i['table'] == 'cirdc_identity' for i in issues):
        markers = store.execute('SELECT singleton,application,schema_version,instance_id FROM cirdc_identity')
        if len(markers) == 1:
            identity = markers[0]
        elif markers:
            issues.append({'table': 'cirdc_identity', 'rule': 'single_identity'})
    if any(v not in (1, 2, 3, MIGRATION_VERSION) for v in versions):
        issues.append({'table': 'schema_migrations', 'rule': 'unsupported_version'})
    if identity:
        try:
            uuid.UUID(identity['instance_id'])
            valid_id = True
        except (ValueError, TypeError):
            valid_id = False
        if (identity['singleton'] != 1 or identity['application'] != CONTRACT['application']
                or identity['schema_version'] != MIGRATION_VERSION or not valid_id):
            issues.append({'table': 'cirdc_identity', 'rule': 'application_identity'})
        if store.config.database_id and store.config.database_id != identity['instance_id']:
            issues.append({'table': 'cirdc_identity', 'rule': 'target_identity_changed'})

    if not names and not views:
        state = 'empty'
    elif issues or missing_core:
        state = 'incompatible'
    elif identity and MIGRATION_VERSION in versions and {1, 2}.issubset(versions):
        state = 'ready'
    elif identity:
        state = 'incompatible'
        issues.append({'table': 'schema_migrations', 'rule': 'identity_migration_missing'})
    elif versions and set(versions).issubset({1, 2, 3}) and 2 in versions:
        state = 'legacy_requires_adoption'
    elif (not versions and not views and names == set(CONTRACT['tables'])
          and not any(store.execute('SELECT 1 AS present FROM `' + name + '` LIMIT 1') for name in BUSINESS_TABLES)):
        state = 'empty_template'
    else:
        state = 'incompatible'
        issues.append({'table': 'cirdc_identity', 'rule': 'unrecognized_existing_data'})
    if store.config.database_id and not identity:
        state = 'incompatible'
        issues.append({'table': 'cirdc_identity', 'rule': 'pinned_identity_missing'})
    web_index = False
    optional = {'web_settings': {'name': 'varchar(64)', 'value': 'varchar(255)'},
                'web_index_queue': {'number': 'varchar(64)', 'token': 'char(32)', 'changed_at': 'datetime(6)'}}
    if any(name in names for name in optional):
        web_index = all(name in names for name in optional)
        for name, required in optional.items():
            if name not in names:
                issues.append({'table': name, 'rule': 'incomplete_optional_web_index'})
                continue
            columns = {r['Field']: r for r in store.execute('SHOW COLUMNS FROM `' + name + '`')}
            if any(k not in columns or column_type(columns[k]['Type']) != v or columns[k]['Null'] != 'NO'
                   for k, v in required.items()):
                issues.append({'table': name, 'rule': 'optional_web_index_schema'})
            primary = [r for r in store.execute('SHOW INDEX FROM `' + name + '`') if r['Key_name'] == 'PRIMARY']
            expected_key = 'name' if name == 'web_settings' else 'number'
            if len(primary) != 1 or primary[0]['Column_name'] != expected_key or primary[0]['Sub_part'] is not None:
                issues.append({'table': name, 'rule': 'optional_web_index_primary_key'})
            ddl = store.execute('SHOW CREATE TABLE `' + name + '`')[0]['Create Table'].lower()
            if 'engine=innodb' not in ddl or 'charset=utf8mb4' not in ddl:
                issues.append({'table': name, 'rule': 'optional_web_index_storage'})
        if issues:
            state = 'incompatible'
    return {'state': state, 'compatible': state == 'ready', 'schema_version': MIGRATION_VERSION,
            'identity': identity, 'migration_versions': versions, 'issues': issues,
            'missing_tables': missing_core, 'extra_tables': sorted(names - set(CONTRACT['tables'])),
            'features': {'web_index': web_index}}


def initialize(store, adopt=False):
    with store.lock('schema'), store.lock('worker'):
        report = inspect(store)
        if report['compatible']:
            return report
        allowed = report['state'] in ('empty', 'empty_template') or (adopt and report['state'] == 'legacy_requires_adoption')
        if not allowed:
            raise SchemaError(report)
        store._initializing = True
        try:
            for statement in SCHEMA:
                store.execute(statement)
            for version in (1, 2, MIGRATION_VERSION):
                store.execute('INSERT IGNORE INTO schema_migrations(version) VALUES (%s)', (version,))
            store.execute('INSERT INTO cirdc_identity(singleton,application,schema_version,instance_id) VALUES (%s,%s,%s,%s)',
                          (1, CONTRACT['application'], MIGRATION_VERSION, str(uuid.uuid4())))
            store.db.commit()
        finally:
            store._initializing = False
            store._schema_report = None
    return store.require_schema(force=True)
