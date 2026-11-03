from contextlib import closing

import pytest

from cirdc.web.index import put_rows, search
from cirdc.web.settings import connect
from test_web import website as website


@pytest.mark.parametrize('params', [{}, {'q': 'RF'}, {'q': 'RF', 'sort': 'year'},
                                 {'q': 'Alice', 'field': 'authors'}])
def test_total_counts_the_entire_match_set_on_every_page(website, params):
    cursor = None
    numbers = []
    for _ in range(3):
        page = search({**params, 'limit': '3', **({'cursor': cursor} if cursor else {})})
        assert page['total'] == 9
        assert len(page['items']) == 3
        numbers.extend(row['number'] for row in page['items'])
        cursor = page['next_cursor']
    assert len(set(numbers)) == 9
    assert cursor is None
    assert search({**params, 'limit': '1'})['total'] == 9


@pytest.mark.parametrize('params,total', [
    ({'q': 'RF', 'year_from': '2025', 'year_to': '2025', 'venue': '4',
      'kind': 'Journals', 'abstract_state': 'complete', 'keywords_state': 'complete'}, 9),
    ({'q': 'UniqueBodyToken', 'field': 'abstract'}, 9),
    ({'q': 'UniqueBodyToken', 'field': 'title'}, 0),
    ({'q': 'RF', 'year_from': '2026'}, 0),
    ({'q': 'RF', 'keywords_state': 'no_data'}, 0),
    ({'q': 'RF', 'venue': '999'}, 0),
    ({'q': '10.1234/example1'}, 1),
])
def test_total_honors_query_fields_and_combined_filters(website, params, total):
    page = search(params)
    assert page['total'] == total
    assert len(page['items']) == total


def test_author_matches_count_each_paper_once_and_invalidate_after_an_index_change(website):
    params = {'field': 'authors', 'q': 'Alex'}
    assert search(params)['total'] == 0
    with closing(connect('search.sqlite')) as db:
        put_rows(db, [{'number': '200', 'data': {
            'articleTitle': 'Two matching identities on one paper', 'publicationYear': '2025',
            'authors': [{'id': '11', 'preferredName': 'Alex Kim'},
                        {'id': '12', 'preferredName': 'Alex Kim'}]},
            'abstract_state': 'complete', 'keywords_state': 'complete'}])
        db.commit()
    assert search(params)['total'] == 1
    assert search({'author_id': '11'})['total'] == 1
    assert search({'field': 'authors', 'q': 'Alice', 'author_unidentified': '1'})['total'] == 9
