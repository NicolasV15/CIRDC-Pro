from collections import deque

import pytest

from cirdc.patent_citation_source import fetch_patent_citations, normalize_patent
from cirdc.provider import UpstreamError


def row(order, number='US6323801B1'):
    return {'order': str(order), 'title': 'Example patent', 'displayText': 'A public patent citation',
            'patentNumber': number, 'links': {}}


class Source:
    def __init__(self, pages, sections=None, metrics=None):
        self.pages = deque(pages)
        self.paths = []
        self.metadata = {'articleNumber': '123', 'title': 'Parent article'}
        if sections is not None:self.metadata['sections'] = sections
        if metrics is not None:self.metadata['metrics'] = metrics

    def _document_metadata(self, number):return self.metadata

    def request(self, method, path):
        assert path != '/rest/document/123', 'No full-text access from patent reads'
        self.paths.append(path)
        value = self.pages.popleft()
        if isinstance(value, Exception):raise value
        return value


def summary(count, rows=None):
    value = {'patentCitationCount': count}
    if rows is not None:value['patentCitations'] = rows
    return value


def test_pagination_over_300_keeps_duplicates_and_uses_one_budgeted_provider():
    pages = [summary(302)]
    for start, end in [(1, 100), (101, 200), (201, 300), (301, 302)]:
        pages.append(summary(302, [row(i) for i in range(start, end+1)]))
    p = Source(pages);value = fetch_patent_citations(p, '123')
    assert value['state'] == 'complete' and len(value['items']) == 302
    assert value['items'][0]['publication_number'] == value['items'][-1]['publication_number']
    assert 'start=301&count=100&type=patent' in p.paths[-1]
    assert all(v['target_url'] == 'https://patents.google.com/patent/US6323801B1/en' for v in value['items'])


@pytest.mark.parametrize('payload', [summary(0), {'patentCitations': []}])
def test_explicit_zero_is_distinct_from_missing(payload):
    value = fetch_patent_citations(Source([payload]), '123')
    assert value['state'] == 'no_data' and value['empty_reason'] == 'zero_count'
    assert value['counts']['patent'] == 0
    missing = fetch_patent_citations(Source([{}]), '123')
    assert missing['state'] == 'unavailable' and missing['counts']['patent'] is None


def test_paper_zero_does_not_imply_patent_zero():
    value = fetch_patent_citations(Source([{'ieeeCitationCount': 0, 'nonIeeeCitationCount': 0}]), '123')
    assert value['source_presence'] == 'unknown' and value['counts']['patent'] is None
    value = fetch_patent_citations(Source([summary(1, [row(1)])], {'references': 'false'}), '123')
    assert value['state'] == 'complete'


def test_verified_absent_section_and_metadata_zero_have_distinct_reasons():
    absent = fetch_patent_citations(Source([{}], {'citedby': 'false'}), '123')
    assert absent['source_presence'] == 'absent' and absent['empty_reason'] == 'section_absent'
    zero = fetch_patent_citations(Source([{}], {'citedby': 'false'}, {'citationCountPatent': 0}), '123')
    assert zero['source_presence'] == 'present' and zero['empty_reason'] == 'zero_count'


@pytest.mark.parametrize('bad', [False, -1, 'unknown', 1.2])
def test_invalid_count_does_not_fall_back_to_zero(bad):
    value = fetch_patent_citations(Source([summary(bad, [])], metrics={'citationCountPatent': 0}), '123')
    assert value['state'] == 'failed' and value['counts']['patent'] is None


@pytest.mark.parametrize('second', [summary(2, [row(1)]), summary(3, [row(2)]), UpstreamError('access_restricted', 'limited')])
def test_repeated_page_drift_and_restriction_preserve_partial(second):
    value = fetch_patent_citations(Source([summary(2, [row(1)]), second]), '123')
    assert value['state'] == 'partial' and len(value['items']) == 1


def test_wrong_identity_and_error_responses_are_not_empty():
    for bad in [{'articleNumber': '999'}, {'error': 'unavailable'}]:
        assert fetch_patent_citations(Source([bad]), '123')['state'] == 'failed'


def test_conflicting_zero_count_is_not_legal_empty():
    value = fetch_patent_citations(Source([summary(0)], metrics={'citationCountPatent': 12}), '123')
    assert value['state'] == 'failed' and value['empty_reason'] is None
    assert value['counts']['patent'] is None


def test_text_and_identifiers_use_safe_patent_targets_only():
    value = row(1, 'US 6,323,801 B1');value['links']['articleNumber'] = '999'
    assert normalize_patent(value, 1)['publication_number'] == 'US6323801B1'
    value = row(1, None);value['links'] = {'patentLink': 'https://evil.example/patent/US6323801B1', 'articleNumber': '999'}
    target = normalize_patent(value, 1)
    assert target['target_kind'] == 'patent_search' and target['target_url'].startswith('https://patents.google.com/?q=')


def test_missing_parent_id_is_supported_and_user_info_not_retained():
    value = fetch_patent_citations(Source([{**summary(1, [row(1)]), 'userInfo': {'secret': 'sensitive-session-value','institute':False}}]), '123')
    assert value['state'] == 'complete' and 'sensitive-session-value' not in str(value)
    assert value['evidence']['access_flags']=={'institute':False}


def test_publisher_numeric_id_and_separate_metadata_use_trusted_patent_url():
    item = {'order':'1','id':'11853096','patentNumber':'11853096','title':'Example patent',
            'inventors':'Harris, Michael; Meacham, Daniel','assignees':['EXAMPLE COMPANY'],
            'grantDate':'26 December 2023','externalLink':'https://patents.google.com/patent/US11853096'}
    value = normalize_patent(item,1)
    assert value['publication_number']=='US11853096' and value['country']=='US'
    assert value['target_url']=='https://patents.google.com/patent/US11853096/en'
    assert value['inventors']==['Harris, Michael','Meacham, Daniel']
    assert value['assignee']=='EXAMPLE COMPANY' and value['publication_date']=='26 December 2023'
