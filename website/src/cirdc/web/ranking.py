"""Paper-level Top-K ranking for metadata fields, with explicit match reasons."""
import time
from contextlib import closing
from .index import filter_clauses, interpret, metadata, public_query, validate_year_range
from .query import excerpt, fts_expression, locate, phrase_expression, tokens
from .settings import connect
from .venues import parse_venue_any

FIELDS = ('title', 'keywords', 'authors', 'abstract')
WEIGHTS = {'title': 40.0, 'keywords': 20.0, 'authors': 15.0, 'abstract': 10.0}
CANDIDATES = 300
COLUMNS = ('d.id,d.number,d.doi,d.title,d.authors,d.keywords,d.abstract,d.publication,d.year,d.kind,d.venue,'
           'd.abstract_state,d.keywords_state,d.updated,d.order_number')


def explain(row, groups, query_words):
    """Which query groups matched which stored fields, using the same tokenization as FTS5."""
    reasons, matched = [], {}
    for field in FIELDS:
        terms = []
        for group in groups:
            found = locate(row[field], group['alternatives'])
            if found:
                spellings = sorted({row[field][start:end] for start, end, _ in found})
                typed = ' '.join(tokens(group['text']))
                terms.append({'query': group['text'], 'matched': spellings[:3], 'alias': any(key != typed for _, _, key in found)})
                matched.setdefault(field, []).extend(found)
        if terms:
            reasons.append({'field': field, 'terms': terms})
    title = tokens(row['title'])
    flags = {'exact_title': bool(query_words) and title == query_words,
             'title_phrase': len(query_words) >= 3 and any(title[i:i + len(query_words)] == query_words for i in range(len(title) - len(query_words) + 1)),
             'author_name': 2 <= len(query_words) <= 5 and any(tokens(name) == query_words for name in row['authors'].split(';'))}
    return reasons, flags, matched


def score(groups, reasons, flags, position):
    value = 1.0 / (1 + position)
    value += 1000 if flags['exact_title'] else 500 if flags['title_phrase'] else 0
    value += 300 if flags['author_name'] else 0
    for reason in reasons:
        value += WEIGHTS[reason['field']] * len(reason['terms']) / max(1, len(groups))
    return value


def top(params):
    years = validate_year_range(params)
    k = max(1, min(100, int(params.get('k', 20))))
    field = params.get('field', 'all')
    if field not in ('all', 'title', 'authors', 'keywords', 'abstract'):
        raise ValueError('Invalid search field')
    query = str(params.get('q') or '').strip()
    if len(query) > 200:
        raise ValueError('Search is limited to 200 characters')
    with closing(connect('search.sqlite')) as db:
        db.execute('BEGIN')
        meta = metadata(db)
        started = time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic() - started > 4), 10000)
        venue_any = parse_venue_any(params.get('venue_any'))
        understood = interpret(params, field)
        clauses, args, author_filtered, filtered = filter_clauses(db, params, years, venue_any)
        where = (' AND ' + ' AND '.join(clauses)) if clauses else ''
        groups = understood.get('groups') or []
        query_words = tokens(query) if groups else []
        candidates, order = {}, []

        def collect(sql, values):
            for row in db.execute(sql, values):
                if row['id'] not in candidates:
                    candidates[row['id']] = dict(row)
                    order.append(row['id'])

        if understood.get('number') or understood.get('doi'):
            key = 'number' if understood.get('number') else 'doi'
            collect('SELECT ' + COLUMNS + ' FROM docs d WHERE d.' + key + '=?' + where + ' LIMIT 1', (understood[key], *args))
            total = len(candidates)
        elif groups:
            expression = fts_expression(groups, None if field == 'all' else field)
            join = 'search CROSS JOIN docs d INDEXED BY docs_facets_by_id ON d.id=search.rowid'
            collect('SELECT ' + COLUMNS + ' FROM ' + join + ' WHERE search MATCH ?' + where + ' ORDER BY search.rank LIMIT ?',
                    (expression, *args, CANDIDATES))
            # Whole-title and full-name phrases can rank below long abstracts in BM25; recall them directly.
            if len(query_words) >= 3 and field in ('all', 'title'):
                collect('SELECT ' + COLUMNS + ' FROM ' + join + ' WHERE search MATCH ?' + where + ' ORDER BY search.rank LIMIT 50',
                        (phrase_expression(query_words, 'title'), *args))
            if 2 <= len(query_words) <= 5 and field in ('all', 'authors'):
                collect('SELECT ' + COLUMNS + ' FROM ' + join + ' WHERE search MATCH ?' + where + ' ORDER BY search.rank LIMIT 100',
                        (phrase_expression(query_words, 'authors'), *args))
            count = ('SELECT COUNT(*) FROM search' if not filtered else 'SELECT COUNT(*) FROM ' + join) + ' WHERE search MATCH ?' + where
            total = db.execute(count, (expression, *args)).fetchone()[0]
        else:
            # Browsing or author-identity results have no text score; keep their stable year order.
            source = 'docs d INDEXED BY docs_year' if not clauses else 'docs d'
            collect('SELECT ' + COLUMNS + ' FROM ' + source + (' WHERE ' + ' AND '.join(clauses) if clauses else '')
                    + ' ORDER BY d.year DESC,d.order_number DESC,d.number DESC LIMIT ?', (*args, k))
            total = db.execute('SELECT COUNT(*) FROM docs d' + (' WHERE ' + ' AND '.join(clauses) if clauses else ''), args).fetchone()[0]
        ranked = []
        for position, identifier in enumerate(order):
            row = candidates[identifier]
            reasons, flags, matched = explain(row, groups, query_words) if groups else ([], {'exact_title': False, 'title_phrase': False, 'author_name': False}, {})
            if understood.get('number') or understood.get('doi'):
                flags['exact_identifier'] = 'number' if understood.get('number') else 'doi'
            value = score(groups, reasons, flags, position) if groups else -position
            snippet_field = next((name for name in ('abstract', 'keywords') if matched.get(name)), None)
            item = {key: row[key] for key in ('number', 'doi', 'title', 'authors', 'publication', 'year', 'kind', 'venue',
                                               'abstract_state', 'keywords_state', 'updated', 'order_number')}
            item.update(snippet=row['abstract'][:400], rank=value, reasons=reasons, flags=flags,
                        excerpt=({'field': snippet_field, **excerpt(row[snippet_field], matched[snippet_field])} if snippet_field else None))
            ranked.append(item)
        ranked.sort(key=lambda item: -item['rank'])
        for index, item in enumerate(ranked[:k], 1):
            item['position'] = index
        return {'items': ranked[:k], 'total': total, 'view': 'top', 'k': k, 'candidates': len(order),
                'index': meta, 'query': public_query(understood), 'next_cursor': None,
                'partial': meta.get('phase') != 'ready' or bool(meta.get('error')) or
                           (author_filtered and meta.get('authors_phase') != 'ready')}
