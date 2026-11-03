"""Incoming patents, independently fetched with the caller's IEEE HTTP budget."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

from .citation_source import count
from .provider import UpstreamError
from .reference_source import article_id, plain
from .relationship_source import verify_response, resolve_section


def publication_number(value):
    if not isinstance(value, str):
        return None
    normalized = re.sub(r'[\s,.-]', '', value).upper()
    return normalized if re.fullmatch(r'[A-Z]{2}[0-9]{4,15}(?:[A-Z][0-9]{0,2})?', normalized) else None


def normalize_patent(row, ordinal):
    if not isinstance(row, dict):
        raise UpstreamError('parse_failed', 'Invalid citing patent')
    if 'order' in row and str(row['order']) != str(ordinal):
        raise UpstreamError('coverage_incomplete', 'Patent sequence is missing or repeated')
    links = row.get('links') or {}
    if not isinstance(links, dict):
        raise UpstreamError('parse_failed', 'Patent links must be an object')
    number = next((n for v in [row.get('patentNumber'), row.get('publicationNumber'),
                               links.get('patentNumber'), links.get('publicationNumber')]
                   if (n := publication_number(v))), None)
    if not number:
        # The publisher can put its canonical Google Patents URL in different
        # metadata fields. Derive the country prefix from that trusted URL,
        # never assume one from a bare numeric patent identifier.
        for value in [*links.values(), *row.values()]:
            if isinstance(value, str):
                try:address = urlsplit(value)
                except ValueError:continue
                match = re.fullmatch(r'/patent/([^/]+)(?:/[a-z]{2})?/?', address.path)
                if address.hostname == 'patents.google.com' and match:
                    number = publication_number(match[1])
                    if number:
                        break
    title = plain(row.get('title') or row.get('patentTitle'))
    text = plain(row.get('displayText') or row.get('text'))
    if not (title or text):
        raise UpstreamError('parse_failed', 'Patent has no citation text')
    inventors = row.get('inventors') or []
    if isinstance(inventors, str):
        inventors = inventors.split(';')
    if not isinstance(inventors, list):
        inventors = []
    assignee = row.get('assignee') or row.get('assignees')
    if isinstance(assignee, list):
        assignee = '; '.join(plain(v) for v in assignee if isinstance(v, str))
    if not isinstance(assignee, str):assignee = None
    return {'group': 'patent', 'order': ordinal, 'label': str(row.get('order', ordinal)),
            'source_id': str(row.get('id') or ''), 'title': title, 'text': text or title,
            'publication_number': number, 'country': number[:2] if number else None,
            'publication_date': plain(row.get('publicationDate') or row.get('grantDate') or row.get('patentDate')) or None,
            'inventors': [plain(v) for v in inventors if isinstance(v, str)],
            'assignee': plain(assignee) or None,
            'target_kind': 'patent' if number else 'patent_search',
            'target_url': ('https://patents.google.com/patent/' + number + '/en' if number else
                           'https://patents.google.com/?' + urlencode({'q': title or text}))}


def _rows(data):
    rows = data.get('patentCitations')
    if isinstance(rows, dict):
        return rows.get('patent')
    return rows


def _evidence(data):
    # Retain public response evidence, never session/user/account information.
    payload = data.get('patentCitations')
    return {'keys': list(data), 'patent_payload_sample': payload[:2] if isinstance(payload, list) else payload,
            **{key: data[key] for key in
               ('articleNumber', 'articleId', 'title', 'displayDocTitle', 'patentCitationCount') if key in data}}


def _access_flags(data):
    info = data.get('userInfo')
    if not isinstance(info, dict):return {}
    return {key: info[key] for key in ('institute', 'member', 'subscribedContent', 'showPatentCitations')
            if isinstance(info.get(key), bool)}


def fetch_patent_citations(provider, number, page_size=100):
    number = article_id(number)
    if not 1 <= page_size <= 100:
        raise ValueError('Invalid patent citations page size')
    result = {'number': number, 'version': uuid.uuid4().hex,
              'fetched_at': datetime.now(timezone.utc).isoformat(), 'state': 'complete',
              'source_presence': 'unknown', 'empty_reason': None,
              'counts': {'patent': None}, 'group_states': {'patent': 'missing'},
              'items': [], 'raw': [], 'error': None, 'evidence': {'request_number': number, 'responses': []}}
    metadata = None
    try:
        metadata = provider._document_metadata(number)
        if str(metadata.get('articleNumber')) != number:
            raise UpstreamError('parse_failed', 'Document identity differs')
        result['evidence']['access_flags'] = _access_flags(metadata)
    except UpstreamError as error:
        result['metadata_error'] = error.code
        metadata = None
    try:
        data = provider.request('GET', '/rest/document/' + number + '/citations')
        verify_response(data, number, metadata)
        result['evidence'].setdefault('access_flags', {}).update(_access_flags(data))
        result['evidence']['responses'].append(_evidence(data))
        expected = count(data.get('patentCitationCount'))
        if 'patentCitationCount' in data and data['patentCitationCount'] is not None and expected is None:
            raise UpstreamError('parse_failed', 'Invalid patent count')
        if metadata:
            metrics = metadata.get('metrics')
            if isinstance(metrics, dict):
                metadata_count = count(metrics.get('citationCountPatent'))
                result['evidence']['metadata_count'] = metadata_count
                if expected is not None and metadata_count is not None and expected != metadata_count:
                    raise UpstreamError('coverage_incomplete', 'Patent counts disagree between sources')
                if expected is None:expected = metadata_count
        result['counts']['patent'] = expected
        rows = _rows(data)
        seen_pages = set()
        while True:
            if rows is None and expected is None:
                result.update(state='unavailable', error='patent_citations_not_provided')
                break
            if rows is None and expected == 0:
                result['state'] = 'no_data'
                break
            if rows is None:
                start = len(result['items']) + 1
                data = provider.request('GET', f'/rest/document/{number}/citations?start={start}&count={page_size}&type=patent')
                verify_response(data, number, metadata)
                result['evidence']['responses'].append(_evidence(data))
                new_count = count(data.get('patentCitationCount'))
                if 'patentCitationCount' in data and data['patentCitationCount'] is not None and new_count is None:
                    raise UpstreamError('parse_failed', 'Invalid patent count')
                if new_count is not None and new_count != expected:
                    result['counts']['patent'] = None
                    raise UpstreamError('coverage_incomplete', 'Patent count changed')
                rows = _rows(data)
                if rows is None:
                    raise UpstreamError('coverage_incomplete', 'Patent list is missing')
            if not isinstance(rows, list):
                raise UpstreamError('parse_failed', 'Patents must be a list')
            fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
            if rows and fingerprint in seen_pages:
                raise UpstreamError('coverage_incomplete', 'Repeated patent page')
            seen_pages.add(fingerprint)
            if not rows and expected is None:
                result['counts']['patent'] = 0
                result['state'] = 'no_data'
                break
            for row in rows:
                result['items'].append(normalize_patent(row, len(result['items']) + 1))
                result['raw'].append(row)
            if expected is None:
                result.update(state='partial', error='patent_count_missing')
                break
            if len(result['items']) > expected:
                result['counts']['patent'] = None
                raise UpstreamError('coverage_incomplete', 'Patents exceed source count')
            if len(result['items']) == expected:
                result['state'] = 'complete' if expected else 'no_data'
                break
            if not rows:
                raise UpstreamError('coverage_incomplete', 'Patents ended before source count')
            rows = None
    except UpstreamError as error:
        result.update(state='partial' if result['items'] else
                      'blocked' if error.code in ('access_restricted', 'access_denied') else 'failed', error=error.code)
    if result['items']:
        result['source_presence'] = 'present'
    elif result['state'] == 'no_data':
        result.update(source_presence='present', empty_reason='zero_count')
    elif result['state'] == 'unavailable':
        flag = resolve_section(provider, number, metadata, 'citations')
        result['evidence']['section_flag'] = flag
        if flag is False:
            result.update(state='no_data', source_presence='absent', empty_reason='section_absent', error=None)
    result['group_states']['patent'] = result['state']
    return result
