"""Identifier-based bibliographic refresh within an update's selected scope."""
import json
from datetime import datetime, timezone

from .model import normalize
from .provider import UpstreamError


def publication_stage(record):
    value = str(record.get('articleContentType') or '').strip().lower()
    if 'early access' in value or str(record.get('volume') or '').upper() == 'PP':
        return 'early_access'
    if value in ('journals', 'magazines', 'conferences'):
        return 'final'
    return 'unknown'


def scope_condition(service, params):
    """Use existing file membership, so a changed publication year cannot exclude an ID."""
    publication, year = params.get('publication'), params.get('year')
    if publication is None and year is None:
        return '', []
    patterns, paths = [], []
    if year is None:
        patterns = [f'articleInfo/{kind}/{publication}/%' for kind in ('Journals', 'Conferences')]
    else:
        patterns = [f'articleInfo/Journals/{publication or "%"}/{int(year)}.json']
        for parent, venue in service.indexes()['Conferences'].items():
            if publication is not None and str(parent) != str(publication):
                continue
            for edition in venue.get('titleHistory', []):
                if str(edition.get('year') or '') == str(year) and edition.get('publicationNumber'):
                    paths.append(f'articleInfo/Conferences/{parent}/{edition["publicationNumber"]}.json')
    clauses = ['f.path LIKE %s'] * len(patterns)
    values = list(patterns)
    if paths:
        clauses.append('f.path IN (' + ','.join(['%s'] * len(paths)) + ')')
        values.extend(paths)
    return (' AND EXISTS (SELECT 1 FROM paper_files f WHERE f.number=p.number AND ('
            + ' OR '.join(clauses) + '))'), values


def seed(service, run_id, params, stats):
    if stats.get('early_access_seeded'):
        return
    # This marker is set only by new update submissions. Resuming an older job
    # never expands its frozen workflow merely because newer code is installed.
    if params.get('early_access_refresh') and params.get('stage') in ('all', 'metadata'):
        clause, values = scope_condition(service, params)
        last = ''
        while True:
            rows = service.store.execute(
                'SELECT p.number FROM papers p WHERE p.number>%s AND ('
                "LOWER(JSON_UNQUOTE(JSON_EXTRACT(p.data,'$.articleContentType'))) LIKE %s "
                "OR UPPER(JSON_UNQUOTE(JSON_EXTRACT(p.data,'$.volume')))=%s)" + clause
                + ' ORDER BY p.number LIMIT 500', (last, '%early access%', 'PP', *values))
            if not rows:
                break
            service.store.add_tasks(run_id, 'early_access',
                                    ((r['number'], {'number': r['number']}) for r in rows))
            last = rows[-1]['number']
    stats['early_access_seeded'] = True
    service.store.set_run(run_id, stats=stats)


def refresh(service, run_id, payload, record=None):
    # SQL and the export obligation commit together. After a filesystem failure,
    # replay the pending export instead of applying or counting the lookup twice.
    if payload.get('result', {}).get('applied'):
        return
    number = payload['number']
    old = service.store.paper(number)
    if old is None:
        raise ValueError('Selected Early Access article is absent from the database')
    record = normalize(record if record is not None else service.provider.bibliography(number), basic_only=True)
    if record['articleNumber'] != number:
        raise UpstreamError('parse_failed', 'Bibliographic lookup returned a different article')
    stage = publication_stage(record)
    if stage == 'unknown':
        raise UpstreamError('parse_failed', 'Bibliographic lookup did not establish the publication stage')
    if publication_stage(old['record']) == 'final' and stage == 'early_access':
        raise UpstreamError('publication_state_conflict', 'An Early Access response conflicts with a verified final record')
    service.store.upsert_records([record], basic_only=True)
    files = service.store.execute('SELECT path FROM paper_files WHERE number=%s', (number,))
    for row in files:
        service.store.mark_export_dirty(run_id, row['path'])
    result = {'applied': True, 'source': 'ieee_document_metadata',
              'checked_at': datetime.now(timezone.utc).isoformat(),
              'outcome': 'finalized' if stage == 'final' else 'still_early_access',
              'linked_files': len(files), 'previous': normalize(old['record'], basic_only=True)}
    payload['result'] = result
    service.store.execute('UPDATE tasks SET payload=%s WHERE run_id=%s AND kind=%s AND task_key=%s',
                          (json.dumps(payload), run_id, 'early_access', number))
    service.store.db.commit()


def summary(store, run_id):
    rows = store.execute(
        "SELECT status,COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload,'$.result.outcome')),'') AS outcome,"
        'COUNT(*) AS n FROM tasks WHERE run_id=%s AND kind=%s GROUP BY status,outcome',
        (run_id, 'early_access'))
    result = {'selected': sum(r['n'] for r in rows), 'completed': 0, 'finalized': 0,
              'still_early_access': 0, 'pending': 0, 'running': 0, 'failed': 0, 'blocked': 0}
    for row in rows:
        if row['status'] == 'done':
            result['completed'] += row['n']
            if row['outcome'] in ('finalized', 'still_early_access'):
                result[row['outcome']] += row['n']
        elif row['status'] in result:
            result[row['status']] += row['n']
    return result
