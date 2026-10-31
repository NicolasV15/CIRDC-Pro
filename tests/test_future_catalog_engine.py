import json
from datetime import datetime
from test_engine import setup, run_id
from cirdc.provider import UpstreamError


def freeze(monkeypatch, year):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(year, 10, 28, tzinfo=tz)
    monkeypatch.setattr('cirdc.engine.datetime', Clock)


def seed_year(ctx, year):
    run = run_id(ctx, {'stage': 'catalog', 'skip_catalog': True})
    ctx['store'].add_tasks(run, 'catalog', [(f'Conferences/{year}', {'kind': 'Conferences', 'year': year})])
    return run


def test_future_zero_is_deferred_and_existing_snapshot_is_preserved(setup, monkeypatch):
    ctx = setup
    freeze(monkeypatch, 2026)
    class Source:
        def publication_year(self, kind, year):
            return []
    ctx['service'].provider = Source()
    snapshot = ctx['config'].destination('publicationInfo/Conferences/2027/cirdc.json')
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text('{"records":[{"publicationNumber":"7"}],"totalRecords":1}')
    before = snapshot.read_bytes()
    index = ctx['config'].destination('publicationInfo/all_conferences.json')
    index_before = index.read_bytes()
    run = seed_year(ctx, 2027)
    ctx['service'].work(run)
    result = ctx['service'].status(run)
    assert result['status'] == 'partial'
    assert result['counts']['deferred'] == 1
    assert result['counts'].get('failed', 0) == 0
    assert not result['errors']
    assert result['deferred'][0]['detail']['reason'] == 'confirmed_zero_records'
    assert snapshot.read_bytes() == before
    assert index.read_bytes() == index_before
    assert result['counts']['exports_pending'] == 0


def test_future_year_can_be_rechecked_beyond_failure_retry_budget_then_accept_data(setup, monkeypatch):
    ctx = setup
    freeze(monkeypatch, 2026)
    class Source:
        available = False
        def publication_year(self, kind, year):
            if not self.available:
                return []
            return [{'parentPublicationNumber': '18000001', 'parentTitle': 'Synthetic meeting',
                     'publicationNumber': '18000002', 'titleHistory': [
                         {'publicationNumber': '18000002', 'displayTitle': 'Synthetic edition', 'startYear': '2027'}]}]
    source = Source()
    ctx['service'].provider = source
    run = seed_year(ctx, 2027)
    ctx['service'].work(run)
    for _ in range(3):
        ctx['service'].resume(run, retry=True, foreground=True)
    assert ctx['service'].status(run)['deferred'][0]['attempts'] == 4
    source.available = True
    ctx['service'].resume(run, retry=True, foreground=True)
    state = ctx['service'].status(run)
    assert state['status'] == 'completed'
    assert state['counts']['done'] == 1
    assert state['deferred'] == []
    snapshot = ctx['config'].destination('publicationInfo/Conferences/2027/cirdc.json')
    assert json.loads(snapshot.read_text())['totalRecords'] == 1


def test_current_year_zero_is_a_confirmed_empty_snapshot(setup, monkeypatch):
    ctx = setup
    freeze(monkeypatch, 2026)
    class Source:
        def publication_year(self, kind, year):
            return []
    ctx['service'].provider = Source()
    run = seed_year(ctx, 2026)
    ctx['service'].work(run)
    state = ctx['service'].status(run)
    assert state['status'] == 'completed'
    assert state['counts'].get('deferred', 0) == 0
    snapshot = ctx['config'].destination('publicationInfo/Conferences/2026/cirdc.json')
    assert json.loads(snapshot.read_text())['totalRecords'] == 0


def test_future_access_block_is_not_a_deferred_empty_year(setup, monkeypatch):
    ctx = setup
    freeze(monkeypatch, 2026)
    class Source:
        def publication_year(self, kind, year):
            raise UpstreamError('access_restricted', 'Upstream returned HTTP 418')
    ctx['service'].provider = Source()
    run = seed_year(ctx, 2027)
    ctx['service'].work(run)
    state = ctx['service'].status(run)
    assert state['status'] == 'blocked'
    assert state['counts']['blocked'] == 1
    assert state['deferred'] == []
