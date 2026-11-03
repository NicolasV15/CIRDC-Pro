from contextlib import closing
from types import SimpleNamespace

import pytest

from cirdc.config import Config
from cirdc.web import capture, index
from cirdc.web.settings import connect


class RestrictedStore:
    instances = []
    installed = True
    allow_setup = False

    def __init__(self, config):
        self.statements = []
        self.migrations = 0
        self.closed = False
        self.db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
        self.instances.append(self)

    def execute(self, sql, params=()):
        self.statements.append(sql)
        if not sql.startswith('SELECT'):
            assert self.allow_setup, 'Runtime account attempted a database write outside its queue'
            return []
        if 'web_schema_migrations' in sql:
            return [{'version': 2}] if self.installed else []
        if 'web_settings' in sql:
            return [{'value': '1'}]
        return []

    def migrate(self):
        assert self.allow_setup, 'Runtime account attempted a schema migration'
        self.migrations += 1

    def close(self):
        self.closed = True


@pytest.fixture
def restricted_index(tmp_path, monkeypatch):
    monkeypatch.setenv('CIRDC_WEB_STATE', str(tmp_path / 'web'))
    monkeypatch.setattr('cirdc.store.Store', RestrictedStore)
    monkeypatch.setattr(index, 'refresh_overview', lambda *args: None)
    monkeypatch.setattr('cirdc.web.authors.backfill_step', lambda *args: False)
    monkeypatch.setattr(RestrictedStore, 'instances', [])
    monkeypatch.setattr(RestrictedStore, 'installed', True)
    monkeypatch.setattr(RestrictedStore, 'allow_setup', False)
    with closing(connect('search.sqlite')) as db:
        index.initialize(db)
        index.put_rows(db, [{'number': '12345', 'data': {'articleTitle': 'Preserved fixture'},
                            'abstract_state': 'pending', 'keywords_state': 'pending'}])
        index.save_meta(db, phase='ready', indexed=1, capture_seeded_version=1)
        db.commit()
    return Config(tmp_path, tmp_path / 'state')


def test_index_runtime_works_without_schema_or_metadata_write_privileges(restricted_index):
    result = index.run_index(restricted_index, once=True)
    assert result['phase'] == 'ready'
    store = RestrictedStore.instances[-1]
    assert store.migrations == 0 and store.closed
    assert all(sql.startswith('SELECT') for sql in store.statements)


def test_missing_capture_setup_preserves_existing_search_data(restricted_index, monkeypatch):
    monkeypatch.setattr(RestrictedStore, 'installed', False)
    with pytest.raises(RuntimeError, match='init-index'):
        index.run_index(restricted_index, once=True)
    with closing(connect('search.sqlite')) as db:
        assert db.execute('SELECT title FROM docs WHERE number=?', ('12345',)).fetchone()[0] == 'Preserved fixture'
        assert index.metadata(db)['phase'] == 'ready'


def test_explicit_index_initialization_uses_setup_credentials(restricted_index, monkeypatch):
    monkeypatch.setattr(RestrictedStore, 'allow_setup', True)
    installed = []
    monkeypatch.setattr(capture, 'install', lambda store: installed.append(store))
    assert index.initialize_indexing(restricted_index) == {'status': 'ready', 'capture_version': 2}
    store = RestrictedStore.instances[-1]
    assert installed == [store] and store.migrations == 1 and store.closed


def test_update_does_not_attempt_automatic_schema_changes(tmp_path, monkeypatch):
    from cirdc import api
    monkeypatch.setattr(api, 'Store', RestrictedStore)
    monkeypatch.setattr(RestrictedStore, 'allow_setup', False)
    monkeypatch.setattr(api, 'Service', lambda config, store: SimpleNamespace(
        start=lambda params, foreground: {'run_id': 'fixture-run', 'status': 'queued'}))
    value = api._invoke('update', Config(tmp_path, tmp_path / 'state'))
    assert value['run_id'] == 'fixture-run'
    assert RestrictedStore.instances[-1].migrations == 0
