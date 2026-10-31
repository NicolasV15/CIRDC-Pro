"""Optional author schema. Never advances the paper engine migration version."""
import re

VERSION = 1
COMMENT = 'cirdc-author-schema:1'
COLUMNS = {
    'source': 'varchar(16)', 'author_id': 'varchar(64)',
    'preferred_name': 'varchar(512)', 'first_name': 'varchar(512)', 'last_name': 'varchar(512)',
    'orcid': 'varchar(64)',
    **{name + '_json': 'longtext' for name in (
        'current_affiliations', 'bio_paragraphs', 'coauthors', 'topics', 'publication_years', 'field_states')},
    'ieee_article_count': 'bigint unsigned', 'ieee_citation_count': 'bigint unsigned',
    'first_published_year': 'smallint unsigned', 'last_published_year': 'smallint unsigned',
    'is_hidden': 'tinyint(1)', 'source_url': 'varchar(512)', 'source_endpoint': 'varchar(512)',
    'fetched_at': 'datetime(6)', 'parser_version': 'varchar(32)', 'payload_sha256': 'char(64)',
    'snapshot_path': 'varchar(512)', 'fetch_state': 'varchar(24)',
    'last_attempt_at': 'datetime(6)', 'last_http_status': 'smallint unsigned',
    'last_error_code': 'varchar(64)', 'last_error': 'varchar(512)',
    'created_at': 'datetime(6)', 'updated_at': 'datetime(6)',
}


def ddl():
    lines = []
    for name, kind in COLUMNS.items():
        suffix = ' NOT NULL' if name in ('source', 'author_id', 'fetch_state') else ' NULL'
        if name in ('created_at', 'updated_at'):
            suffix = ' NOT NULL DEFAULT CURRENT_TIMESTAMP(6)'
        binary = ' COLLATE utf8mb4_bin' if name in ('source', 'author_id') else ''
        lines.append('`' + name + '` ' + kind + binary + suffix)
    lines += ['PRIMARY KEY(source,author_id)', 'INDEX author_name(preferred_name)',
              'INDEX author_orcid(orcid)', 'INDEX author_state(fetch_state,updated_at)']
    return ('CREATE TABLE authors (\n  ' + ',\n  '.join(lines) +
            "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='" + COMMENT + "'")


class AuthorSchemaError(RuntimeError):
    code = 'author_schema_mismatch'


def core_ready(store):
    from .store import MIGRATION_VERSION
    if not store.execute('SELECT version FROM schema_migrations WHERE version=%s', (MIGRATION_VERSION,)):
        raise AuthorSchemaError('Initialize the paper database before the optional author schema')
    if hasattr(store, 'require_schema'):
        store.require_schema()


def _type(value):
    # MySQL 8 omits integer display widths; MariaDB 10.5 retains them.
    return re.sub(r'\b(bigint|smallint)\(\d+\)', r'\1', value.lower())


def check(store):
    tables = store.execute('SELECT ENGINE,TABLE_COLLATION,TABLE_COMMENT FROM information_schema.tables '
                           'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', ('authors',))
    if not tables:
        return False
    info = tables[0]
    columns = store.execute('SHOW FULL COLUMNS FROM authors')
    actual = {row['Field']: _type(row['Type']) for row in columns}
    indexes = store.execute('SHOW INDEX FROM authors')
    keys = {}
    for row in sorted(indexes, key=lambda r: (r['Key_name'], r['Seq_in_index'])):
        keys.setdefault(row['Key_name'], []).append(row['Column_name'])
    expected_keys = {'PRIMARY': ['source', 'author_id'], 'author_name': ['preferred_name'],
                     'author_orcid': ['orcid'], 'author_state': ['fetch_state', 'updated_at']}
    identity = [r for r in columns if r['Field'] in ('source', 'author_id')]
    required = {'source', 'author_id', 'fetch_state', 'created_at', 'updated_at'}
    if (info['ENGINE'] != 'InnoDB' or not info['TABLE_COLLATION'].startswith('utf8mb4_')
            or info['TABLE_COMMENT'] != COMMENT or actual != COLUMNS or keys != expected_keys
            or any(r['Null'] != 'NO' or r['Collation'] != 'utf8mb4_bin' for r in identity)
            or any((r['Null'] == 'NO') != (r['Field'] in required) for r in columns)):
        raise AuthorSchemaError('Existing authors table differs from the author schema v1 contract')
    return True


def initialize(store):
    core_ready(store)
    # A schema lock prevents two agents creating the optional table simultaneously.
    from .author_profiles import author_lock
    with author_lock(store, 'schema'):
        if not check(store):
            store.execute(ddl())
            store.db.commit()
        check(store)
    return {'status': 'ready', 'author_schema_version': VERSION}
