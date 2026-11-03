import pytest
from cirdc.web.agent_documents import DocumentError, page_document


def document(html, version='v1'):
    return {'html': html, 'version': version, 'source': 'publisher', 'toc': [{'id': 's1'}],
            'state': 'partial', 'assets_ready': 0, 'assets_total': 1}


def test_math_table_figure_and_plain_text():
    source = '<section id="s1"><h2>Results</h2><p>Gain <span class="doc-math">\\(A_v=x_1\\)</span></p>' \
             '<table><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table>' \
             '<figure><img alt="Figure 1" src="/api/content/123/assets/a1?version=v1"><figcaption>Measured gain</figcaption></figure></section>'
    value = page_document(document(source), '123')
    assert '$A_v=x_1$' in value['content']
    assert 'rowspan="2"' in value['content']
    assert 'table_preserved_as_html' in value['warnings']
    assert 'Measured gain' in value['content']
    assert value['assets'][0]['url'] == '/api/agent/v1/papers/123/assets/a1?version=v1'
    assert value['state'] == 'partial' and value['assets_ready'] == 0
    assert value['blocks'][0]['section_id'] == 's1'
    plain = page_document(document(source), '123', 'text')
    assert 'A_v=x_1' in plain['content'] and 'A\tB' in plain['content']
    assert 'table_flattened_to_text' in plain['warnings']


def test_version_pagination_is_complete_and_detects_mixed_versions():
    source = ''.join('<p>' + str(i) + 'x' * 600 + '</p>' for i in range(8))
    value = page_document(document(source), '123', limit=1000)
    blocks = list(value['blocks'])
    cursor = value['next_cursor']
    with pytest.raises(DocumentError, match='cursor_document_mismatch'):
        page_document(document(source, 'v2'), '123', cursor=cursor)
    with pytest.raises(DocumentError, match='cursor_document_mismatch'):
        page_document(document(source), '124', cursor=cursor)
    while cursor:
        value = page_document(document(source), '123', cursor=cursor, limit=1000)
        blocks.extend(value['blocks'])
        cursor = value['next_cursor']
    assert [b['id'] for b in blocks] == ['b' + str(i) for i in range(8)]
    assert all(len(b['content']) == 601 for b in blocks)


def test_html_assets_are_pinned_and_executable_markup_is_removed():
    source = '<p onclick="bad()">Hello</p><script>bad()</script><img src="https://tracker.example.org/a.png">'
    value = page_document(document(source), '123', 'html')
    assert 'script' not in value['content'] and 'onclick' not in value['content']
    assert 'tracker.example' not in value['content']
    assert 'image_source_unavailable' in value['warnings']


def test_large_block_is_not_truncated_and_cursor_is_validated():
    value = page_document(document('<p>' + 'x' * 1500 + '</p><p>tail</p>'), '123', limit=1000)
    assert len(value['content']) == 1500 and value['next_cursor']
    assert 'oversized_block_preserved' in value['warnings']
    with pytest.raises(DocumentError, match='invalid_cursor'):
        page_document(document('<p>x</p>'), '123', cursor='!bad')
