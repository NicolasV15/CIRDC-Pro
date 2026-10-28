import json
from collections import deque
from unittest.mock import Mock
import pytest
from cirdc.config import Config
from cirdc.model import normalize, merge
from cirdc.provider import IEEE, UpstreamError


def response(data=None, status=200, text=''):
    r = Mock(status_code=status, text=text)
    r.json.return_value = data
    return r


def client(tmp_path, monkeypatch, responses):
    monkeypatch.setattr('cirdc.provider.time.sleep', lambda _: None)
    session = Mock()
    session.headers = {}
    queue = deque(responses)
    session.request.side_effect = lambda *a, **k: queue.popleft()
    config = Config(tmp_path, tmp_path / 'state')
    return IEEE(config, session), session


def test_missing_page_rejected(tmp_path, monkeypatch):
    p, _ = client(tmp_path, monkeypatch, [
        response({'totalRecords': 2, 'totalPages': 2, 'records': [{'articleNumber': '1'}]}),
        response({'totalRecords': 2, 'totalPages': 2, 'records': []}),
    ])
    with pytest.raises(UpstreamError, match='distinct'):
        p.search_all('4', 2026)


def test_duplicate_page_rejected(tmp_path, monkeypatch):
    data = {'totalRecords': 2, 'totalPages': 2, 'records': [{'articleNumber': '1'}]}
    p, _ = client(tmp_path, monkeypatch, [response(data), response(data)])
    with pytest.raises(UpstreamError):
        p.search_all('4', 2026)


@pytest.mark.parametrize('status', [202, 418, 429])
def test_access_response_is_not_empty_success(tmp_path, monkeypatch, status):
    p, session = client(tmp_path, monkeypatch, [response(status=status) for _ in range(3)])
    with pytest.raises(UpstreamError) as error:
        p.search_all('4', 2026)
    assert error.value.code == 'access_restricted'
    assert session.request.call_count == 3


def test_valid_empty_response_is_distinct(tmp_path, monkeypatch):
    p, _ = client(tmp_path, monkeypatch, [response({'totalRecords': 0, 'totalPages': 0, 'records': []})])
    assert p.search_all('4', 2026) == []


def test_source_no_data_only_after_valid_document(tmp_path, monkeypatch):
    p, _ = client(tmp_path, monkeypatch, [response(text='<html>Search</html>'),
                                        response(text='xplGlobal.document.metadata={"articleNumber":"7"};')])
    data, states = p.document('7')
    assert data['keywords'] == {}
    assert states == {'abstract': 'no_data', 'keywords': 'no_data'}


def test_challenge_page_not_source_absence(tmp_path, monkeypatch):
    p, _ = client(tmp_path, monkeypatch, [response(text='<html>Search</html>'),
                                        response(text='<html>Try again</html>')])
    with pytest.raises(UpstreamError) as error:
        p.document('7')
    assert error.value.code == 'parse_failed'


def test_keyword_categories_and_order(tmp_path, monkeypatch):
    value = {'articleNumber': '7', 'abstract': 'Summary',
             'keywords': [{'type': 'Author Keywords', 'kwd': ['a', 'b']},
                          {'type': 'IEEE Keywords', 'kwd': ['c']}]}
    p, _ = client(tmp_path, monkeypatch, [response(text='<html>Search</html>'),
                                        response(text='xplGlobal.document.metadata = ' + json.dumps(value) + ';')])
    data, states = p.document('7')
    assert data['keywords'] == {'Author Keywords': ['a', 'b'], 'IEEE Keywords': ['c']}
    assert states == {'abstract': 'complete', 'keywords': 'complete'}


def test_identity_and_empty_doi():
    a = normalize({'articleNumber': 1, 'doi': '', 'authors': [{'preferredName': 'B'}, {'preferredName': 'A'}]})
    b = normalize({'articleNumber': 2, 'doi': ''})
    assert a['articleNumber'] != b['articleNumber']
    assert [r['preferredName'] for r in a['authors']] == ['B', 'A']
    assert merge({'abstract': 'Keep'}, {'abstract': ''})['abstract'] == 'Keep'


def test_large_query_cannot_silently_truncate(tmp_path, monkeypatch):
    p, _ = client(tmp_path, monkeypatch, [response({'totalRecords': 20000, 'totalPages': 200,
                                                 'records': [{'articleNumber': '1', 'volume': '1', 'issue': '1'}]})])
    with pytest.raises(UpstreamError) as error:
        p.search_all('4', 2026)
    assert error.value.code == 'coverage_incomplete'


def test_pagination_count_change_rejected(tmp_path, monkeypatch):
    p, _ = client(tmp_path, monkeypatch, [
        response({'totalRecords': 2, 'totalPages': 2, 'records': [{'articleNumber': '1'}]}),
        response({'totalRecords': 3, 'totalPages': 2, 'records': [{'articleNumber': '2'}]}),
    ])
    with pytest.raises(UpstreamError, match='changed'):
        p.search_all('4', 2026)


def test_config_does_not_expose_credentials(tmp_path):
    c = Config(tmp_path, tmp_path / 'state', {'password': 'do-not-expose', 'user': 'sample'})
    assert 'do-not-expose' not in json.dumps(c.public())
    assert 'do-not-expose' not in repr(c)
    with pytest.raises(ValueError):
        c.destination('../escape.json')
