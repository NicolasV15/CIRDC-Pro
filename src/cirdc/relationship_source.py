"""Independent evidence for a publisher's outgoing and incoming paper lists."""
from .reference_source import plain
from .provider import UpstreamError


def section_flag(metadata, direction):
    sections = (metadata or {}).get('sections')
    if not isinstance(sections, dict):
        return None
    # The publisher's verified document metadata uses string booleans and
    # names the incoming-citation tab "citedby".
    keys = ('citedby', 'citations') if direction == 'citations' else (direction,)
    values = []
    for key in keys:
        value = sections.get(key)
        if isinstance(value, bool):
            values.append(value)
        elif value in ('true', 'false'):
            values.append(value == 'true')
        elif key in sections:
            return None
    return values[0] if values and all(v == values[0] for v in values) else None


def verify_response(data, number, metadata=None):
    if not isinstance(data, dict) or any(data.get(k) for k in ('error', 'errors', 'errorCode', 'errorMessage', 'challenge', 'captcha')):
        raise UpstreamError('parse_failed', 'Invalid relationship response')
    identity = data.get('articleNumber', data.get('articleId'))
    if identity is not None and str(identity) != number:
        raise UpstreamError('parse_failed', 'Relationship identity differs')
    expected = plain((metadata or {}).get('title') or (metadata or {}).get('articleTitle'))
    actual = plain(data.get('title') or data.get('displayDocTitle'))
    if expected and actual and expected != actual:
        raise UpstreamError('parse_failed', 'Relationship title differs')


def resolve_section(provider, number, metadata, direction):
    # The document metadata is already fetched in the normal session. The bare
    # REST document endpoint serves full text and is outside relationship reads.
    if not metadata or str(metadata.get('articleNumber')) != number:
        return None
    return section_flag(metadata, direction)


def availability(state, total, expected, flag=None):
    if total:
        return {'source_presence': 'present', 'empty_reason': None}
    if state == 'no_data':
        return {'source_presence': 'absent' if flag is False else 'present',
                'empty_reason': 'section_absent' if flag is False else 'zero_count'}
    return {'source_presence': 'unknown', 'empty_reason': None}
