from cirdc.store import Store, SCHEMA, MIGRATION_VERSION


def test_reserved_pdf_columns_use_nullable_defaults_without_changing_metadata_upserts():
    ddl=next(sql for sql in SCHEMA if 'CREATE TABLE IF NOT EXISTS papers (' in sql)
    assert 'has_pdf TINYINT(1) NULL DEFAULT NULL' in ddl and 'pdf_path TEXT NULL DEFAULT NULL' in ddl
    assert MIGRATION_VERSION==4


def test_existing_database_migration_requests_instant_addition_and_restores_timeout():
    class Connection:
        def commit(self):pass
    class Migration(Store):
        def __init__(self):self.db=Connection();self.calls=[]
        def execute(self,sql,args=()):
            self.calls.append((sql,args))
            if sql.startswith('SHOW COLUMNS'):return [{'Field':'number'},{'Field':'data'}]
            if 'information_schema.statistics' in sql:return [{'INDEX_NAME':'field_coverage'}]
            if '@@SESSION.lock_wait_timeout' in sql:return [{'n':60}]
            return []
    store=Migration();store.migrate()
    alters=[sql for sql,args in store.calls if sql.startswith('ALTER TABLE papers')]
    assert len(alters)==1 and 'ALGORITHM=INSTANT, LOCK=NONE' in alters[0]
    assert store.calls[-2]==('SET SESSION lock_wait_timeout=%s',(60,))


def test_trigger_upgrade_captures_metadata_without_a_drop_create_gap():
    from cirdc.web.capture import install
    class Connection:
        def commit(self):pass
    class Capture:
        db=Connection()
        def __init__(self):self.calls=[]
        def execute(self,sql,args=()):
            self.calls.append(sql)
            if 'information_schema.TRIGGERS' in sql:return [{'TRIGGER_NAME':'cirdc_web_papers_'+s} for s in ['insert','update','delete']]
            if sql=='SELECT version FROM web_schema_migrations':return [{'version':1}]
            return []
    store=Capture();install(store)
    bridge=next(i for i,s in enumerate(store.calls) if s.startswith('CREATE TRIGGER cirdc_web_papers_update_bridge_v2'))
    drop=store.calls.index('DROP TRIGGER cirdc_web_papers_update')
    replacement=next(i for i,s in enumerate(store.calls) if s.startswith('CREATE TRIGGER cirdc_web_papers_update AFTER'))
    assert bridge<drop<replacement
    assert 'OLD.data <=> NEW.data' in store.calls[replacement]
    assert 'has_pdf' not in store.calls[replacement] and 'pdf_path' not in store.calls[replacement]
