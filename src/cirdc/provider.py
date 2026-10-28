import json
import re
import time
import requests
from .model import keywords, merge, normalize


class UpstreamError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class IEEE:
    BASE = 'https://ieeexplore.ieee.org'

    def __init__(self, config, session=None):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update({
            'Accept': 'application/json,text/plain,*/*', 'Content-Type': 'application/json',
            'Referer': self.BASE + '/search/searchresult.jsp',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.46',
        })
        self.last_request = 0.0

    def request(self, method, path, payload=None, html=False):
        last = None
        for attempt in range(self.config.retries):
            time.sleep(max(0, self.config.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.session.request(method, self.BASE + path,
                                                data=json.dumps(payload) if payload is not None else None,
                                                timeout=(self.config.connect_timeout, self.config.read_timeout))
                if response.status_code != 200:
                    code = 'access_restricted' if response.status_code in (202, 401, 403, 418, 429) else 'http_error'
                    raise UpstreamError(code, f'Upstream returned HTTP {response.status_code}')
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

    def search_all(self, number, year=None, extra='', split=True):
        first = self.search_page(number, year, extra=extra)
        if not all(k in first for k in ('records', 'totalRecords', 'totalPages')):
            raise UpstreamError('parse_failed', 'Search response lacks coverage fields')
        expected = int(first['totalRecords'])
        pages = int(first['totalPages'])
        if expected == 0:
            return []
        if expected > 10000 or pages > 100:
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
            raise UpstreamError('coverage_incomplete', 'Cannot prove full volume/issue partition coverage')
        collected = []
        for page in range(1, pages + 1):
            data = first if page == 1 else self.search_page(number, year, page, extra)
            if int(data.get('totalRecords', -1)) != expected or not isinstance(data.get('records'), list):
                raise UpstreamError('coverage_incomplete', 'Search coverage changed during pagination')
            collected.extend(data['records'])
        unique = {}
        for record in collected:
            normalized = normalize(record)
            key = normalized['articleNumber']
            unique[key] = merge(unique.get(key, {}), normalized)
        if len(unique) != expected:
            raise UpstreamError('coverage_incomplete', f'Expected {expected} distinct records, received {len(unique)}')
        return list(unique.values())

    def document(self, article_number):
        if not str(article_number).isdigit():
            raise ValueError('articleNumber must be numeric')
        html = self.request('GET', '/document/' + str(article_number), html=True)
        match = re.search(r'xplGlobal\.document\.metadata\s*=\s*(\{)', html)
        if not match:
            raise UpstreamError('parse_failed', 'Document metadata was not present in the response')
        try:
            data, _ = json.JSONDecoder().raw_decode(html[match.start(1):])
        except ValueError:
            raise UpstreamError('parse_failed', 'Document metadata could not be decoded') from None
        if str(data.get('articleNumber', article_number)) != str(article_number):
            raise UpstreamError('parse_failed', 'Document identity did not match')
        abstract = data.get('abstract') or ''
        terms = keywords(data.get('keywords'))
        return {'articleNumber': str(article_number), 'abstract': abstract, 'keywords': terms}, {
            'abstract': 'complete' if abstract.strip() else 'no_data',
            'keywords': 'complete' if any(terms.values()) else 'no_data',
        }

    def publication_year(self, kind, year):
        rows = []
        page = 1
        expected = None
        while True:
            data = self.request('POST', '/rest/publication', {
                'contentType': 'periodicals' if kind == 'Journals' else 'conferences',
                'tabId': 'title', 'ranges': [f'{year}_{year}_Year'], 'pageNumber': page,
            })
            if not all(k in data for k in ('records', 'totalRecords', 'totalPages')):
                raise UpstreamError('parse_failed', 'Publication response lacks coverage fields')
            expected = int(data['totalRecords']) if expected is None else expected
            if int(data['totalRecords']) != expected:
                raise UpstreamError('coverage_incomplete', 'Publication counts changed during pagination')
            rows.extend(data['records'])
            if page >= int(data['totalPages']):
                break
            page += 1
        if len(rows) != expected:
            raise UpstreamError('coverage_incomplete', 'Publication index is incomplete')
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
