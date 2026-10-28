from test_engine import setup, run_id
import json
import pytest


def test_database_ack_failure_after_file_replace_is_idempotent(setup, monkeypatch):
    ctx = setup
    run = run_id(ctx)
    values = [{**r, 'abstract': 'Recovered'} for r in ctx['rows']]
    ctx['store'].stage_export(run, ctx['relative'], values)
    ctx['store'].db.commit()
    execute = ctx['store'].execute
    once = [True]
    def fail_ack(sql, params=()):
        if sql.startswith('UPDATE exports SET status') and once[0]:
            once[0] = False
            raise RuntimeError('Simulated acknowledgement failure')
        return execute(sql, params)
    monkeypatch.setattr(ctx['store'], 'execute', fail_ack)
    with pytest.raises(RuntimeError):
        ctx['service'].flush_exports(run)
    ctx['store'].db.rollback()
    assert json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]['abstract'] == 'Recovered'
    assert ctx['store'].counts(run)['exports_pending'] == 1
    ctx['service'].flush_exports(run)
    assert ctx['store'].counts(run)['exports_pending'] == 0
