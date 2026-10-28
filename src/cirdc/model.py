import hashlib
import json

BASIC_FIELDS = ('publicationNumber', 'doi', 'publicationYear', 'publicationDate', 'articleTitle',
                'volume', 'issue', 'startPage', 'endPage', 'publisher', 'articleContentType',
                'publicationTitle')


def keywords(value):
    if isinstance(value, list):
        return {str(v.get('type', 'Unknown')): list(v.get('kwd') or [])
                for v in value if isinstance(v, dict) and v.get('kwd')}
    if isinstance(value, dict):
        return {str(k): [str(x) for x in v if str(x).strip()] for k, v in value.items()
                if isinstance(v, list) and v}
    return {}


def normalize(record):
    number = record.get('articleNumber')
    if number is None or not str(number).strip():
        raise ValueError('Record has no articleNumber')
    out = {'articleNumber': str(number)}
    out.update({k: record[k] for k in BASIC_FIELDS if record.get(k) is not None})
    out['authors'] = [{k: a[k] for k in ['id', 'preferredName', 'firstName', 'lastName'] if k in a}
                      for a in (record.get('authors') or []) if isinstance(a, dict)]
    if isinstance(record.get('abstract'), str):
        out['abstract'] = record['abstract']
    if 'keywords' in record:
        out['keywords'] = keywords(record['keywords'])
    return out


def merge(old, new):
    result = dict(old)
    for key, value in new.items():
        if value not in (None, '', [], {}):
            result[key] = value
        elif key not in result:
            result[key] = value
    return result


def field_states(record):
    return ('complete' if record.get('abstract', '').strip() else 'pending',
            'complete' if any(keywords(record.get('keywords')).values()) else 'pending')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=4).encode('utf-8')


def digest(content):
    return hashlib.sha256(content).hexdigest()
