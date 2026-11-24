"""Tests for unified IEEE + arXiv search, Demo integration, and skill manifest."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from cirdc.web.unified_search import UnifiedSearchUnavailable, unified_search

SITE = Path(__file__).resolve().parents[1]


class FakeArxivCatalog:
    def __init__(self, items, fail=False):
        self.items = list(items)
        self.fail = fail
        self.calls = []

    def search(
        self,
        query,
        limit=20,
        cursor=None,
        *,
        field='all',
        sort='relevance',
        view='',
        k='20',
        terms='expand',
        category='',
        year_from='',
        year_to='',
        totals='',
    ):
        self.calls.append({'query': query, 'field': field, 'sort': sort, 'category': category, 'year_from': year_from, 'year_to': year_to})
        if self.fail:
            raise sqlite3.OperationalError('database is locked')
        offset = 0
        if cursor:
            import base64
            offset = json.loads(base64.urlsafe_b64decode(cursor + '===').decode())['offset']
        filtered = list(self.items)
        if category:
            wanted = {c.strip().lower() for c in category.split(',') if c.strip()}
            filtered = [it for it in filtered if wanted & {c.lower() for c in it.get('categories', [])}]
        if year_from:
            filtered = [it for it in filtered if (it.get('year') or 0) >= int(year_from)]
        if year_to:
            filtered = [it for it in filtered if (it.get('year') or 0) <= int(year_to)]
        if sort == 'year':
            filtered.sort(key=lambda it: (it.get('year') or 0, it.get('submitted_at') or '', it.get('arxiv_id') or ''), reverse=True)
        page = [] if totals == 'only' else filtered[offset:offset + limit]
        has_more = offset + limit < len(filtered) and view != 'top' and totals != 'only'
        import base64
        nxt = base64.urlsafe_b64encode(json.dumps({'q': 'sig', 'offset': offset + limit}).encode()).decode() if has_more else None
        return {
            'scope': 'metadata',
            'items': page,
            'total': None if totals == 'defer' else len(filtered),
            'total_exact': True,
            'partial': False,
            'next_cursor': nxt,
            'query': {'terms': terms, 'groups': []},
        }

    def with_submission_dates(self, items):
        return items


def make_fake_ieee(items, *, fail=False, calls=None):
    def search(params):
        if calls is not None:
            calls.append(dict(params))
        if fail:
            raise sqlite3.OperationalError('ieee busy')
        offset = int(params.get('cursor') or 0)
        limit = int(params.get('limit', 25))
        totals = params.get('totals', 'include')
        filtered = list(items)
        if params.get('venue_any'):
            wanted = set(params['venue_any'].split(','))
            filtered = [it for it in filtered if it.get('publication_number') in wanted]
        if params.get('year_from'):
            filtered = [it for it in filtered if (it.get('year') or 0) >= int(params['year_from'])]
        if params.get('year_to'):
            filtered = [it for it in filtered if (it.get('year') or 0) <= int(params['year_to'])]
        if params.get('sort') == 'year':
            filtered.sort(key=lambda it: (it.get('year') or 0, it.get('order_number') or '', it.get('number') or ''), reverse=True)
        page = [] if totals == 'only' else filtered[offset:offset + limit]
        nxt = str(offset + len(page)) if (offset + len(page) < len(filtered) and params.get('view') != 'top' and totals != 'only') else None
        return {
            'items': page,
            'total': None if totals == 'defer' else len(filtered),
            'total_exact': True,
            'next_cursor': nxt,
            'query': {'terms': params.get('terms', 'expand'), 'groups': []},
        }
    return search


SAMPLE_IEEE = [
    {'number': '101', 'title': 'IEEE A', 'year': 2026, 'order_number': '003', 'publication_number': '4'},
    {'number': '102', 'title': 'IEEE B', 'year': 2025, 'order_number': '002', 'publication_number': '4'},
    {'number': '103', 'title': 'IEEE C', 'year': 2024, 'order_number': '001', 'publication_number': '81'},
]
SAMPLE_ARXIV = [
    {'paper_id': 1, 'arxiv_id': '2611.00001', 'title': 'arXiv 1', 'year': 2026, 'submitted_at': '2026-11-12T10:00:00Z', 'categories': ['eess.SY']},
    {'paper_id': 2, 'arxiv_id': '2609.00002', 'title': 'arXiv 2', 'year': 2026, 'submitted_at': '2026-09-01T10:00:00Z', 'categories': ['cs.AR']},
    {'paper_id': 3, 'arxiv_id': '2505.00003', 'title': 'arXiv 3', 'year': 2025, 'submitted_at': '2025-05-05T10:00:00Z', 'categories': ['cs.AI']},
    {'paper_id': 4, 'arxiv_id': '2401.00004', 'title': 'arXiv 4', 'year': 2024, 'submitted_at': '2024-01-10T10:00:00Z', 'categories': ['eess.SY']},
]


def test_unified_rrf_pagination_has_no_duplicates_or_skips():
    ieee = make_fake_ieee(SAMPLE_IEEE)
    arxiv = FakeArxivCatalog(SAMPLE_ARXIV)
    seen = []
    cursor = None
    pages = 0
    while True:
        res = unified_search({'q': 'amplifier', 'sort': 'relevance', 'limit': '2', **({'cursor': cursor} if cursor else {})},
                             ieee_search=ieee, arxiv_catalog=arxiv)
        pages += 1
        assert res['total'] == 7
        assert res['partial'] is False
        assert res['selected_sources'] == ['ieee', 'arxiv']
        for it in res['items']:
            key = (it['source'], it.get('number') or it.get('arxiv_id'))
            seen.append(key)
        cursor = res['next_cursor']
        if not cursor:
            break
        assert pages < 10
    assert len(seen) == 7
    assert len(set(seen)) == 7
    # First page should interleave rank-1 from both sources.
    assert {seen[0][0], seen[1][0]} == {'ieee', 'arxiv'}


def test_unified_chronological_pagination_is_sorted_and_complete():
    ieee = make_fake_ieee(SAMPLE_IEEE)
    arxiv = FakeArxivCatalog(SAMPLE_ARXIV)
    items = []
    cursor = None
    while True:
        res = unified_search({'sort': 'year', 'limit': '3', **({'cursor': cursor} if cursor else {})},
                             ieee_search=ieee, arxiv_catalog=arxiv)
        items.extend(res['items'])
        cursor = res['next_cursor']
        if not cursor:
            break
    assert len(items) == 7
    years = [it['year'] for it in items]
    assert years == sorted(years, reverse=True)
    keys = [(it['source'], it.get('number') or it.get('arxiv_id')) for it in items]
    assert len(set(keys)) == 7


def test_source_specific_fields_and_filters_link_cleanly():
    ieee_calls = []
    ieee = make_fake_ieee(SAMPLE_IEEE, calls=ieee_calls)
    arxiv = FakeArxivCatalog(SAMPLE_ARXIV)

    res_kw = unified_search({'q': 'adc', 'field': 'keywords', 'venue_any': '4'}, ieee_search=ieee, arxiv_catalog=arxiv)
    assert res_kw['sources']['ieee']['status'] == 'ok'
    assert res_kw['sources']['arxiv']['status'] == 'skipped_field'
    assert res_kw['source_notes'] == [{'source': 'arxiv', 'code': 'field_not_supported', 'field': 'keywords'}]
    assert len(arxiv.calls) == 0
    assert all(it['source'] == 'ieee' for it in res_kw['items'])
    assert len(res_kw['items']) == 2

    res_cat = unified_search({'q': 'eess', 'field': 'categories', 'category': 'eess.SY'}, ieee_search=ieee, arxiv_catalog=arxiv)
    assert res_cat['sources']['ieee']['status'] == 'skipped_field'
    assert res_cat['sources']['arxiv']['status'] == 'ok'
    assert res_cat['source_notes'] == [{'source': 'ieee', 'code': 'field_not_supported', 'field': 'categories'}]
    assert all(it['source'] == 'arxiv' for it in res_cat['items'])
    assert len(res_cat['items']) == 2



def test_ieee_status_and_author_filters_reach_ieee_only():
    ieee_calls = []
    arxiv = FakeArxivCatalog(SAMPLE_ARXIV)
    params = {'abstract_state': 'pending', 'keywords_state': 'no_data', 'author_unidentified': '1'}
    unified_search(params, ieee_search=make_fake_ieee(SAMPLE_IEEE, calls=ieee_calls), arxiv_catalog=arxiv)
    assert {k: ieee_calls[0].get(k) for k in params} == params
    first = unified_search({'limit': '2'}, ieee_search=make_fake_ieee(SAMPLE_IEEE), arxiv_catalog=arxiv)
    with pytest.raises(ValueError):
        unified_search({**params, 'limit': '2', 'cursor': first['next_cursor']}, ieee_search=make_fake_ieee(SAMPLE_IEEE), arxiv_catalog=arxiv)


def test_body_search_keeps_the_ieee_fulltext_status():
    status = {'enabled': True, 'phase': 'ready', 'documents': 2}
    def ieee(params):
        return {'items': [{'number': '101', 'title': 'IEEE A', 'year': 2026}], 'total': 1, 'total_exact': True,
                'next_cursor': None, 'fulltext': status}
    res = unified_search({'q': 'adc', 'field': 'body'}, ieee_search=ieee, arxiv_catalog=FakeArxivCatalog(SAMPLE_ARXIV))
    assert res['fulltext'] == status
    assert 'fulltext' not in unified_search({'sources': 'arxiv'}, ieee_search=ieee, arxiv_catalog=FakeArxivCatalog(SAMPLE_ARXIV))

def test_partial_failure_isolates_broken_source_and_never_fabricates_zero():
    ieee = make_fake_ieee(SAMPLE_IEEE)
    broken_arxiv = FakeArxivCatalog(SAMPLE_ARXIV, fail=True)
    res = unified_search({'q': 'amplifier'}, ieee_search=ieee, arxiv_catalog=broken_arxiv)
    assert res['partial'] is True
    assert res['total'] is None
    assert res['total_exact'] is False
    assert res['sources']['ieee']['status'] == 'ok'
    assert res['sources']['ieee']['total'] == 3
    assert res['sources']['arxiv']['status'] == 'error'
    assert res['sources']['arxiv']['total'] is None
    assert len(res['items']) == 3

    with pytest.raises(UnifiedSearchUnavailable):
        unified_search({'q': 'amplifier'}, ieee_search=make_fake_ieee([], fail=True), arxiv_catalog=broken_arxiv)


def test_invalid_inputs_and_tampered_cursor_rejected():
    ieee = make_fake_ieee(SAMPLE_IEEE)
    arxiv = FakeArxivCatalog(SAMPLE_ARXIV)
    for bad in [
        {'sources': 'pubmed'},
        {'field': 'unknown'},
        {'sort': 'random'},
        {'year_from': '2026', 'year_to': '2020'},
        {'cursor': 'not-a-valid-cursor'},
    ]:
        with pytest.raises(ValueError):
            unified_search(bad, ieee_search=ieee, arxiv_catalog=arxiv)


def test_offline_demo_unified_search_endpoint(tmp_path):
    sys.path.insert(0, str(SITE / 'tools'))
    import arxiv_demo
    db = arxiv_demo.prepare(tmp_path / 'demo.sqlite', rebuild=True)
    app = arxiv_demo.create_demo(db, state=tmp_path / 'state')
    client = TestClient(app)

    r = client.get('/api/search/unified?limit=15')
    assert r.status_code == 200
    body = r.json()
    assert body['demo'] is True
    assert body['sources']['ieee']['total'] == 3
    assert body['sources']['arxiv']['total'] == 43
    assert body['total'] == 46
    assert len(body['items']) == 15
    assert body['next_cursor']

    # Paginate through all 46 demo items without duplicates.
    seen = {(it['source'], it.get('number') or it.get('arxiv_id')) for it in body['items']}
    cursor = body['next_cursor']
    while cursor:
        nxt = client.get('/api/search/unified', params={'limit': 15, 'cursor': cursor})
        assert nxt.status_code == 200
        nb = nxt.json()
        for it in nb['items']:
            seen.add((it['source'], it.get('number') or it.get('arxiv_id')))
        cursor = nb['next_cursor']
    assert len(seen) == 46

    # Single-source and body-field guard in offline demo.
    only_ieee = client.get('/api/search/unified?sources=ieee').json()
    assert only_ieee['total'] == 3
    assert all(it['source'] == 'ieee' for it in only_ieee['items'])
    assert client.get('/api/search/unified?field=body&q=test').status_code == 409


def test_skill_manifest_checksums_match_disk():
    skill_dir = SITE / '.agents/skills/cirdc-research'
    manifest = json.loads((skill_dir / 'version.json').read_text())
    assert manifest['version'] == '1.3.0'
    for name, info in manifest['files'].items():
        raw = (skill_dir / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == info['sha256'], name
        assert len(raw) == info['bytes'], name
