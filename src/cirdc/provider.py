import json
import re
import time
import threading
from collections import Counter
import requests
from .model import keywords, merge, normalize


class UpstreamError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class RequestLimiter:
    """One shared start-time budget across all fetch threads in a worker."""
    def __init__(self, interval, clock=None, sleep=None):
        self.interval = interval
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.last = None
        self.lock = threading.Lock()
        self.first = None
        self.starts = 0
        self.min_spacing = None
        self.statuses = {}
        self.response_seconds = 0.0

    def wait(self):
        with self.lock:
            if self.last is not None:
                self.sleep(max(0, self.interval - (self.clock() - self.last)))
            now = self.clock()
            if self.last is not None:
                spacing = now - self.last
                self.min_spacing = spacing if self.min_spacing is None else min(self.min_spacing, spacing)
            else:
                self.first = now
            self.last = now
            self.starts += 1

    def record_status(self, status, seconds):
        with self.lock:
            key = str(status)
            self.statuses[key] = self.statuses.get(key, 0) + 1
            self.response_seconds += seconds

    def snapshot(self):
        with self.lock:
            completed = sum(self.statuses.values())
            return {'started': self.starts, 'completed': completed, 'statuses': dict(self.statuses),
                    'configured_interval_seconds': self.interval,
                    'minimum_start_spacing_seconds': self.min_spacing,
                    'mean_start_spacing_seconds': ((self.last - self.first) / (self.starts - 1)
                                                   if self.starts > 1 else None),
                    'mean_response_seconds': self.response_seconds / completed if completed else None}


class IEEE:
    BASE = 'https://ieeexplore.ieee.org'
    JSON_ACCEPT = 'application/json,text/plain,*/*'
    HTML_ACCEPT = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    SEARCH_LIMIT = 10000

    def __init__(self, config, session=None, limiter=None):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update({
            'Accept': self.JSON_ACCEPT,
            'Referer': self.BASE + '/search/searchresult.jsp',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.46',
        })
        self.last_request = 0.0
        self._document_session_ready = False
        self.limiter = limiter or RequestLimiter(config.interval)

    def request(self, method, path, payload=None, html=False):
        last = None
        for attempt in range(self.config.retries):
            self.limiter.wait()
            self.last_request = time.monotonic()
            try:
                response = self.session.request(method, self.BASE + path,
                                                data=json.dumps(payload) if payload is not None else None,
                                                headers={'Accept': self.HTML_ACCEPT if html else self.JSON_ACCEPT,
                                                         'Content-Type': 'application/json' if payload is not None else None},
                                                timeout=(self.config.connect_timeout, self.config.read_timeout))
                self.limiter.record_status(response.status_code, time.monotonic() - self.last_request)
                if response.status_code != 200:
                    code = 'access_restricted' if response.status_code in (202, 401, 403, 418, 420, 429) else 'http_error'
                    message = f'Upstream returned HTTP {response.status_code}'
                    if response.headers.get('x-amzn-waf-action') == 'challenge':
                        message += ' (AWS WAF challenge)'
                    raise UpstreamError(code, message)
                if html:
                    return response.text
                try:
                    data = response.json()
                except ValueError:
                    raise UpstreamError('parse_failed', 'Expected a JSON metadata response') from None
                if not isinstance(data, dict):
                    raise UpstreamError('parse_failed', 'Expected a metadata object')
                return data
            except requests.RequestException:
                self.limiter.record_status('network_error', time.monotonic() - self.last_request)
                last = UpstreamError('network_error', 'Metadata connection failed')
            except UpstreamError as e:
                last = e
            if attempt + 1 < self.config.retries:
                time.sleep(min(8, 2 ** attempt))
        raise last

    def search_page(self, number, year, page=1, extra=''):
        query = f'("Publication Number":{number})' + extra
        payload = {'newsearch': 'true', 'highlight': 'true', 'matchBoolean': 'true', 'matchPubs': 'true',
                   'action': 'search', 'queryText': query, 'pageNumber': str(page), 'rowsPerPage': 100}
        if year is not None:
            payload['ranges'] = [f'{year}_{year}_Year']
        return self.request('POST', '/rest/search', payload)

    def search_all(self, number, year=None, extra='', split=True, _first=None, _terms=()):
        first = _first if _first is not None else self.search_page(number, year, extra=extra)
        if any(first.get(k) for k in ('error', 'errors', 'errorCode', 'errorMessage', 'challenge', 'captcha')):
            raise UpstreamError('parse_failed', 'Search endpoint returned an error object')
        total = first.get('totalRecords')
        if isinstance(total, bool) or total is None or not str(total).isdigit():
            raise UpstreamError('parse_failed', 'Search response lacks a valid record count')
        expected = int(total)
        if expected == 0:
            if (first.get('records') not in (None, []) or isinstance(first.get('totalPages'), bool)
                    or first.get('totalPages') not in (None, 0, 1, '0', '1')):
                raise UpstreamError('coverage_incomplete', 'Zero search count conflicts with response contents')
            return []
        if not all(k in first for k in ('records', 'totalRecords', 'totalPages')):
            raise UpstreamError('parse_failed', 'Search response lacks coverage fields')
        page_count = first['totalPages']
        if isinstance(page_count, bool) or not str(page_count).isdigit() or int(page_count) < 1:
            raise UpstreamError('coverage_incomplete', 'Search response has invalid page coverage')
        pages = int(page_count)
        if not isinstance(first['records'], list) or any(not isinstance(r, dict) for r in first['records']):
            raise UpstreamError('parse_failed', 'Search response lacks a valid record list')
        if expected > self.SEARCH_LIMIT or pages > 100:
            if not split:
                raise UpstreamError('coverage_incomplete', 'A query partition exceeds the upstream result limit')
            # Discover candidate partitions, then require their totals to cover the parent query.
            rows = first['records']
            for field, label in [('volume', 'Volume'), ('issue', 'Issue')]:
                values = sorted({str(r[field]) for r in rows if r.get(field) not in (None, '')})
                if len(values) < 2:
                    continue
                combined = {}
                try:
                    for value in values:
                        safe = value.replace('"', '')
                        children = self.search_all(number, year, extra + f' AND ("{label}":"{safe}")', False)
                        for r in children:
                            combined[r['articleNumber']] = r
                except UpstreamError as error:
                    if error.code != 'coverage_incomplete':
                        raise
                    continue
                if len(combined) == expected:
                    return list(combined.values())
            # Some continuous volumes have no issue partitions. A title term
            # and its complement exhaust the parent without relying on facets
            # sampled from just the first page. Count and identity coverage are
            # both checked; unsupported or incomplete queries remain failures.
            words = Counter(word.lower() for row in rows
                            for word in re.findall(r'[A-Za-z]{3,}', str(row.get('articleTitle') or '')))
            candidates = [w for w, _ in words.most_common()
                          if w not in set(_terms) | {'the', 'and', 'for', 'with', 'from', 'using', 'that', 'into'}]
            if len(_terms) < 16:
                for term in candidates[:8]:
                    suffixes = (f' AND ("Document Title":{term})', f' AND NOT ("Document Title":{term})')
                    samples = [self.search_page(number, year, extra=extra + suffix) for suffix in suffixes]
                    totals = [self._publication_page(sample)[0] for sample in samples]
                    if sum(totals) != expected:
                        raise UpstreamError('coverage_incomplete', 'Complementary search counts do not cover the parent')
                    if not all(0 < n < expected for n in totals):
                        continue
                    combined = {}
                    for suffix, sample in zip(suffixes, samples):
                        children = self.search_all(number, year, extra + suffix,
                                                   _first=sample, _terms=(*_terms, term))
                        combined.update((r['articleNumber'], r) for r in children)
                    if len(combined) != expected:
                        raise UpstreamError('coverage_incomplete', 'Complementary search identities do not cover the parent')
                    return list(combined.values())
            raise UpstreamError('coverage_incomplete', 'Cannot prove full volume/issue partition coverage')
        collected = []
        for page in range(1, pages + 1):
            data = first if page == 1 else self.search_page(number, year, page, extra)
            if (str(data.get('totalRecords')) != str(expected) or str(data.get('totalPages')) != str(pages)
                    or not isinstance(data.get('records'), list)):
                raise UpstreamError('coverage_incomplete', 'Search coverage changed during pagination')
            collected.extend(data['records'])
        unique = {}
        for record in collected:
            # Stage 3 mirrors the legacy basic-field whitelist. Enrichment comes
            # only from the separately requested document stage.
            normalized = normalize(record, basic_only=True)
            key = normalized['articleNumber']
            unique[key] = merge(unique.get(key, {}), normalized)
        if len(unique) != expected:
            raise UpstreamError('coverage_incomplete', f'Expected {expected} distinct records, received {len(unique)}')
        return list(unique.values())

    def _document_metadata(self, article_number):
        if not str(article_number).isdigit():
            raise ValueError('articleNumber must be numeric')
        if not self._document_session_ready:
            # Establish the site's normal session before opening a document directly.
            # Requests keeps server-issued cookies in memory for this worker only.
            self.request('GET', '/search/searchresult.jsp', html=True)
            self._document_session_ready = True
        html = self.request('GET', '/document/' + str(article_number), html=True)
        match = re.search(r'xplGlobal\.document\.metadata\s*=\s*(\{)', html)
        if not match:
            raise UpstreamError('parse_failed', 'Document metadata was not present in the response')
        try:
            data, _ = json.JSONDecoder().raw_decode(html[match.start(1):])
        except ValueError:
            raise UpstreamError('parse_failed', 'Document metadata could not be decoded') from None
        if not isinstance(data, dict) or str(data.get('articleNumber', article_number)) != str(article_number):
            raise UpstreamError('parse_failed', 'Document identity did not match')
        return data

    def bibliography(self, article_number):
        """Fetch current bibliographic fields by identity, without a year constraint."""
        data = self._document_metadata(article_number)
        if str(data.get('articleNumber')) != str(article_number):
            raise UpstreamError('parse_failed', 'Document metadata did not identify the requested article')
        early = data.get('isEarlyAccess')
        if early is not None and not isinstance(early, bool) and str(early).lower() not in ('true', 'false'):
            raise UpstreamError('parse_failed', 'Document metadata had an invalid Early Access flag')
        kind = data.get('contentTypeDisplay') or data.get('articleContentType')
        if early is True or str(early).lower() == 'true' or 'early access' in str(kind).lower():
            kind = 'Early Access Articles'
        elif early is False or str(early).lower() == 'false':
            if kind not in ('Journals', 'Magazines', 'Conferences'):
                kind = ('Journals' if data.get('isJournal') is True else
                        'Conferences' if data.get('isConference') is True else kind)
        record = dict(data, articleTitle=data.get('articleTitle') or data.get('title')
                      or data.get('displayDocTitle') or data.get('formulaStrippedArticleTitle'), articleContentType=kind)
        if not isinstance(data.get('authors') or [], list):
            raise UpstreamError('parse_failed', 'Document authors were not an ordered list')
        authors = []
        for author in data.get('authors') or []:
            if isinstance(author, dict):
                authors.append({**{k: author[k] for k in ('id', 'firstName', 'lastName') if k in author},
                                'preferredName': author.get('preferredName') or author.get('name') or ''})
        record['authors'] = authors
        record = normalize(record, basic_only=True)
        from .early_access import publication_stage
        if not record.get('articleTitle') or publication_stage(record) == 'unknown':
            raise UpstreamError('parse_failed', 'Document metadata lacked bibliographic identity or publication stage')
        return record

    def document(self, article_number):
        data = self._document_metadata(article_number)
        abstract = data.get('abstract') or ''
        terms = keywords(data.get('keywords'))
        return {'articleNumber': str(article_number), 'abstract': abstract, 'keywords': terms}, {
            'abstract': 'complete' if abstract.strip() else 'no_data',
            'keywords': 'complete' if any(terms.values()) else 'no_data',
        }

    @staticmethod
    def _publication_page(data):
        if any(data.get(key) for key in ('error', 'errors', 'errorCode', 'errorMessage', 'challenge', 'captcha')):
            raise UpstreamError('parse_failed', 'Publication endpoint returned an error object')

        def count(key):
            value = data.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not str(value).isdigit():
                raise UpstreamError('parse_failed', 'Publication coverage count is not a non-negative integer')
            return int(value)

        total, pages = count('totalRecords'), count('totalPages')
        records = data.get('records')
        # The endpoint omits records for an explicitly confirmed zero-result query.
        # A missing count, HTML response, or error object is never evidence of absence.
        if total == 0:
            if records not in (None, []) or pages not in (None, 0, 1):
                raise UpstreamError('coverage_incomplete', 'Zero-result publication response is inconsistent')
            return 0, 0, []
        if total is None or pages is None or not isinstance(records, list):
            raise UpstreamError('parse_failed', 'Publication response lacks coverage fields')
        if pages == 0 or any(not isinstance(row, dict) for row in records):
            raise UpstreamError('coverage_incomplete', 'Publication response has invalid page coverage')
        return total, pages, records

    def publication_year(self, kind, year):
        if kind not in ('Journals', 'Conferences') or isinstance(year, bool) or not str(year).isdigit():
            raise ValueError('Invalid publication kind or year')
        rows = []
        page = 1
        expected = None
        expected_pages = None
        while True:
            data = self.request('POST', '/rest/publication', {
                'contentType': 'periodicals' if kind == 'Journals' else 'conferences',
                'tabId': 'title', 'ranges': [f'{year}_{year}_Year'], 'pageNumber': page,
            })
            total, pages, records = self._publication_page(data)
            expected = total if expected is None else expected
            expected_pages = pages if expected_pages is None else expected_pages
            if total != expected or pages != expected_pages:
                raise UpstreamError('coverage_incomplete', 'Publication counts changed during pagination')
            rows.extend(records)
            if page >= expected_pages:
                break
            page += 1
        if len(rows) != expected:
            raise UpstreamError('coverage_incomplete', 'Publication index is incomplete')
        field = 'publicationNumber' if kind == 'Journals' else 'parentPublicationNumber'
        identifiers = [str(row.get(field) or '') for row in rows]
        if any(not number for number in identifiers):
            raise UpstreamError('parse_failed', 'Publication records lack their catalog identity')
        if len(set(identifiers)) != expected:
            raise UpstreamError('coverage_incomplete', 'Publication pagination repeats catalog identities')
        return rows

    def relationships(self, article_number, direction):
        if direction not in ('references', 'citations') or not str(article_number).isdigit():
            raise ValueError('Invalid relationship request')
        data = self.request('GET', f'/rest/document/{article_number}/{direction}?start=1&count=300')
        if direction == 'references':
            rows = data.get('references')
        else:
            count = int(data.get('ieeeCitationCount', 0))
            data = self.request('GET', f'/rest/document/{article_number}/citations?start=1&count={count}&type=ieee')
            rows = data.get('paperCitations', {}).get('ieee', [])
        if not isinstance(rows, list):
            raise UpstreamError('parse_failed', 'Relationship response lacks its record list')
        return rows
