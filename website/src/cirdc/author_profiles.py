"""Single-author acquisition and portable, sanitized snapshots; no batch traversal."""
import fcntl
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

import requests

BASE = 'https://ieeexplore.ieee.org'
PARSER_VERSION = '1.0'
MAX_BYTES = 4 * 1024 * 1024
FIELD_MAP = {
    'preferred_name': 'preferredName', 'first_name': 'firstName', 'last_name': 'lastName',
    'orcid': 'orcid', 'current_affiliations': 'currentAffiliations', 'bio_paragraphs': 'bioParagraphs',
    'coauthors': 'coAuthors', 'topics': 'topics', 'publication_years': 'publicationYears',
    'ieee_article_count': 'articleCount', 'ieee_citation_count': 'citations',
    'first_published_year': 'firstPublishedYear', 'last_published_year': 'lastPublishedYear',
    'is_hidden': 'isHideProfile',
}
ARRAYS = {'current_affiliations', 'bio_paragraphs', 'coauthors', 'topics', 'publication_years'}
NUMBERS = {'ieee_article_count', 'ieee_citation_count', 'first_published_year', 'last_published_year'}


class AuthorError(RuntimeError):
    def __init__(self, code, http_status=None):
        self.code, self.http_status = code, http_status
        super().__init__(code)  # Never retain upstream bodies, URLs, cookies or SQL errors.


def identity(author_id, source='ieee'):
    if source != 'ieee' or not isinstance(author_id, str) or not re.fullmatch(r'[0-9]{1,64}', author_id):
        raise AuthorError('invalid_author_reference')
    return source, author_id


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe', 'object', 'svg'):
            self.hidden += 1
        if not self.hidden and tag in ('br', 'p', 'div'):
            self.out.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'iframe', 'object', 'svg'):
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in ('p', 'div'):
            self.out.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.out.append(data)


def text(value, limit=100000):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise AuthorError('invalid_profile_field')
    parser = _Text()
    parser.feed(value)
    out = ''.join(parser.out)
    # Image elements/attributes are discarded above; also remove visible image URLs.
    out = re.sub(r'https?://[^\s<>]+', lambda m: '' if re.search(
        r'photo|avatar|portrait|/images?/|\.(?:png|jpe?g|gif|webp|svg)(?:[?#]|$)', m[0], re.IGNORECASE) else m[0], out)
    return '\n'.join(line.strip() for line in out.splitlines()).strip() or None


def number(value, year=False):
    if value in (None, ''):
        return None
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,20}', str(value)):
        raise AuthorError('invalid_profile_field')
    value = int(value)
    if value > (65535 if year else 2**64 - 1):
        raise AuthorError('invalid_profile_field')
    return value


def _array(value, field):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 10000:
        raise AuthorError('invalid_profile_field')
    out = []
    for item in value:
        if field in ('current_affiliations', 'bio_paragraphs'):
            cleaned = text(item)
            if cleaned:
                out.append(cleaned)
        elif not isinstance(item, dict):
            raise AuthorError('invalid_profile_field')
        elif field == 'coauthors':
            aid = item.get('author_id', item.get('idStr', item.get('id')))
            if aid is not None:
                if isinstance(aid, bool):
                    raise AuthorError('invalid_profile_field')
                aid = identity(str(aid))[1]
            hidden = item.get('is_hidden', item.get('isHideProfile'))
            if hidden is not None and not isinstance(hidden, bool):
                raise AuthorError('invalid_profile_field')
            out.append({'author_id': aid,
                        'preferred_name': text(item.get('preferred_name', item.get('preferredName')), 512),
                        'first_name': text(item.get('first_name', item.get('firstName')), 512),
                        'last_name': text(item.get('last_name', item.get('lastName')), 512),
                        'is_hidden': hidden})
        else:
            row = {'name': text(item.get('name'), 512), 'num_records': number(item.get('num_records', item.get('numRecords')))}
            if field == 'publication_years':
                row['id'] = text(item.get('id'), 128)
            out.append(row)
    return out


def normalize(data, canonical=False):
    if not isinstance(data, dict):
        raise AuthorError('invalid_profile')
    profile, states = {}, {}
    for name, upstream in FIELD_MAP.items():
        key = name if canonical else upstream
        value = data.get(key)
        if name in ARRAYS:
            cleaned = _array(value, name)
        elif name in NUMBERS:
            cleaned = number(value, name.endswith('_year'))
        elif name == 'is_hidden':
            if value is not None and not isinstance(value, bool):
                raise AuthorError('invalid_profile_field')
            cleaned = value
        else:
            cleaned = text(value, 64 if name == 'orcid' else 512)
        profile[name] = cleaned
        states[name] = ('not_returned' if key not in data else 'no_data' if cleaned in (None, '', []) else 'complete')
    return profile, states


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def timestamp(value=None):
    try:
        parsed = datetime.now(timezone.utc) if value is None else datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        if parsed.timestamp() > time.time() + 300:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, AttributeError):
        raise AuthorError('invalid_fetch_time') from None


def envelope(data, author_id):
    identity(author_id)
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise AuthorError('unexpected_author_response')
    raw = data[0]
    returned = raw.get('idStr', raw.get('id'))
    if isinstance(returned, bool) or str(returned) != author_id:
        raise AuthorError('author_identity_mismatch')
    profile, states = normalize(raw)
    # A non-hidden identity-only object is not a complete profile response.
    if not profile['is_hidden'] and not profile['preferred_name']:
        raise AuthorError('unexpected_author_response')
    return {'author_schema_version': 1, 'parser_version': PARSER_VERSION, 'source': 'ieee',
            'author_id': author_id, 'fetched_at': timestamp(), 'profile': profile,
            'field_states': states, 'payload_sha256': sha256(encoded(profile)).hexdigest()}


def validate(value):
    if not isinstance(value, dict) or value.get('author_schema_version') != 1 or value.get('parser_version') != PARSER_VERSION:
        raise AuthorError('unsupported_author_snapshot')
    if not isinstance(value.get('fetched_at'), str):
        raise AuthorError('invalid_fetch_time')
    source, aid = identity(value.get('author_id'), value.get('source'))
    profile, states = normalize(value.get('profile'), canonical=True)
    original = value.get('field_states')
    if not isinstance(original, dict) or set(original) != set(states):
        raise AuthorError('invalid_field_states')
    for field, state in original.items():
        if state not in ('complete', 'no_data', 'not_returned'):
            raise AuthorError('invalid_field_states')
        if (state == 'complete') != (states[field] == 'complete'):
            raise AuthorError('invalid_field_states')
        states[field] = state
    digest = sha256(encoded(profile)).hexdigest()
    if digest != value.get('payload_sha256'):
        raise AuthorError('snapshot_digest_mismatch')
    if not profile['is_hidden'] and not profile['preferred_name']:
        raise AuthorError('unexpected_author_response')
    return {'author_schema_version': 1, 'parser_version': PARSER_VERSION, 'source': source,
            'author_id': aid, 'fetched_at': timestamp(value.get('fetched_at')), 'profile': profile,
            'field_states': states, 'payload_sha256': digest}


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_snapshot(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise AuthorError('snapshot_too_large')
    try:
        return validate(json.loads(raw))
    except (ValueError, UnicodeError):
        raise AuthorError('invalid_snapshot_json') from None


class AuthorClient:
    def __init__(self, config, session=None):
        self.config = config
        self.session = session or requests.Session()
        from .provider import IEEE
        # A fresh normal session; never import browser credentials.
        self.session.headers.update({'Referer': BASE + '/search/searchresult.jsp', 'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.46'})
        self.session.headers.pop('Content-Type', None)
        self.base = IEEE.BASE

    def request(self, path, html, clock):
        error = AuthorError('network_error')
        for attempt in range(min(3, max(1, self.config.retries))):
            clock.seek(0)
            try:
                last = float(clock.read() or '0')
            except ValueError:
                last = 0
            time.sleep(max(0, max(1, self.config.interval) - (time.time() - last)))
            clock.seek(0); clock.truncate(); clock.write(str(time.time())); clock.flush()
            try:
                with self.session.get(self.base + path, headers={'Accept': 'text/html' if html else
                        'application/json, text/plain, */*'}, timeout=(5, 30), stream=True, allow_redirects=False) as reply:
                    status = reply.status_code
                    if status in (202, 401, 403, 418, 429):
                        raise AuthorError('access_restricted', status)
                    if 500 <= status < 600:
                        error = AuthorError('upstream_unavailable', status)
                    elif status != 200:
                        raise AuthorError('unexpected_http_status', status)
                    else:
                        raw = bytearray()
                        for chunk in reply.iter_content(65536):
                            raw.extend(chunk)
                            if len(raw) > MAX_BYTES:
                                raise AuthorError('response_too_large', status)
                        if html:
                            if b'<html' not in raw.lower() and b'<!doctype html' not in raw.lower():
                                raise AuthorError('unexpected_entry_response', status)
                            return None
                        if 'json' not in reply.headers.get('Content-Type', '').lower():
                            raise AuthorError('unexpected_content_type', status)
                        try:
                            return json.loads(raw)
                        except (ValueError, UnicodeError):
                            raise AuthorError('parse_failed', status) from None
            except requests.RequestException:
                error = AuthorError('network_error')
            if attempt + 1 < min(3, max(1, self.config.retries)):
                time.sleep(2**attempt)
        raise error

    def fetch(self, author_id):
        identity(author_id)
        root = self.config.state_dir / 'authors'
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Serializes single-author HTTP across local agents and preserves spacing across processes.
        fd = os.open(root / 'requests.lock', os.O_CREAT | os.O_RDWR, 0o600)
        try:
            with os.fdopen(fd, 'r+') as clock:
                try:
                    fcntl.flock(clock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise AuthorError('author_fetch_busy') from None
                self.request('/search/searchresult.jsp', True, clock)
                value = self.request('/rest/author/' + author_id, False, clock)
                return envelope(value, author_id)
        finally:
            self.session.close()


@contextmanager
def author_lock(store, key):
    database = store.execute('SELECT DATABASE() AS name')[0]['name']
    name = 'cirdc-author:' + sha256((database + ':' + key).encode()).hexdigest()[:48]
    if store.execute('SELECT GET_LOCK(%s,0) AS acquired', (name,))[0]['acquired'] != 1:
        raise AuthorError('author_write_busy')
    try:
        yield
    finally:
        store.execute('SELECT RELEASE_LOCK(%s)', (name,))


class AuthorRepository:
    def __init__(self, store, state_dir):
        self.store, self.state_dir = store, Path(state_dir)
        # DATETIME defaults use the connection timezone, independently of source timestamps.
        self.store.execute('SET SESSION time_zone=%s', ('+00:00',))

    def ready(self):
        from .author_schema import check, core_ready
        core_ready(self.store)
        if not check(self.store):
            raise AuthorError('author_schema_not_initialized')

    def row(self, aid):
        rows = self.store.execute('SELECT * FROM authors WHERE source=%s AND author_id=%s', identity(aid))
        return rows[0] if rows else None

    def save(self, value):
        value = validate(value)
        self.ready()
        aid = value['author_id']
        with author_lock(self.store, aid):
            # End any preceding consistent-read snapshot before examining concurrent writes.
            self.store.db.rollback()
            old = self.row(aid)
            observed = datetime.fromisoformat(value['fetched_at']).replace(tzinfo=None)
            if old and old['last_attempt_at'] and old['last_attempt_at'] > observed:
                self.store.db.rollback()
                return {'status': 'stale', 'author_id': aid, 'written': False}
            relative = f"authors/ieee/{aid}/{value['payload_sha256']}.json"
            destination = self.state_dir / relative
            if not destination.exists():
                atomic_write(destination, value)
            else:
                # Same content shares one successful snapshot; provenance retains its first observation time.
                existing = read_snapshot(destination)
                if existing['payload_sha256'] != value['payload_sha256'] or existing['author_id'] != aid:
                    raise AuthorError('snapshot_collision')
            fields = {'source': 'ieee', 'author_id': aid}
            for name, val in value['profile'].items():
                fields[name + '_json' if name in ARRAYS else name] = (
                    encoded(val).decode() if name in ARRAYS else val)
            fields.update(field_states_json=encoded(value['field_states']).decode(),
                source_url=BASE + '/author/' + aid, source_endpoint=BASE + '/rest/author/' + aid,
                fetched_at=observed, parser_version=value['parser_version'],
                payload_sha256=value['payload_sha256'], snapshot_path=relative,
                fetch_state='hidden' if value['profile']['is_hidden'] else 'complete',
                last_attempt_at=observed, last_http_status=200, last_error_code=None, last_error=None)
            names = list(fields)
            sql = ('INSERT INTO authors (' + ','.join(names) + ') VALUES (' + ','.join(['%s'] * len(names)) +
                   ') ON DUPLICATE KEY UPDATE ' + ','.join(n + '=VALUES(' + n + ')' for n in names[2:]) +
                   ',updated_at=CURRENT_TIMESTAMP(6)')
            try:
                self.store.execute(sql, tuple(fields[n] for n in names))
                self.store.db.commit()
            except Exception:
                self.store.db.rollback()
                raise
        return {'status': 'saved', 'source': 'ieee', 'author_id': aid, 'written': True,
                'payload_sha256': value['payload_sha256'], 'snapshot_path': relative}

    def failed(self, aid, error, attempted_at):
        self.ready()
        with author_lock(self.store, aid):
            self.store.db.rollback()
            old = self.row(aid)
            attempted = datetime.fromisoformat(attempted_at).replace(tzinfo=None)
            if old and old['last_attempt_at'] and old['last_attempt_at'] > attempted:
                self.store.db.rollback()
                return
            try:
                self.store.execute('INSERT INTO authors (source,author_id,fetch_state,last_attempt_at,'
                    'last_http_status,last_error_code,last_error) VALUES (%s,%s,%s,%s,%s,%s,%s) '
                    'ON DUPLICATE KEY UPDATE fetch_state=VALUES(fetch_state),last_attempt_at=VALUES(last_attempt_at),'
                    'last_http_status=VALUES(last_http_status),last_error_code=VALUES(last_error_code),'
                    'last_error=VALUES(last_error),updated_at=CURRENT_TIMESTAMP(6)',
                    ('ieee', aid, 'blocked' if error.code == 'access_restricted' else 'failed',
                     attempted, error.http_status, error.code, 'Single-author retrieval did not complete'))
                self.store.db.commit()
            except Exception:
                self.store.db.rollback()
                raise

    def show(self, aid, public=False):
        identity(aid)
        from .author_schema import check, core_ready
        core_ready(self.store)
        if not check(self.store):
            return None
        row = self.row(aid)
        if not row:
            return None
        profile = {name: json.loads(row.get(name + '_json') or 'null') if name in ARRAYS else row.get(name)
                   for name in FIELD_MAP}
        if profile['is_hidden'] is not None:
            profile['is_hidden'] = bool(profile['is_hidden'])
        # Reapply whitelist and plain-text handling at the response boundary.
        profile, _ = normalize(profile, canonical=True)
        hidden = profile['is_hidden'] is True
        if public and hidden:
            profile = {'is_hidden': True}
        def date(name):
            val = row.get(name)
            return val.replace(tzinfo=timezone.utc).isoformat() if val else None
        out = {'source': 'ieee', 'author_id': aid, 'profile': profile,
               'fetch_state': 'hidden' if hidden else row['fetch_state'],
               'field_states': {} if public and hidden else json.loads(row.get('field_states_json') or '{}'),
               'fetched_at': date('fetched_at'), 'last_attempt_at': date('last_attempt_at'),
               'last_http_status': row.get('last_http_status'), 'last_error_code': row.get('last_error_code'),
               'source_url': BASE + '/author/' + aid, 'updated_at': date('updated_at')}
        if not public:
            out.update(snapshot_path=row.get('snapshot_path'), payload_sha256=row.get('payload_sha256'),
                       parser_version=row.get('parser_version'))
        return out
