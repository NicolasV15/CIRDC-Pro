from datetime import datetime
from unittest.mock import Mock
import pytest
from cirdc.config import Config
from cirdc.engine import Service
from cirdc.provider import UpstreamError
from test_provider import client, response


@pytest.mark.parametrize('payload', [
    {'totalRecords': 0, 'totalPages': 1, 'endRecord': 0, 'startRecord': 0,
     'meta': {'queryParams': {'contentType': 'Conferences', 'rowsPerPage': '0'}}},
    {'totalRecords': 0},
    {'totalRecords': '0', 'totalPages': '1'},
    {'totalRecords': 0, 'records': None, 'totalPages': 0},
    {'totalRecords': 0, 'records': [], 'totalPages': 1},
])
def test_confirmed_zero_accepts_omitted_optional_fields(tmp_path, monkeypatch, payload):
    provider, session = client(tmp_path, monkeypatch, [response(payload)])
    assert provider.publication_year('Conferences', 2027) == []
    assert session.request.call_count == 1


@pytest.mark.parametrize('payload', [
    {}, {'records': []}, {'totalPages': 0},
    {'totalRecords': 1, 'totalPages': 1},
    {'totalRecords': 1, 'records': []},
    {'totalRecords': False, 'records': []},
    {'totalRecords': -1, 'records': []},
    {'totalRecords': 0, 'error': 'upstream error'},
])
def test_missing_or_invalid_response_is_not_future_absence(tmp_path, monkeypatch, payload):
    provider, _ = client(tmp_path, monkeypatch, [response(payload)])
    with pytest.raises(UpstreamError) as error:
        provider.publication_year('Conferences', 2027)
    assert error.value.code == 'parse_failed'


@pytest.mark.parametrize('payload', [
    {'totalRecords': 0, 'records': [{'publicationNumber': '7'}], 'totalPages': 1},
    {'totalRecords': 0, 'records': [], 'totalPages': 2},
    {'totalRecords': 1, 'records': [], 'totalPages': 0},
])
def test_contradictory_zero_or_page_counts_are_rejected(tmp_path, monkeypatch, payload):
    provider, _ = client(tmp_path, monkeypatch, [response(payload)])
    with pytest.raises(UpstreamError) as error:
        provider.publication_year('Conferences', 2027)
    assert error.value.code == 'coverage_incomplete'


def test_future_year_with_data_is_paginated_normally(tmp_path, monkeypatch):
    provider, session = client(tmp_path, monkeypatch, [
        response({'totalRecords': 2, 'totalPages': 2, 'records': [{'publicationNumber': '1'}]}),
        response({'totalRecords': 2, 'totalPages': 2, 'records': [{'publicationNumber': '2'}]}),
    ])
    assert provider.publication_year('Journals', 2027) == [
        {'publicationNumber': '1'}, {'publicationNumber': '2'}]
    assert session.request.call_count == 2


def test_later_empty_page_cannot_turn_positive_year_into_absence(tmp_path, monkeypatch):
    provider, _ = client(tmp_path, monkeypatch, [
        response({'totalRecords': 2, 'totalPages': 2, 'records': [{'publicationNumber': '1'}]}),
        response({'totalRecords': 0, 'totalPages': 1}),
    ])
    with pytest.raises(UpstreamError) as error:
        provider.publication_year('Conferences', 2027)
    assert error.value.code == 'coverage_incomplete'


@pytest.mark.parametrize('status', [202, 403, 418, 429])
def test_future_year_access_rejection_stays_blocked(tmp_path, monkeypatch, status):
    provider, session = client(tmp_path, monkeypatch, [response(status=status)] * 3)
    with pytest.raises(UpstreamError) as error:
        provider.publication_year('Conferences', 2027)
    assert error.value.code == 'access_restricted'
    assert session.request.call_count == 3


def test_future_year_html_challenge_is_not_absence(tmp_path, monkeypatch):
    invalid = response(text='<html>challenge</html>')
    invalid.json.side_effect = ValueError('not JSON')
    provider, _ = client(tmp_path, monkeypatch, [invalid] * 3)
    with pytest.raises(UpstreamError) as error:
        provider.publication_year('Conferences', 2027)
    assert error.value.code == 'parse_failed'


def freeze(monkeypatch, year):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(year, 1, 1, tzinfo=tz)
    monkeypatch.setattr('cirdc.engine.datetime', Clock)


@pytest.mark.parametrize('year', [2026, 2027, 2030])
def test_default_window_rolls_with_calendar_and_ignores_far_future_folders(tmp_path, monkeypatch, year):
    freeze(monkeypatch, year)
    config = Config(tmp_path, tmp_path / 'state')
    for kind in ['Journals', 'Conferences']:
        (tmp_path / 'publicationInfo' / kind / '2099').mkdir(parents=True)
    captured = []
    store = Mock()
    store.add_tasks.side_effect = lambda run, kind, tasks: captured.extend((kind, key) for key, _ in tasks)
    service = Service(config, store=store, provider=Mock())
    service._seed('run', {'skip_import': True}, {})
    assert {key for kind, key in captured if kind == 'catalog'} == {
        f'{kind}/{value}' for kind in ['Journals', 'Conferences']
        for value in range(year - 1, year + 2)}


def test_explicit_catalog_year_is_respected(tmp_path, monkeypatch):
    freeze(monkeypatch, 2026)
    captured = []
    store = Mock()
    store.add_tasks.side_effect = lambda run, kind, tasks: captured.extend(key for key, _ in tasks)
    Service(Config(tmp_path, tmp_path / 'state'), store=store, provider=Mock())._seed(
        'run', {'stage': 'catalog', 'year': 2029}, {})
    assert set(captured) == {'Journals/2029', 'Conferences/2029'}
