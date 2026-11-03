"""Explicit incoming paper citations; group order spaces stay independent."""
import uuid
from datetime import datetime, timezone

from .provider import UpstreamError
from .reference_source import article_id, normalize_reference
from .relationship_source import availability, resolve_section, verify_response

GROUPS = ('ieee', 'nonIeee')
COUNTERS = {'ieee': 'ieeeCitationCount', 'nonIeee': 'nonIeeeCitationCount'}


def count(value):
    if isinstance(value, bool) or value is None or not str(value).isdigit():
        return None
    return int(value)


def normalize_citation(row, group, ordinal):
    if not isinstance(row, dict):
        raise UpstreamError('parse_failed', 'Invalid citing paper')
    item, _ = normalize_reference({**row, 'text': row.get('displayText') or row.get('text') or ''}, ordinal)
    item['group'] = group
    raw = {k: row[k] for k in ('order', 'id', 'title', 'displayText', 'text', 'links') if k in row}
    return item, raw


def fetch_citations(provider, number, page_size=100):
    number = article_id(number)
    if not 1 <= page_size <= 100:
        raise ValueError('Invalid citations page size')
    result = {'number': number, 'version': uuid.uuid4().hex, 'fetched_at': datetime.now(timezone.utc).isoformat(),
              'state': 'complete', 'source_presence': 'unknown', 'empty_reason': None,
              'counts': {g: None for g in GROUPS}, 'group_states': {},
              'items': [], 'raw': {g: [] for g in GROUPS}, 'error': None}
    metadata = None
    try:
        metadata = provider._document_metadata(number)
        if str(metadata.get('articleNumber')) != number:
            raise UpstreamError('parse_failed', 'Document identity differs')
    except UpstreamError as error:
        result['metadata_error'] = error.code
        metadata = None
    try:
        first = provider.request('GET', '/rest/document/' + number + '/citations')
        verify_response(first, number, metadata)
    except UpstreamError as error:
        result.update(state='blocked' if error.code in ('access_restricted', 'access_denied') else 'failed', error=error.code)
        return result
    containers = first.get('paperCitations')
    result['reported_counts'] = {g: first.get(COUNTERS[g]) if isinstance(first.get(COUNTERS[g]),(str,int)) else None for g in GROUPS}
    if containers is not None and not isinstance(containers, dict):
        result.update(state='failed', error='parse_failed')
        return result
    flag = None
    for group in GROUPS:
        expected = count(first.get(COUNTERS[group]))
        result['counts'][group] = expected
        items = []
        raw = result['raw'][group]
        state = 'complete'
        error = None
        rows = (containers or {}).get(group)
        try:
            if COUNTERS[group] in first and first[COUNTERS[group]] is not None and expected is None:
                raise UpstreamError('parse_failed', 'Invalid citation count')
            while True:
                if rows is None and expected == 0:
                    state = 'no_data'
                    break
                if rows is None and expected is None:
                    state, error = 'unavailable', 'citation_count_missing'
                    break
                if rows is None:
                    page = provider.request('GET', f'/rest/document/{number}/citations?start={len(items)+1}&count={page_size}&type={group}')
                    verify_response(page, number, metadata)
                    new_count = count(page.get(COUNTERS[group]))
                    if new_count is not None and new_count != expected:
                        result['counts'][group] = None
                        raise UpstreamError('coverage_incomplete', 'Citation count changed')
                    listing = page.get('paperCitations')
                    rows = listing.get(group) if isinstance(listing, dict) else None
                    if rows is None:
                        raise UpstreamError('coverage_incomplete', 'Citations group list is missing')
                if not isinstance(rows, list):
                    raise UpstreamError('parse_failed', 'Citations must be a list')
                if not rows and expected is None:
                    # Explicitly present empty arrays are evidence; omitted groups
                    # and omitted counters without an array remain unknown.
                    result['counts'][group] = 0
                    state = 'no_data'
                    break
                for row in rows:
                    item, original = normalize_citation(row, group, len(items) + 1)
                    items.append(item);raw.append(original)
                if expected is None:
                    state, error = ('partial', 'citation_count_missing') if items else ('unavailable', 'citation_count_missing')
                    break
                if len(items) > expected:
                    result['counts'][group] = None
                    raise UpstreamError('coverage_incomplete', 'Citations exceed source count')
                if len(items) == expected:
                    state = 'complete' if expected else 'no_data'
                    break
                if not rows:
                    raise UpstreamError('coverage_incomplete', 'Citations ended before source count')
                rows = None
        except UpstreamError as exception:
            state = 'partial' if items else 'blocked' if exception.code in ('access_restricted', 'access_denied') else 'failed'
            error = exception.code
        result['items'].extend(items)
        result['group_states'][group] = state
        if error:
            result['error'] = result['error'] or error
    states = set(result['group_states'].values())
    if states <= {'complete', 'no_data'}:
        result['state'] = 'complete' if result['items'] else 'no_data'
    else:
        result['state'] = 'partial' if result['items'] else 'blocked' if 'blocked' in states else 'unavailable' if 'unavailable' in states else 'failed'
    if not result['items'] and result['state'] in ('no_data', 'unavailable'):
        flag = resolve_section(provider, number, metadata, 'citations')
        if flag is False and states <= {'unavailable', 'no_data'}:
            result.update(state='no_data', error=None)
            result['group_states'] = {g: 'no_data' for g in GROUPS}
    result.update(availability(result['state'], len(result['items']), None, flag))
    result['evidence'] = {'section_flag': flag, 'counts': result['counts'], 'request_number': number}
    return result
