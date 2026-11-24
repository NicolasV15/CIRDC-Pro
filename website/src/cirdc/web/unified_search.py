"""Unified IEEE + arXiv search with deterministic RRF/chronological merging."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from typing import Any, Callable

VALID_SOURCES = ('ieee', 'arxiv')
VALID_FIELDS = ('all', 'title', 'authors', 'abstract', 'keywords', 'body', 'categories')
IEEE_FIELDS = {'all', 'title', 'authors', 'abstract', 'keywords', 'body'}
ARXIV_FIELDS = {'all', 'title', 'authors', 'abstract', 'categories'}
VALID_SORTS = ('relevance', 'year')
VALID_VIEWS = ('', 'all', 'top')
VALID_TERMS = ('', 'expand', 'exact')
VALID_TOTALS = ('', 'include', 'defer', 'only')
VALID_TOP_K = {10, 20, 50, 100}
IEEE_FILTER_KEYS = ('venue', 'venue_any', 'venue_tags', 'kind', 'publication', 'author_id', 'author_source')
RRF_K = 60


class UnifiedSearchUnavailable(RuntimeError):
    """Raised when every active search source fails to answer."""


def parse_sources(raw: str | None) -> list[str]:
    if raw is None or not str(raw).strip():
        return ['ieee', 'arxiv']
    parts = [part.strip().lower() for part in str(raw).split(',') if part.strip()]
    if not parts:
        raise ValueError('sources_required')
    selected: list[str] = []
    for part in parts:
        if part not in VALID_SOURCES:
            raise ValueError('invalid_source')
        if part not in selected:
            selected.append(part)
    return selected


def _encode_cursor(payload: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode('utf-8')).decode('ascii')


def _decode_cursor(token: str, expected_fingerprint: str) -> dict[str, Any]:
    if not token or len(token) > 4096:
        raise ValueError('invalid_cursor')
    try:
        padded = token + '=' * (-len(token) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        raise ValueError('invalid_cursor') from None
    if not isinstance(data, dict) or data.get('q') != expected_fingerprint:
        raise ValueError('invalid_cursor')
    return data


def _fingerprint(params: dict[str, Any], selected_sources: list[str], field: str, sort: str, view: str, top_k: int) -> str:
    key = {
        'sources': selected_sources,
        'q': str(params.get('q') or '').strip(),
        'field': field,
        'sort': sort,
        'view': view,
        'k': top_k if view == 'top' else None,
        'terms': str(params.get('terms') or 'expand'),
        'year_from': str(params.get('year_from') or ''),
        'year_to': str(params.get('year_to') or ''),
        'category': str(params.get('category') or ''),
        'include_dates': str(params.get('include_dates', '1')),
        **{name: str(params.get(name) or '') for name in IEEE_FILTER_KEYS},
    }
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode('utf-8')).hexdigest()[:24]


def _item_year(item: dict[str, Any]) -> int:
    value = item.get('year')
    try:
        return int(value) if value is not None and str(value).strip() != '' else 0
    except (TypeError, ValueError):
        return 0


def _chronological_key(source: str, item: dict[str, Any]) -> tuple[int, str, int, str]:
    year = _item_year(item)
    if source == 'arxiv':
        submitted = str(item.get('submitted_at') or '')
        date_key = submitted[:10] if len(submitted) >= 10 else f'{year:04d}-00-00'
        tie_id = str(item.get('arxiv_id') or item.get('paper_id') or '')
        source_tie = 0
    else:
        # IEEE records have publication year and order_number; keep deterministic order within a year.
        order_num = str(item.get('order_number') or '')
        date_key = f'{year:04d}-00-00'
        tie_id = order_num or str(item.get('number') or '')
        source_tie = 1
    return (year, date_key, source_tie, tie_id)


def _fetch_ieee_window(
    ieee_search: Callable[[dict[str, Any]], dict[str, Any]],
    base_params: dict[str, Any],
    cursor: str | None,
    skip: int,
    need: int,
    totals_mode: str,
) -> dict[str, Any]:
    """Fetch up to `need` unconsumed IEEE items starting at `(cursor, skip)`."""
    page_limit = max(need, min(100, need + skip))
    first_params = {**base_params, 'limit': str(page_limit), 'totals': totals_mode}
    if cursor:
        first_params['cursor'] = cursor
    first = ieee_search(first_params)
    first_items = list(first.get('items') or [])
    if skip > len(first_items):
        raise ValueError('invalid_cursor')
    unconsumed = first_items[skip:]
    # Track exact page boundaries so cursor advancement never duplicates or skips.
    entries: list[tuple[dict[str, Any], str | None, int, bool]] = []
    for idx, item in enumerate(unconsumed[:need]):
        pos_in_page = skip + idx + 1
        if pos_in_page < len(first_items):
            entries.append((item, cursor, pos_in_page, False))
        else:
            nxt = first.get('next_cursor')
            entries.append((item, nxt, 0, nxt is None))

    second_cursor = first.get('next_cursor')
    has_more_after_first = len(unconsumed) > need or second_cursor is not None
    if len(entries) < need and second_cursor and totals_mode != 'only':
        remaining = need - len(entries)
        second_params = {**base_params, 'limit': str(max(remaining, need)), 'totals': 'defer', 'cursor': second_cursor}
        second = ieee_search(second_params)
        second_items = list(second.get('items') or [])
        for idx, item in enumerate(second_items[:remaining]):
            pos_in_page = idx + 1
            if pos_in_page < len(second_items):
                entries.append((item, second_cursor, pos_in_page, False))
            else:
                nxt = second.get('next_cursor')
                entries.append((item, nxt, 0, nxt is None))
        has_more_after_second = len(second_items) > remaining or second.get('next_cursor') is not None
    else:
        has_more_after_second = has_more_after_first

    return {
        'entries': entries,
        'total': first.get('total'),
        'total_exact': first.get('total_exact', first.get('total') is not None),
        'has_more': has_more_after_second if len(entries) == need else False,
        'query': first.get('query'),
    }


def _fetch_arxiv_window(
    arxiv_catalog: Any,
    query: str,
    field: str,
    sort: str,
    view: str,
    top_k: int,
    terms: str,
    category: str,
    year_from: str,
    year_to: str,
    totals_mode: str,
    include_dates: bool,
    offset: int,
    need: int,
) -> dict[str, Any]:
    arxiv_totals = 'only' if totals_mode == 'only' else 'defer' if totals_mode == 'defer' else ''
    arxiv_view = 'top' if view == 'top' else ''
    cursor = None
    if offset > 0:
        # Build a valid arXiv offset cursor via the catalog's own search signature.
        probe = arxiv_catalog.search(
            query,
            limit=1,
            cursor=None,
            field=field,
            sort=sort,
            view='',
            k=str(top_k),
            terms=terms or 'expand',
            category=category,
            year_from=year_from,
            year_to=year_to,
            totals='defer',
        )
        if probe.get('next_cursor'):
            raw = json.loads(base64.urlsafe_b64decode(probe['next_cursor'] + '===').decode('utf-8'))
            raw['offset'] = offset
            cursor = base64.urlsafe_b64encode(json.dumps(raw).encode('utf-8')).decode('ascii')
        else:
            return {'entries': [], 'total': 0 if arxiv_totals != 'defer' else None, 'total_exact': True, 'has_more': False}

    result = arxiv_catalog.search(
        query,
        limit=need,
        cursor=cursor,
        field=field,
        sort=sort,
        view=arxiv_view,
        k=str(top_k),
        terms=terms or 'expand',
        category=category,
        year_from=year_from,
        year_to=year_to,
        totals=arxiv_totals,
    )
    items = list(result.get('items') or [])
    if include_dates and items and hasattr(arxiv_catalog, 'with_submission_dates'):
        items = list(arxiv_catalog.with_submission_dates(items))
    entries = [(item, offset + idx + 1) for idx, item in enumerate(items[:need])]
    return {
        'entries': entries,
        'total': result.get('total'),
        'total_exact': bool(result.get('total_exact', result.get('total') is not None)),
        'has_more': result.get('next_cursor') is not None,
        'query': result.get('query'),
    }


def unified_search(
    params: dict[str, Any],
    *,
    ieee_search: Callable[[dict[str, Any]], dict[str, Any]],
    arxiv_catalog: Any | None,
) -> dict[str, Any]:
    """Execute a unified search across selected IEEE and arXiv sources."""
    selected = parse_sources(params.get('sources'))
    query = str(params.get('q') or '').strip()
    field = str(params.get('field') or 'all').strip().lower()
    if field not in VALID_FIELDS:
        raise ValueError('invalid_field')
    max_len = 600 if field == 'body' else 200
    if len(query) > max_len:
        raise ValueError('query_too_long')

    view = str(params.get('view') or 'all').strip().lower()
    if view not in VALID_VIEWS:
        raise ValueError('invalid_view')
    normalized_view = 'top' if view == 'top' else 'all'

    raw_k = str(params.get('k') or '20').strip()
    try:
        top_k = int(raw_k)
    except ValueError:
        raise ValueError('invalid_top_k') from None
    if top_k not in VALID_TOP_K:
        raise ValueError('invalid_top_k')

    raw_sort = str(params.get('sort') or '').strip().lower()
    if raw_sort and raw_sort not in VALID_SORTS:
        raise ValueError('invalid_sort')
    sort = raw_sort or ('relevance' if query else 'year')
    if normalized_view == 'top':
        sort = 'relevance'

    terms = str(params.get('terms') or 'expand').strip().lower()
    if terms not in VALID_TERMS:
        raise ValueError('invalid_terms')

    totals_mode = str(params.get('totals') or 'include').strip().lower()
    if totals_mode not in VALID_TOTALS:
        raise ValueError('invalid_totals')
    if totals_mode == '':
        totals_mode = 'include'

    include_dates_raw = str(params.get('include_dates', '1')).strip()
    if include_dates_raw not in ('0', '1'):
        raise ValueError('invalid_include_dates')
    include_dates = include_dates_raw == '1'

    try:
        limit = int(params.get('limit', 25))
    except (TypeError, ValueError):
        raise ValueError('invalid_limit') from None
    if not 1 <= limit <= 100:
        raise ValueError('invalid_limit')
    if normalized_view == 'top':
        limit = top_k

    year_from = str(params.get('year_from') or '').strip()
    year_to = str(params.get('year_to') or '').strip()
    low = int(year_from) if year_from else None
    high = int(year_to) if year_to else None
    if any(v is not None and not 1800 <= v <= 2200 for v in (low, high)):
        raise ValueError('invalid_year_range')
    if low is not None and high is not None and low > high:
        raise ValueError('invalid_year_range')

    category = str(params.get('category') or '').strip()
    fingerprint = _fingerprint(params, selected, field, sort, normalized_view, top_k)

    cursor_state: dict[str, Any] = {
        'ieee_cursor': None,
        'ieee_skip': 0,
        'ieee_consumed': 0,
        'ieee_done': False,
        'arxiv_offset': 0,
        'arxiv_consumed': 0,
        'arxiv_done': False,
    }
    raw_cursor = params.get('cursor')
    if raw_cursor:
        decoded = _decode_cursor(str(raw_cursor), fingerprint)
        cursor_state.update({
            'ieee_cursor': decoded.get('ic'),
            'ieee_skip': int(decoded.get('is', 0)),
            'ieee_consumed': int(decoded.get('in', 0)),
            'ieee_done': bool(decoded.get('id', False)),
            'arxiv_offset': int(decoded.get('ao', 0)),
            'arxiv_consumed': int(decoded.get('an', 0)),
            'arxiv_done': bool(decoded.get('ad', False)),
        })
        if cursor_state['ieee_skip'] < 0 or cursor_state['arxiv_offset'] < 0:
            raise ValueError('invalid_cursor')

    source_notes: list[dict[str, str]] = []
    sources_info: dict[str, dict[str, Any]] = {
        'ieee': {'enabled': True, 'selected': 'ieee' in selected, 'status': 'not_selected', 'total': None, 'total_exact': False},
        'arxiv': {'enabled': arxiv_catalog is not None, 'selected': 'arxiv' in selected, 'status': 'not_selected', 'total': None, 'total_exact': False},
    }

    run_ieee = 'ieee' in selected
    run_arxiv = 'arxiv' in selected

    if run_ieee and field not in IEEE_FIELDS:
        run_ieee = False
        sources_info['ieee']['status'] = 'skipped_field'
        source_notes.append({'source': 'ieee', 'code': 'field_not_supported', 'field': field})

    if run_arxiv and arxiv_catalog is None:
        run_arxiv = False
        sources_info['arxiv']['status'] = 'unconfigured'
        source_notes.append({'source': 'arxiv', 'code': 'source_unconfigured'})
    elif run_arxiv and field not in ARXIV_FIELDS:
        run_arxiv = False
        sources_info['arxiv']['status'] = 'skipped_field'
        source_notes.append({'source': 'arxiv', 'code': 'field_not_supported', 'field': field})

    ieee_window: dict[str, Any] | None = None
    arxiv_window: dict[str, Any] | None = None
    errors: dict[str, str] = {}
    attempted = 0

    if run_ieee:
        if cursor_state['ieee_done'] and totals_mode != 'only':
            done_total = None if totals_mode == 'defer' else cursor_state['ieee_consumed']
            ieee_window = {'entries': [], 'total': done_total, 'total_exact': done_total is not None, 'has_more': False}
            sources_info['ieee'].update({'status': 'ok', 'total': done_total, 'total_exact': done_total is not None})
        else:
            attempted += 1
            ieee_params: dict[str, Any] = {
                'q': query,
                'field': field,
                'sort': sort,
                'view': normalized_view,
                'k': str(top_k),
                'terms': terms or 'expand',
                'year_from': year_from,
                'year_to': year_to,
            }
            for key in IEEE_FILTER_KEYS:
                if params.get(key):
                    ieee_params[key] = str(params[key])
            try:
                ieee_window = _fetch_ieee_window(
                    ieee_search,
                    ieee_params,
                    cursor_state['ieee_cursor'],
                    cursor_state['ieee_skip'],
                    limit,
                    totals_mode,
                )
                sources_info['ieee'].update({
                    'status': 'ok',
                    'total': ieee_window['total'],
                    'total_exact': bool(ieee_window['total_exact']),
                })
            except ValueError:
                raise
            except (sqlite3.Error, OSError, RuntimeError):
                errors['ieee'] = 'search_busy'
                sources_info['ieee'].update({'status': 'error', 'error': 'search_busy', 'total': None, 'total_exact': False})

    if run_arxiv:
        if cursor_state['arxiv_done'] and totals_mode != 'only':
            done_total = None if totals_mode == 'defer' else cursor_state['arxiv_consumed']
            arxiv_window = {'entries': [], 'total': done_total, 'total_exact': done_total is not None, 'has_more': False}
            sources_info['arxiv'].update({'status': 'ok', 'total': done_total, 'total_exact': done_total is not None})
        else:
            attempted += 1
            arxiv_low = str(max(low, 1991)) if low is not None else ''
            arxiv_high = str(high) if high is not None else ''
            if high is not None and high < 1991:
                arxiv_window = {'entries': [], 'total': 0 if totals_mode != 'defer' else None, 'total_exact': True, 'has_more': False}
                sources_info['arxiv'].update({'status': 'ok', 'total': arxiv_window['total'], 'total_exact': True})
            else:
                try:
                    arxiv_window = _fetch_arxiv_window(
                        arxiv_catalog,
                        query=query,
                        field=field,
                        sort=sort,
                        view=normalized_view,
                        top_k=top_k,
                        terms=terms,
                        category=category,
                        year_from=arxiv_low,
                        year_to=arxiv_high,
                        totals_mode=totals_mode,
                        include_dates=include_dates,
                        offset=cursor_state['arxiv_offset'],
                        need=limit,
                    )
                    sources_info['arxiv'].update({
                        'status': 'ok',
                        'total': arxiv_window['total'],
                        'total_exact': bool(arxiv_window['total_exact']),
                    })
                except ValueError:
                    raise
                except (sqlite3.Error, OSError, RuntimeError):
                    errors['arxiv'] = 'search_busy'
                    sources_info['arxiv'].update({'status': 'error', 'error': 'search_busy', 'total': None, 'total_exact': False})

    if attempted > 0 and len(errors) == attempted:
        raise UnifiedSearchUnavailable('all_sources_unavailable')

    ieee_entries = ieee_window['entries'] if ieee_window else []
    arxiv_entries = arxiv_window['entries'] if arxiv_window else []

    merged_items: list[dict[str, Any]] = []
    i_idx = 0
    a_idx = 0
    next_ieee_cursor = cursor_state['ieee_cursor']
    next_ieee_skip = cursor_state['ieee_skip']
    next_ieee_done = cursor_state['ieee_done'] or (ieee_window is None)
    next_arxiv_offset = cursor_state['arxiv_offset']
    next_arxiv_done = cursor_state['arxiv_done'] or (arxiv_window is None)

    use_rrf = sort == 'relevance' and bool(query)

    if totals_mode != 'only':
        while len(merged_items) < limit and (i_idx < len(ieee_entries) or a_idx < len(arxiv_entries)):
            choose_ieee = False
            if i_idx < len(ieee_entries) and a_idx >= len(arxiv_entries):
                choose_ieee = True
            elif a_idx < len(arxiv_entries) and i_idx >= len(ieee_entries):
                choose_ieee = False
            else:
                ieee_item = ieee_entries[i_idx][0]
                arxiv_item = arxiv_entries[a_idx][0]
                if use_rrf:
                    ieee_rank = cursor_state['ieee_consumed'] + i_idx + 1
                    arxiv_rank = cursor_state['arxiv_consumed'] + a_idx + 1
                    ieee_score = 1.0 / (RRF_K + ieee_rank)
                    arxiv_score = 1.0 / (RRF_K + arxiv_rank)
                    if ieee_score != arxiv_score:
                        choose_ieee = ieee_score > arxiv_score
                    else:
                        choose_ieee = (_item_year(ieee_item), 1) >= (_item_year(arxiv_item), 0)
                else:
                    choose_ieee = _chronological_key('ieee', ieee_item) >= _chronological_key('arxiv', arxiv_item)

            if choose_ieee:
                raw_item, next_ieee_cursor, next_ieee_skip, next_ieee_done = ieee_entries[i_idx]
                item = {**raw_item, 'source': 'ieee'}
                if use_rrf:
                    item['rrf_rank'] = cursor_state['ieee_consumed'] + i_idx + 1
                merged_items.append(item)
                i_idx += 1
            else:
                raw_item, next_arxiv_offset = arxiv_entries[a_idx]
                item = {**raw_item, 'source': 'arxiv'}
                if use_rrf:
                    item['rrf_rank'] = cursor_state['arxiv_consumed'] + a_idx + 1
                merged_items.append(item)
                a_idx += 1

    if ieee_window is not None:
        if i_idx == len(ieee_entries) and not ieee_window['has_more']:
            next_ieee_done = True
        elif i_idx < len(ieee_entries):
            next_ieee_done = False

    if arxiv_window is not None:
        if a_idx == len(arxiv_entries) and not arxiv_window['has_more']:
            next_arxiv_done = True
        elif a_idx < len(arxiv_entries):
            next_arxiv_done = False

    has_more = normalized_view != 'top' and totals_mode != 'only' and (
        (run_ieee and 'ieee' not in errors and not next_ieee_done)
        or (run_arxiv and 'arxiv' not in errors and not next_arxiv_done)
    )

    next_cursor = None
    if has_more:
        next_cursor = _encode_cursor({
            'q': fingerprint,
            'ic': next_ieee_cursor,
            'is': next_ieee_skip,
            'in': cursor_state['ieee_consumed'] + i_idx,
            'id': next_ieee_done,
            'ao': next_arxiv_offset,
            'an': cursor_state['arxiv_consumed'] + a_idx,
            'ad': next_arxiv_done,
        })

    active_ok_totals = [
        info['total']
        for name, info in sources_info.items()
        if info['status'] == 'ok'
    ]
    partial = bool(errors)
    if partial or totals_mode == 'defer' or any(t is None for t in active_ok_totals):
        combined_total = None
        total_exact = False
    else:
        combined_total = sum(int(t) for t in active_ok_totals)
        total_exact = all(info['total_exact'] for info in sources_info.values() if info['status'] == 'ok')

    explanation = (ieee_window or {}).get('query') or (arxiv_window or {}).get('query')

    return {
        'items': merged_items,
        'total': combined_total,
        'total_exact': total_exact,
        'partial': partial,
        'next_cursor': next_cursor,
        'sort': sort,
        'field': field,
        'view': normalized_view,
        'selected_sources': selected,
        'sources': sources_info,
        'source_notes': source_notes,
        **({'query': explanation} if explanation else {}),
    }
