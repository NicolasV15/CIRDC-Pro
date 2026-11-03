"""Explicit single-paper references, using the caller's existing HTTP budget."""
import json
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from .provider import UpstreamError


def article_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,64}', value):
        raise ValueError('Invalid article number')
    return value


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('br', 'p', 'div'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value):
    parser = _Text()
    parser.feed(str(value or ''))
    return ' '.join(''.join(parser.parts).split())


def normalize_reference(row, ordinal):
    if not isinstance(row, dict) or str(row.get('order')) != str(ordinal):
        raise UpstreamError('coverage_incomplete', 'Reference sequence is missing or repeated')
    links = row.get('links') or {}
    if not isinstance(links, dict):
        raise UpstreamError('parse_failed', 'Reference links must be an object')
    target = str(links.get('articleNumber') or '')
    if not re.fullmatch(r'[0-9]{1,64}', target):
        target = None
        link = links.get('documentLink')
        if isinstance(link, str):
            url = urlsplit(link)
            match = re.fullmatch(r'/document/([0-9]{1,64})/?', url.path)
            if match and (not url.netloc or url.hostname == 'ieeexplore.ieee.org'):
                target = match[1]
    title, text = plain(row.get('title')), plain(row.get('text'))
    if not (title or text):
        raise UpstreamError('parse_failed', 'Reference has no citation text')
    doi = str(links.get('doi') or '').strip() or None
    item = {'order': ordinal, 'label': str(row['order']), 'source_id': str(row.get('id') or ''),
            'text': text or title, 'title': title, 'target_number': target, 'doi': doi,
            'target_kind': 'paper' if target else 'scholar'}
    item['target_url'] = ('/papers/' + target if target else
                          'https://scholar.google.com/scholar?' + urlencode({'q': doi or title or text}))
    # Keep source citation data, never the response's userInfo/session object.
    raw = {key: row[key] for key in ('order', 'id', 'text', 'title', 'links', 'refType') if key in row}
    return item, raw


def fetch_references(provider, number, page_size=300):
    number = article_id(number)
    if not 1 <= page_size <= 300:
        raise ValueError('Invalid references page size')
    items, raw = [], []
    result = {'number': number, 'version': uuid.uuid4().hex,
              'fetched_at': datetime.now(timezone.utc).isoformat(),
              'state': 'complete', 'expected_total': None, 'error': None,
              'items': items, 'raw': raw}
    metadata = None
    try:
        metadata = provider._document_metadata(number)
        if str(metadata.get('articleNumber')) != number:
            raise UpstreamError('parse_failed', 'Document identity did not match')
        count = metadata.get('referenceCount')
        if count is not None:
            if isinstance(count, bool) or not str(count).isdigit():
                raise UpstreamError('parse_failed', 'Invalid source reference count')
            result['expected_total'] = int(count)
        expected = result['expected_total']
        while True:
            start = len(items) + 1
            data = provider.request('GET', f'/rest/document/{number}/references?start={start}&count={page_size}')
            if not isinstance(data, dict) or str(data.get('articleNumber')) != number:
                raise UpstreamError('parse_failed', 'References identity did not match')
            if any(data.get(k) for k in ('error', 'errors', 'errorCode', 'errorMessage', 'challenge', 'captcha')):
                raise UpstreamError('parse_failed', 'References endpoint returned an error')
            rows = data.get('references')
            if rows is None:
                if not items:
                    result.update(state='no_data' if expected == 0 else 'unavailable',
                                  error=None if expected == 0 else 'references_not_provided')
                elif expected is not None and len(items) != expected:
                    raise UpstreamError('coverage_incomplete', 'References ended before their declared count')
                break
            if not isinstance(rows, list):
                raise UpstreamError('parse_failed', 'References must be a list')
            if not rows:
                if expected is not None and len(items) != expected:
                    raise UpstreamError('coverage_incomplete', 'Reference count does not match')
                if not items:
                    # An explicit valid empty array confirms absence; a missing field does not.
                    result.update(state='no_data', expected_total=0)
                break
            if len(rows) > page_size:
                raise UpstreamError('coverage_incomplete', 'Unexpected reference page size')
            for row in rows:
                item, original = normalize_reference(row, len(items) + 1)
                items.append(item)
                raw.append(original)
            if expected is not None:
                if len(items) > expected:
                    raise UpstreamError('coverage_incomplete', 'References exceed their declared count')
                if len(items) == expected:
                    break
            # Advance by actual returned rows, including servers with smaller page caps.
    except UpstreamError as error:
        result.update(state='partial' if items else
                      'blocked' if error.code in ('access_restricted', 'access_denied') else 'failed',
                      error=error.code)
    from .relationship_source import availability, resolve_section, section_flag
    flag = section_flag(metadata, 'references')
    if result['state'] == 'unavailable' and not items:
        flag = resolve_section(provider, number, metadata, 'references')
        if flag is False:
            result.update(state='no_data', error=None)
    result.update(availability(result['state'], len(items), result['expected_total'], flag))
    result['evidence'] = {'section_flag': flag, 'count': result['expected_total'], 'request_number': number}
    return result
