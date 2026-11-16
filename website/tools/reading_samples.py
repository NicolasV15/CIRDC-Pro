"""Extra reading samples for the offline demo, one per reading path.

* ``arxiv_html``: the cached CC BY 4.0 supplement 2611.14443v1, byte-for-byte. Its paper record is derived only
  from the cached HTML (title, abstract, the arXiv watermark's category and date); the HTML names no authors.
* ``arxiv_source`` and ``pdf_parse``: representative fixtures written for this demo to exercise the reader's
  structure handling. They are not conversions of any paper and say so in their own text.

All samples use demo-only internal IDs outside the 43-paper seed and are not added to the search index.
"""
import hashlib
import html
import json
import re
from pathlib import Path

from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

DATA = Path(__file__).resolve().parents[1] / 'demo' / 'arxiv'
SUPPLEMENT = DATA / 'reading-supplement' / '2611.14443v1'
FIXTURES = DATA / 'reading-fixtures'


def verified(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    for entry in manifest['files']:
        raw = (folder / entry['file']).read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('reading_sample_digest_mismatch: ' + entry['file'])
    return manifest


def text(fragment):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', fragment))).strip()


def table_of_contents(body):
    return [{'id': m['id'], 'title': text(m['title']), 'level': int(m['level'])}
            for m in re.finditer(r'<h(?P<level>[1-6])[^>]*\bid="(?P<id>[^"]+)"[^>]*>(?P<title>.*?)</h(?P=level)>', body, re.DOTALL)]


def supplement_record(paper_id):
    manifest = verified(SUPPLEMENT)
    article = (SUPPLEMENT / 'article.html').read_text()
    watermark = re.search(r'arXiv:(\S+)v(\d+) \[([^\]]+)\] (\d+ \w+ \d{4})', article)
    from datetime import datetime
    date = datetime.strptime(watermark[4], '%d %b %Y').strftime('%Y-%m-%dT00:00:00+00:00')
    title = text(re.search(r'<h1 class="ltx_title ltx_title_document">(.*?)</h1>', article, re.DOTALL)[1])
    abstract = text(re.search(r'<p id="abstract1.1" class="ltx_p">(.*?)</p>', article, re.DOTALL)[1])
    return manifest, {
        'paper_id': paper_id, 'arxiv_id': manifest['arxiv_id'], 'title': title, 'abstract': abstract, 'authors_raw': '',
        'source': 'arxiv', 'deleted': 0,
        'metadata': {'categories': [watermark[3]], 'license': manifest['license'], 'submitted_at': date,
                     'demo_record': 'derived from the cached HTML; the HTML lists no authors'},
        'versions': [{'version': manifest['version'], 'version_date': date}],
        'metadata_coverage': {'scope': 'demo_reading_sample', 'verified_through': None},
    }


def samples():
    """{paper_id: sample} for every extra reading sample; ``files`` maps original kinds to cached files."""
    result = {}
    manifest, record = supplement_record('9900001')
    result['9900001'] = {'record': record, 'source': manifest['source'], 'render_id': manifest['render_id'],
                         'body': SUPPLEMENT / 'body.html', 'files': {'html': (SUPPLEMENT / 'article.html', 'text/html')}}
    for entry in verified(FIXTURES)['samples']:
        record = {'paper_id': entry['paper_id'], 'arxiv_id': entry['label'], 'title': entry['title'], 'abstract': entry['abstract'],
                  'authors_raw': 'CIRDC fixture', 'source': 'arxiv', 'deleted': 0,
                  'metadata': {'categories': ['eess.SP'], 'demo_record': 'representative fixture, not a paper'},
                  'versions': [{'version': 1, 'version_date': None}],
                  'metadata_coverage': {'scope': 'demo_reading_fixture', 'verified_through': None}}
        result[entry['paper_id']] = {'record': record, 'source': entry['source'], 'render_id': entry['render_id'],
                                     'body': FIXTURES / entry['body'], 'files': {}}
    return result


def routes():
    registry = samples()

    def missing(code='demo_resource_not_packaged'):
        return JSONResponse({'error': code, 'demo': True}, status_code=404)

    def lookup(request):
        sample = registry.get(request.url.path.split('/')[4])
        return sample if sample and request.path_params.get('version', 1) == 1 else None

    def document(sample):
        base = f"/api/arxiv/papers/{sample['record']['paper_id']}/versions/1"
        return {'source': sample['source'], 'version': sample['render_id'], 'render_id': sample['render_id'], 'paper_version': 1,
                'body_url': f"{base}/body?render_id={sample['render_id']}", 'toc': table_of_contents(sample['body'].read_text()),
                'assets_ready': 0, 'assets_total': 0}

    def paper(request):
        sample = lookup(request)
        return JSONResponse({'paper': sample['record']}) if sample else missing('paper_or_version_not_found')

    def resources(request):
        sample = lookup(request)
        if not sample:
            return missing('paper_or_version_not_found')
        base = f"/api/arxiv/papers/{sample['record']['paper_id']}/versions/1/files/"
        state = {kind: {'state': 'ready', 'download_url': base + kind} if kind in sample['files'] else {'state': 'not_packaged'}
                 for kind in ('html', 'pdf', 'source')}
        return JSONResponse({'state': 'demo_snapshot', 'paper_version': 1, 'reading_state': 'ready', 'reading_ready': True,
                             'acquisition_complete': False, 'document': document(sample), 'resources': state, 'demo': True})

    def content(request):
        sample = lookup(request)
        return JSONResponse({'state': 'ready', 'document': document(sample)}) if sample else missing('paper_or_version_not_found')

    def body(request):
        sample = lookup(request)
        if not sample or request.query_params.get('render_id') != sample['render_id']:
            return missing('render_not_found')
        return FileResponse(sample['body'], media_type='text/html; charset=utf-8')

    def original(request):
        sample = lookup(request)
        if not sample or request.path_params['kind'] not in sample['files']:
            return missing()
        path, media = sample['files'][request.path_params['kind']]
        return FileResponse(path, media_type=media, filename=f"{sample['record']['arxiv_id']}v1.html")

    # Literal paths: only these demo-only IDs are answered here; every other paper keeps its normal routes.
    result = []
    for paper_id in registry:
        base = '/api/arxiv/papers/' + paper_id
        result += [Route(base, paper), Route(base + '/versions/{version:int}/resources', resources),
                   Route(base + '/versions/{version:int}/document', content), Route(base + '/versions/{version:int}/body', body),
                   Route(base + '/versions/{version:int}/files/{kind}', original)]
    return result, set(registry)
