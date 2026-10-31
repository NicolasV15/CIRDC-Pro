import html
import re


def plain_abstract(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', value or ''))).strip()


def search_preview(value):
    text = (value or '').strip()
    if not text.endswith('...'):
        return False
    body = text[:-3]
    return len(body) == 400 or len(plain_abstract(body).encode('utf-16-le')) // 2 == 400
