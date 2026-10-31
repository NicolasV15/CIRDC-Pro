import json
import pytest
from unittest.mock import Mock

from cirdc.config import Config
from cirdc.early_access import publication_stage
from cirdc.engine import Service
from cirdc.provider import UpstreamError
from test_engine import setup as setup, run_id
from test_provider import client, response


@pytest.mark.parametrize('stage,enabled', [('all', True), ('metadata', True), ('catalog', False), ('enrich', False)])
def test_plan_explains_automatic_scoped_refresh_without_starting_a_job(tmp_path, monkeypatch, stage, enabled):
    service = Service(Config(tmp_path, tmp_path / 'state'), store=Mock())
    monkeypatch.setattr(service, 'indexes', lambda: {'Journals': {}, 'Conferences': {}})
    monkeypatch.setattr(service.storage, 'article_paths', lambda: [])
    monkeypatch.setattr(service, 'summary', lambda: {})
    result = service.plan({'stage': stage})
    assert result['early_access_refresh']['enabled'] is enabled
    assert result['early_access_refresh']['fields'] == ['bibliographic']
    service.store.create_run.assert_not_called()


@pytest.mark.parametrize('early,kind,volume', [(True, 'Early Access Articles', 'PP'),
                                             (False, 'Journals', '36')])
def test_identifier_lookup_reads_live_document_field_names_and_only_basic_fields(tmp_path, monkeypatch, early, kind, volume):
    data = {'articleNumber': '7', 'publicationNumber': '4', 'publicationYear': '2025',
            'publicationDate': 'March 2025', 'title': 'Current title', 'isEarlyAccess': early,
            'formulaStrippedArticleTitle': 'Do not prefer the formula-stripped title',
            'isJournal': True, 'contentType': 'periodicals', 'contentTypeDisplay': 'Journals',
            'volume': volume, 'issue': '99' if early else '3', 'startPage': '3976', 'endPage': '3989',
            'doi': '', 'abstract': 'Must remain owned by the document enrichment stage',
            'keywords': [{'type': 'Author Keywords', 'kwd': ['document']}],
            'authors': [{'id': '2', 'name': 'Second'}, {'id': '1', 'name': 'First'}]}
    source, session = client(tmp_path, monkeypatch, [response(text='<html>Search</html>'),
                              response(text='xplGlobal.document.metadata=' + json.dumps(data) + ';')])
    record = source.bibliography('7')
    assert record['articleNumber'] == '7' and record['publicationYear'] == '2025'
    assert record['articleTitle'] == 'Current title'
    assert record['articleContentType'] == kind and record['volume'] == volume
    assert [a['preferredName'] for a in record['authors']] == ['Second', 'First']
    assert 'abstract' not in record and 'keywords' not in record
    assert session.request.call_args.args[1].endswith('/document/7')


@pytest.mark.parametrize('data', [{}, {'articleNumber': '8'},
                                {'articleNumber': '7', 'title': 'Unknown stage'},
                                {'articleNumber': '7', 'contentTypeDisplay': 'Journals'},
                                {'articleNumber': '7', 'title': 'Title', 'contentTypeDisplay': 'Journals',
                                 'isEarlyAccess': 'unexpected'},
                                {'articleNumber': '7', 'title': 'Title', 'contentTypeDisplay': 'Journals',
                                 'authors': {'name': 'Unordered author object'}}])
def test_identifier_lookup_rejects_missing_identity_or_unusable_metadata(tmp_path, monkeypatch, data):
    source, _ = client(tmp_path, monkeypatch, [response(text='<html>Search</html>'),
                      response(text='xplGlobal.document.metadata=' + json.dumps(data) + ';')])
    with pytest.raises(UpstreamError) as error:
        source.bibliography('7')
    assert error.value.code == 'parse_failed'


def prepare(ctx):
    for row in ctx['rows']:
        row.update(abstract='Existing complete abstract retained throughout bibliography refresh.',
                   keywords={'Author Keywords': ['existing']})
    ctx['rows'][0].update(articleContentType='Early Access Articles', volume='PP', issue='99',
                          publicationYear='2023', startPage='1', endPage='14')
    ctx['config'].destination(ctx['relative']).write_text(json.dumps(ctx['rows']))
    ctx['service']._import({'path': ctx['relative']}, {})
    return ctx['numbers'][0]


def params(ctx, **extra):
    return {'stage': 'metadata', 'skip_import': True, 'skip_catalog': True,
            'publication': ctx['publication'], 'year': 2026, 'workers': 1, **extra}


def source_for(number, early=False, problem=None):
    class Source:
        def __init__(self):
            self.lookups = []
        def search_all(self, *args):
            return []
        def bibliography(self, value):
            assert value == number
            self.lookups.append(value)
            if problem:
                raise problem
            return {'articleNumber': value, 'articleTitle': 'Latest bibliographic title',
                    'publicationYear': '2028', 'publicationDate': 'January 2028',
                    'articleContentType': 'Early Access Articles' if early else 'Journals',
                    'volume': 'PP' if early else '42', 'issue': '99' if early else '1',
                    'startPage': '100', 'endPage': '113',
                    'abstract': 'Must not overwrite the existing complete abstract',
                    'keywords': {'Author Keywords': ['must-not-import']}}
        def document(self, value):
            raise AssertionError('Bibliographic updates cannot implicitly perform enrichment')
    return Source()


@pytest.mark.parametrize('stage,workers', [('metadata', 1), ('metadata', 2), ('all', 1), ('all', 2)])
def test_new_full_and_incremental_updates_automatically_refresh_selected_early_access(setup, stage, workers):
    ctx = setup
    number = prepare(ctx)
    source = source_for(number)
    ctx['service'].provider = source
    before = ctx['store'].paper(number)
    job = ctx['service'].start(params(ctx, stage=stage, workers=workers), foreground=True)['run_id']
    assert source.lookups == [number]
    paper = ctx['store'].paper(number)
    assert paper['record']['publicationYear'] == '2028'
    assert paper['record']['volume'] == '42'
    assert paper['record']['abstract'] == before['record']['abstract']
    assert paper['record']['keywords'] == before['record']['keywords']
    assert (paper['abstract_state'], paper['keywords_state']) == ('complete', 'complete')
    saved = json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]
    assert saved['publicationYear'] == '2028' and saved['abstract'] == before['record']['abstract']
    assert ctx['service'].status(job)['early_access'] == {
        'selected': 1, 'completed': 1, 'finalized': 1, 'still_early_access': 0,
        'pending': 0, 'running': 0, 'failed': 0, 'blocked': 0}
    assert ctx['store'].run(job)['status'] == 'completed'
    assert ctx['store'].execute('SELECT COUNT(*) AS n FROM papers')[0]['n'] == 2


def test_old_job_resume_keeps_its_original_workflow_even_if_early_access_exists(setup):
    ctx = setup
    number = prepare(ctx)
    source = source_for(number)
    ctx['service'].provider = source
    old = run_id(ctx, {**params(ctx), 'cooperative_writes': True})
    ctx['service'].resume(old, foreground=True)
    assert source.lookups == []
    assert not ctx['store'].execute('SELECT id FROM tasks WHERE run_id=%s AND kind=%s', (old, 'early_access'))
    assert publication_stage(ctx['store'].paper(number)['record']) == 'early_access'


def test_selected_year_uses_file_membership_and_updates_all_existing_copies(setup):
    ctx = setup
    number = prepare(ctx)
    extra = f'articleInfo/Journals/{ctx["publication"]}/2023.json'
    ctx['config'].destination(extra).write_text(json.dumps([ctx['rows'][0]]))
    ctx['service']._import({'path': extra}, {})
    # The other article is Early Access in a different selected-year file.
    other = f'articleInfo/Journals/{ctx["publication"]}7/2026.json'
    p = ctx['config'].destination(other);p.parent.mkdir(parents=True)
    row = {**ctx['rows'][0], 'articleNumber': ctx['numbers'][1]}
    p.write_text(json.dumps([row]))
    ctx['service']._import({'path': other}, {})
    ctx['store'].execute('DELETE FROM paper_files WHERE path=%s AND number=%s',
                          (ctx['relative'], ctx['numbers'][1]));ctx['store'].db.commit()
    ctx['config'].destination(ctx['relative']).write_text(json.dumps([ctx['rows'][0]]))
    source = source_for(number)
    ctx['service'].provider = source
    job = ctx['service'].start(params(ctx), foreground=True)['run_id']
    assert source.lookups == [number]
    for path in (extra, ctx['relative']):
        saved = next(r for r in json.loads(ctx['config'].destination(path).read_text())
                     if r['articleNumber'] == number)
        assert saved['publicationYear'] == '2028' and saved['articleContentType'] == 'Journals'
        assert saved['abstract'] == ctx['rows'][0]['abstract']
    assert publication_stage(ctx['store'].paper(ctx['numbers'][1])['record']) == 'early_access'
    assert ctx['store'].run(job)['status'] == 'completed'


def test_scope_includes_old_early_access_even_when_historical_fetch_was_skipped(setup):
    ctx = setup
    number = prepare(ctx)
    oldpath = f'articleInfo/Journals/{ctx["publication"]}/2023.json'
    ctx['config'].destination(oldpath).write_text(json.dumps([ctx['rows'][0]]))
    ctx['service']._import({'path': oldpath}, {})
    ctx['store'].execute('INSERT INTO sync_cursors(path,source_count) VALUES (%s,%s)', (oldpath, 1))
    ctx['store'].db.commit()
    source = source_for(number)
    ctx['service'].provider = source
    job = ctx['service'].start(params(ctx, year=None), foreground=True)['run_id']
    assert source.lookups == [number]
    assert not ctx['store'].execute('SELECT id FROM tasks WHERE run_id=%s AND kind=%s AND task_key=%s',
                                   (job, 'fetch', oldpath))


def test_still_early_access_is_checked_once_per_job_and_selected_again_next_update(setup):
    ctx = setup
    number = prepare(ctx)
    source = source_for(number, early=True)
    ctx['service'].provider = source
    for _ in range(2):
        job = ctx['service'].start(params(ctx), foreground=True)['run_id']
        status = ctx['service'].status(job)
        assert status['early_access']['completed'] == status['early_access']['still_early_access'] == 1
        assert status['status'] == 'completed'
    assert source.lookups == [number, number]


def test_access_failure_keeps_record_and_bounded_retry_recovers_same_job(setup):
    ctx = setup
    number = prepare(ctx)
    ctx['service'].provider = source_for(number, problem=UpstreamError('access_restricted', 'HTTP 418'))
    job = ctx['service'].start(params(ctx), foreground=True)['run_id']
    assert ctx['service'].status(job)['early_access']['blocked'] == 1
    assert publication_stage(ctx['store'].paper(number)['record']) == 'early_access'
    source = source_for(number);ctx['service'].provider = source
    ctx['service'].resume(job, retry=True, foreground=True)
    assert source.lookups == [number]
    assert ctx['service'].status(job)['early_access']['finalized'] == 1


@pytest.mark.parametrize('failure', ['sql', 'json'])
def test_early_access_recovers_single_sided_write_failure_without_refetching_or_double_counting(setup, monkeypatch, failure):
    import cirdc.engine as engine
    ctx = setup
    number = prepare(ctx)
    source = source_for(number);ctx['service'].provider = source
    if failure == 'json':
        original = engine.atomic_write
        def fail(path, content):
            if path == ctx['config'].destination(ctx['relative']):
                raise OSError('Filesystem temporarily unavailable')
            return original(path, content)
        monkeypatch.setattr(engine, 'atomic_write', fail)
    else:
        original = ctx['store'].execute
        def fail(sql, values=()):
            if sql.startswith('UPDATE tasks SET payload=') and len(values) == 4 and values[-2] == 'early_access':
                raise RuntimeError('Database write interrupted')
            return original(sql, values)
        monkeypatch.setattr(ctx['store'], 'execute', fail)
    with pytest.raises((OSError, RuntimeError)):
        ctx['service'].start(params(ctx), foreground=True)
    job = ctx['store'].execute('SELECT id FROM runs ORDER BY created_at DESC,id DESC LIMIT 1')[0]['id']
    if failure == 'json':
        monkeypatch.setattr(engine, 'atomic_write', original)
        ctx['store'].upsert_records([{'articleNumber': number, 'publicationYear': '2029',
                                      'articleTitle': 'Newer metadata committed while this export was pending'}],
                                    basic_only=True)
        ctx['store'].db.commit()
    else:
        monkeypatch.setattr(ctx['store'], 'execute', original)
        assert publication_stage(ctx['store'].paper(number)['record']) == 'early_access'
    ctx['service'].resume(job, foreground=True)
    assert source.lookups == [number]
    assert ctx['service'].status(job)['early_access']['finalized'] == 1
    assert ctx['store'].counts(job)['exports_pending'] == 0
    if failure == 'json':
        saved = json.loads(ctx['config'].destination(ctx['relative']).read_text())[0]
        assert saved['publicationYear'] == '2029'
        assert saved['articleTitle'] == ctx['store'].paper(number)['record']['articleTitle']


def test_conference_year_selection_uses_catalog_edition_and_does_not_select_another_year(setup):
    ctx = setup
    prepare(ctx)
    family = ctx['publication'] + '9'
    ctx['service'].indexes = lambda: {'Journals': {}, 'Conferences': {family: {'titleHistory': [
        {'publicationNumber': '501', 'year': '2025'}, {'publicationNumber': '502', 'year': '2026'}]}}}
    for number, child in zip(ctx['numbers'], ['501', '502']):
        path = f'articleInfo/Conferences/{family}/{child}.json'
        ctx['store'].upsert_records([{'articleNumber': number, 'articleContentType': 'Early Access Articles',
                                     'volume': 'PP'}], path, basic_only=True)
    ctx['store'].db.commit()
    job = run_id(ctx)
    ctx['service']._seed_early_access(job, {'stage': 'metadata', 'early_access_refresh': True,
                                           'publication': family, 'year': 2026}, {})
    rows = ctx['store'].execute('SELECT task_key FROM tasks WHERE run_id=%s', (job,))
    assert [row['task_key'] for row in rows] == [ctx['numbers'][1]]


def test_all_stage_keeps_enrichment_as_a_separate_following_phase(setup):
    ctx = setup
    number = prepare(ctx)
    ctx['store'].execute('UPDATE papers SET abstract_state=%s,keywords_state=%s WHERE number=%s',
                         ('pending', 'pending', number));ctx['store'].db.commit()
    source = source_for(number)
    documents = []
    def document(value):
        documents.append(value)
        record = ctx['store'].paper(value)['record']
        assert record['volume'] == '42' and record['abstract'] == ctx['rows'][0]['abstract']
        return {'articleNumber': value, 'abstract': 'Separately checked document abstract',
                'keywords': {'Author Keywords': ['separately-checked']}}, {
                    'abstract': 'complete', 'keywords': 'complete'}
    source.document = document
    ctx['service'].provider = source
    job = ctx['service'].start(params(ctx, stage='all'), foreground=True)['run_id']
    assert documents == source.lookups == [number]
    assert ctx['store'].paper(number)['record']['abstract'] == 'Separately checked document abstract'
    assert ctx['store'].run(job)['status'] == 'completed'


def test_missing_or_conflicting_lookup_is_failed_without_destroying_existing_metadata(setup):
    ctx = setup
    number = prepare(ctx)
    job = run_id(ctx)
    ctx['store'].add_tasks(job, 'early_access', [(number, {'number': number})])
    with pytest.raises(UpstreamError):
        ctx['service']._refresh_early_access(job, {'number': number}, {}, record={
            'articleNumber': '999', 'articleContentType': 'Journals'})
    ctx['store'].upsert_records([{'articleNumber': number, 'articleContentType': 'Journals',
                                 'volume': '40', 'issue': '6'}], basic_only=True)
    ctx['store'].db.commit()
    with pytest.raises(UpstreamError) as error:
        ctx['service']._refresh_early_access(job, {'number': number}, {}, record={
            'articleNumber': number, 'articleContentType': 'Early Access Articles', 'volume': 'PP'})
    assert error.value.code == 'publication_state_conflict'
    assert ctx['store'].paper(number)['record']['volume'] == '40'


def test_cached_early_access_cannot_regress_verified_final_bibliography(setup):
    ctx = setup
    number = ctx['numbers'][0]
    final = {'articleNumber': number, 'articleContentType': 'Journals', 'volume': '40',
             'issue': '6', 'publicationYear': '2025', 'startPage': '2983', 'endPage': '2992'}
    ctx['store'].upsert_records([final], basic_only=True)
    ctx['store'].upsert_records([{**final, 'articleContentType': 'Early Access Articles', 'volume': 'PP',
                                 'issue': '99', 'publicationYear': '2022', 'startPage': '1', 'endPage': '10'}],
                                basic_only=True)
    assert ctx['store'].paper(number)['record']['volume'] == '40'
    assert ctx['store'].paper(number)['record']['publicationYear'] == '2025'


def test_all_selected_identifiers_cross_the_seed_batch_boundary_without_duplicates(setup):
    ctx = setup
    numbers = [str(700000000 + i) for i in range(501)]
    ctx['store'].upsert_records([{'articleNumber': n, 'articleContentType': 'Early Access'} for n in numbers],
                                ctx['relative'], basic_only=True)
    ctx['store'].db.commit()
    job = run_id(ctx)
    selected = {'stage': 'metadata', 'early_access_refresh': True, 'publication': ctx['publication'], 'year': 2026}
    stats = {}
    ctx['service']._seed_early_access(job, selected, stats)
    ctx['service']._seed_early_access(job, selected, stats)
    tasks = ctx['store'].execute('SELECT task_key FROM tasks WHERE run_id=%s AND kind=%s', (job, 'early_access'))
    assert len(tasks) == 501 and {r['task_key'] for r in tasks} == set(numbers)
