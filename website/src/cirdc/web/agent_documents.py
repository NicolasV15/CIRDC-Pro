"""Version-pinned, bounded reading of provider-supplied, cleaned documents."""
import base64
import hashlib
import html
import json
import re
from urllib.parse import urlsplit, quote

from lxml import etree
from lxml import html as markup

PREFIX = '/api/agent/v1'
FORMATS = ('markdown', 'text', 'html')


class DocumentError(ValueError):
    pass


def encode_cursor(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).decode().rstrip('=')


def decode_cursor(value):
    try:
        if len(value) > 2048:
            raise ValueError()
        data = json.loads(base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, UnicodeError, TypeError):
        raise DocumentError('invalid_cursor') from None


def asset_url(value, number, version):
    """Only a declared local document asset can become an Agent asset URL."""
    url = urlsplit(value)
    match = re.fullmatch(r'/api/content/([0-9]{1,64})/assets/([A-Za-z0-9_.:-]{1,128})', url.path)
    agent = re.fullmatch(PREFIX + r'/papers/([0-9]{1,64})/assets/([A-Za-z0-9_.:-]{1,128})', url.path)
    match = match or agent
    if url.scheme or url.netloc or not match or match[1] != number:
        return None
    return f'{PREFIX}/papers/{number}/assets/{quote(match[2])}?version={quote(version)}'


def render_document(source, number, version, output_format):
    if output_format not in FORMATS:
        raise DocumentError('invalid_format')
    root = markup.fragment_fromstring(source or '<p></p>', create_parent='div')
    warnings = set()
    assets = []
    for node in list(root.iter()):
        if not isinstance(node.tag, str):
            continue
        if node.tag in ('script', 'style', 'iframe', 'object', 'embed', 'form'):
            node.drop_tree()
            continue
        for key in list(node.attrib):
            if key.lower().startswith('on'):
                del node.attrib[key]
        if node.tag == 'img':
            href = asset_url(node.get('src', ''), number, version)
            if href:
                node.set('src', href)
                assets.append({'url': href, 'alt': node.get('alt', '')})
            else:
                node.attrib.pop('src', None)
                warnings.add('image_source_unavailable')
        if node.tag == 'a':
            href = node.get('href', '')
            url = urlsplit(href)
            if url.scheme not in ('', 'http', 'https') or url.netloc and not url.scheme:
                node.attrib.pop('href', None)

    def literal(value):
        return re.sub(r'([\\`*_\[\]<>$])', r'\\\1', value) if output_format == 'markdown' else value

    def children(node):
        return literal(node.text or '') + ''.join(render(c) + literal(c.tail or '') for c in node)

    def render(node):
        if not isinstance(node.tag, str):
            return ''
        tag = node.tag.lower()
        text = children(node)
        if 'doc-math' in node.get('class', '').split():
            tex = ''.join(node.itertext()).strip()
            if output_format == 'text':
                return tex
            display = tex.startswith(('\\[', '$$', '\\begin{'))
            if tex.startswith(('\\(', '\\[')) and tex.endswith(('\\)', '\\]')):
                tex = tex[2:-2]
            elif tex.startswith('$$') and tex.endswith('$$'):
                tex = tex[2:-2]
            elif tex.startswith('$') and tex.endswith('$'):
                tex = tex[1:-1]
            return ('\n\n$$\n' + tex + '\n$$\n\n') if display else '$' + tex + '$'
        if tag == 'img':
            label, href = node.get('alt', 'Image'), node.get('src')
            return ('![' + label.replace(']', '\\]') + '](' + href + ')') if href and output_format == 'markdown' else (label + (' (' + href + ')' if href else ''))
        if tag == 'table':
            if output_format == 'markdown':
                warnings.add('table_preserved_as_html')
                return '\n\n' + etree.tostring(node, encoding='unicode', method='html', with_tail=False) + '\n\n'
            warnings.add('table_flattened_to_text')
            return '\n\n' + '\n'.join('\t'.join(''.join(c.itertext()).strip() for c in row if c.tag in ('th', 'td')) for row in node.iter('tr')) + '\n\n'
        if tag == 'br':
            return '\n'
        if tag == 'pre':
            text = ''.join(node.itertext())
            fence = '`' * max(3, 1 + max((len(m) for m in re.findall(r'`+', text)), default=0))
            return '\n\n' + (fence + '\n' + text + '\n' + fence if output_format == 'markdown' else text) + '\n\n'
        if output_format == 'markdown':
            if re.fullmatch('h[1-6]', tag):
                return '\n\n' + '#' * int(tag[1]) + ' ' + text.strip() + '\n\n'
            if tag in ('strong', 'b'):
                return '**' + text + '**'
            if tag in ('em', 'i'):
                return '*' + text + '*'
            if tag in ('sub', 'sup'):
                return '<' + tag + '>' + text + '</' + tag + '>'
            if tag == 'a' and node.get('href'):
                return '[' + text + '](' + node.get('href').replace(' ', '%20').replace(')', '%29') + ')'
            if tag == 'li':
                parent = node.getparent()
                marker = str(list(parent).index(node) + int(parent.get('start', '1'))) + '. ' if parent.tag == 'ol' else '- '
                return '\n' + marker + text.strip() + '\n'
        if tag in ('p', 'div', 'section', 'figure', 'figcaption', 'blockquote', 'ul', 'ol') or re.fullmatch('h[1-6]', tag):
            return '\n\n' + text.strip() + '\n\n'
        return text

    # Sections retain their original anchors; pages contain complete blocks.
    blocks = []

    def collect(parent, section=None):
        if parent.text and parent.text.strip():
            blocks.append({'section_id': section, 'html': html.escape(parent.text), 'text': literal(parent.text)})
        for child in parent:
            if not isinstance(child.tag, str):
                continue
            if child.tag in ('section', 'div', 'article') and 'doc-math' not in child.get('class', '').split():
                collect(child, child.get('id') or section)
            else:
                value = etree.tostring(child, encoding='unicode', method='html', with_tail=False) if output_format == 'html' else render(child).strip()
                if value:
                    blocks.append({'section_id': child.get('id') or section, 'text': value})
            if child.tail and child.tail.strip():
                blocks.append({'section_id': section, 'text': html.escape(child.tail) if output_format == 'html' else literal(child.tail)})

    collect(root)
    for index, block in enumerate(blocks):
        block['id'] = 'b' + str(index)
        block['content'] = block.pop('html', block['text']) if output_format == 'html' else block['text']
        block.pop('text', None)
    return blocks, assets, sorted(warnings)


def page_document(document, number, output_format='markdown', cursor=None, limit=12000):
    version = document['version']
    source = document['html']
    fingerprint = hashlib.sha256(source.encode()).hexdigest()
    blocks, assets, warnings = render_document(source, number, version, output_format)
    start = 0
    if cursor:
        token = decode_cursor(cursor)
        if any(token.get(k) != v for k, v in {'number': number, 'version': version, 'format': output_format, 'sha256': fingerprint}.items()):
            raise DocumentError('cursor_document_mismatch')
        start = token.get('offset')
        if type(start) is not int or not 0 <= start <= len(blocks):
            raise DocumentError('invalid_cursor')
    selected, length = [], 0
    for block in blocks[start:]:
        size = len(block['content'])
        if selected and length + size > limit:
            break
        selected.append(block)
        length += size
        if size > limit:
            warnings.append('oversized_block_preserved')
            break
    end = start + len(selected)
    next_cursor = encode_cursor({'number': number, 'version': version, 'format': output_format,
                                 'sha256': fingerprint, 'offset': end}) if end < len(blocks) else None
    return {'number': number, 'version': version, 'source': document.get('source'), 'format': output_format,
            'sha256': fingerprint, 'toc': document.get('toc', []), 'blocks': selected,
            'content': '\n\n'.join(b['content'] for b in selected), 'assets': assets,
            'assets_ready': document.get('assets_ready'), 'assets_total': document.get('assets_total'),
            'state': document.get('state', 'ready'), 'offset': start, 'total_blocks': len(blocks),
            'next_cursor': next_cursor, 'warnings': sorted(set(warnings))}
