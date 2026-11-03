from collections import deque
from urllib.parse import parse_qs, urlsplit

import pytest

from cirdc.provider import UpstreamError
from cirdc.reference_source import fetch_references, normalize_reference


def row(order, number='456', **extra):
    return {'order': str(order), 'id': 'ref' + str(order), 'title': 'A useful article',
            'text': 'Author, <em>A useful article</em>, 2025.',
            'links': {'articleNumber': number}, **extra}


class Source:
    def __init__(self, pages, count=None):
        self.pages = deque(pages)
        self.metadata = {'articleNumber': '123'}
        if count is not None:
            self.metadata['referenceCount'] = count
        self.paths = []

    def _document_metadata(self, number):
        return self.metadata

    def request(self, method, path):
        self.paths.append(path)
        if path == '/rest/document/123':
            return {'articleNumber': '123'}
        value = self.pages.popleft()
        if isinstance(value, Exception):
            raise value
        return value


def page(rows, number='123'):
    return {'articleNumber': number, 'references': rows, 'userInfo': {'private': 'never save'}}


def test_more_than_300_references_and_duplicate_targets_are_preserved():
    source = Source([page([row(i) for i in range(1, 301)]), page([row(i) for i in range(301, 306)])], 305)
    result = fetch_references(source, '123')
    assert result['state'] == 'complete'
    assert len(result['items']) == 305
    assert result['items'][0]['target_number'] == result['items'][-1]['target_number']
    assert 'start=301&count=300' in source.paths[-1]
    assert 'userInfo' not in str(result)


def test_unknown_count_uses_verified_terminal_response_and_real_page_lengths():
    source = Source([page([row(1), row(2)]), page([row(3)]), {'articleNumber': '123'}])
    result = fetch_references(source, '123')
    assert result['state'] == 'complete' and len(result['items']) == 3
    assert 'start=3&' in source.paths[1] and 'start=4&' in source.paths[2]


@pytest.mark.parametrize('response,count,state', [
    ({'articleNumber': '123'}, None, 'unavailable'),
    ({'articleNumber': '123'}, 0, 'no_data'),
    (page([]), None, 'no_data'),
    (page([]), 2, 'failed'),
])
def test_absence_requires_source_evidence(response, count, state):
    assert fetch_references(Source([response], count), '123')['state'] == state


@pytest.mark.parametrize('next_page', [
    page([row(1)]), page([row(3)]), page([row(2)], '999'),
    {'articleNumber': '123'}, UpstreamError('access_restricted', 'limited'),
])
def test_failed_pagination_preserves_partial_items(next_page):
    result = fetch_references(Source([page([row(1)]), next_page], 2), '123')
    assert result['state'] == 'partial' and len(result['items']) == 1 and result['error']


def test_access_restriction_is_not_no_data():
    source = Source([UpstreamError('access_restricted', 'limited')])
    assert fetch_references(source, '123')['state'] == 'blocked'


def test_source_count_change_and_wrong_identity_fail():
    assert fetch_references(Source([page([row(1), row(2)])], 1), '123')['state'] == 'partial'
    source = Source([])
    source.metadata['articleNumber'] = '999'
    assert fetch_references(source, '123')['state'] == 'failed'


def test_links_use_only_ieee_identity_or_scholar_search():
    item, raw = normalize_reference(row(1, '9007199254740993'), 1)
    assert item['target_url'] == '/papers/9007199254740993'
    assert item['text'] == 'Author, A useful article, 2025.'
    assert '<em>' in raw['text']
    item, _ = normalize_reference(row(2, links={'doi': '10.1234/a&b?x=1'}), 2)
    assert item['target_kind'] == 'scholar'
    assert parse_qs(urlsplit(item['target_url']).query)['q'] == ['10.1234/a&b?x=1']
    item, _ = normalize_reference(row(3, links={'documentLink': 'https://other.example/document/456'}), 3)
    assert item['target_number'] is None
    item, _ = normalize_reference(row(4, links={'documentLink': '/document/789'}), 4)
    assert item['target_number'] == '789'


def test_missing_title_falls_back_to_plain_text_without_executing_html():
    item, _ = normalize_reference(row(1, title='', text='Book <script>unsafe()</script> &amp; chapter', links={}), 1)
    assert item['text'] == 'Book & chapter'
    assert parse_qs(urlsplit(item['target_url']).query)['q'] == ['Book & chapter']
