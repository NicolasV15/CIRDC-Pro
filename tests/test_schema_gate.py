import json

import pytest

from cirdc.api import doctor, invoke
from cirdc.schema import SchemaError
from test_engine import setup as setup


def raw(store, sql, params=()):
    with store.db.cursor() as cursor:
        cursor.execute(sql, params)
    store.db.commit()
    store._schema_report = None


@pytest.mark.parametrize('sql', [
    'ALTER TABLE papers MODIFY number VARCHAR(63) NOT NULL',
    'ALTER TABLE tasks DROP INDEX unique_task',
    'ALTER TABLE papers ADD UNIQUE KEY wrong_identity(abstract_state)',
    'ALTER TABLE papers ADD required_extra VARCHAR(24) NOT NULL',
    'ALTER TABLE papers MODIFY abstract_state VARCHAR(24) NULL',
])
def test_bad_headers_or_constraints_block_writes_before_a_task_is_created(setup, sql):
    ctx = setup
    raw(ctx['store'], sql)
    with pytest.raises(SchemaError):
        ctx['service'].start({'stage': 'enrich'}, foreground=True)
    assert ctx['store'].execute('SELECT COUNT(*) AS n FROM runs')[0]['n'] == 0
    assert ctx['store'].execute('SELECT COUNT(*) AS n FROM papers')[0]['n'] == 0
    with pytest.raises(SchemaError):
        ctx['store'].execute("INSERT INTO runs(id,status,params,stats) VALUES (%s,%s,%s,%s)", ('a' * 32, 'queued', '{}', '{}'))


def test_legacy_implicit_nonnull_timestamp_remains_compatible(setup):
    ctx = setup
    raw(ctx['store'], 'ALTER TABLE schema_migrations MODIFY applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP')
    assert ctx['store'].inspect_schema()['compatible']
    run = ctx['store'].create_run({'stage': 'metadata'})
    assert ctx['store'].run(run)['status'] == 'queued'


def test_a_different_database_identity_is_rejected(setup):
    ctx = setup
    ctx['config'].database_id = '00000000-0000-0000-0000-000000000000'
    report = ctx['store'].inspect_schema()
    assert report['state'] == 'incompatible'
    assert any(i['rule'] == 'target_identity_changed' for i in report['issues'])
    with pytest.raises(SchemaError):
        ctx['service'].start({}, foreground=True)
    ctx['config'].database_id = None
    ctx['store']._schema_report = None


def test_legacy_adoption_is_explicit_and_preserves_existing_papers(setup):
    ctx = setup
    ctx['service']._import({'path': ctx['relative']}, {})
    before = ctx['store'].execute('SELECT number,data FROM papers ORDER BY number')
    raw(ctx['store'], 'DELETE FROM cirdc_identity')
    raw(ctx['store'], 'DELETE FROM schema_migrations WHERE version=4')
    assert ctx['store'].inspect_schema()['state'] == 'legacy_requires_adoption'
    with pytest.raises(SchemaError):
        ctx['store'].migrate()
    assert ctx['store'].execute('SELECT number,data FROM papers ORDER BY number') == before
    assert ctx['store'].migrate(adopt=True)['compatible']
    assert ctx['store'].execute('SELECT number,data FROM papers ORDER BY number') == before


def test_unidentified_nonempty_tables_cannot_be_adopted_as_an_empty_template(setup):
    ctx = setup
    ctx['service']._import({'path': ctx['relative']}, {})
    raw(ctx['store'], 'DELETE FROM cirdc_identity')
    raw(ctx['store'], 'DELETE FROM schema_migrations')
    assert ctx['store'].inspect_schema()['state'] == 'incompatible'
    with pytest.raises(SchemaError):
        ctx['store'].migrate(adopt=True)
    assert ctx['store'].execute('SELECT COUNT(*) AS n FROM papers')[0]['n'] == 2


def test_unknown_future_migration_version_is_read_only_rejected(setup):
    ctx = setup
    raw(ctx['store'], 'INSERT INTO schema_migrations(version) VALUES (999)')
    report = ctx['store'].inspect_schema()
    assert report['state'] == 'incompatible'
    before = ctx['store'].execute('SELECT version FROM schema_migrations ORDER BY version')
    with pytest.raises(SchemaError):
        ctx['store'].migrate(adopt=True)
    assert ctx['store'].execute('SELECT version FROM schema_migrations ORDER BY version') == before


def test_invalid_database_blocks_cli_engine_and_network_doctor(setup, monkeypatch):
    ctx = setup
    raw(ctx['store'], "UPDATE cirdc_identity SET application='another-application'")
    class Connection:
        def __init__(self, config):
            pass
        def __getattr__(self, key):
            return getattr(ctx['store'], key)
        def close(self):
            pass
    monkeypatch.setattr('cirdc.api.Store', Connection)
    def unexpected_source(*args, **kwargs):
        raise AssertionError('Invalid target must never open a source session')
    monkeypatch.setattr('cirdc.api.IEEE', unexpected_source)
    result = doctor(ctx['config'], network=True)
    assert result['status'] == 'not_ready'
    assert result['network'] == {'status': 'skipped', 'code': 'database_not_ready'}
    result = invoke('update', ctx['config'], foreground=True)
    assert result['code'] == 'schema_mismatch'
    assert 'password' not in json.dumps(result)
    assert ctx['store'].execute('SELECT COUNT(*) AS n FROM runs')[0]['n'] == 0
