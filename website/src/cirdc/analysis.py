from .provider import IEEE


def analyze(config, number, direction, depth=3, max_nodes=100):
    if not str(number).isdigit() or direction not in ('references', 'citations', 'tree'):
        raise ValueError('Invalid analysis request')
    provider = IEEE(config)
    seen = set()
    def visit(n, level):
        if n in seen or level >= depth or len(seen) >= max_nodes:
            return {'articleNumber': n, 'children': [], 'boundary': True}
        seen.add(n)
        rows = provider.relationships(n, 'citations' if direction == 'tree' else direction)
        children = []
        for r in rows:
            links = r.get('links') or {}
            child = links.get('articleNumber')
            if not child and links.get('documentLink'):
                child = links['documentLink'].split('/document/')[-1].split('/')[0]
            item = {'articleNumber': str(child) if child else None, 'title': r.get('title', '')}
            if direction == 'tree' and child:
                item['children'] = visit(str(child), level + 1)['children']
            children.append(item)
        return {'articleNumber': n, 'children': children,
                'coverage': 'source_page_limit_reached' if direction == 'references' and len(rows) >= 300 else 'source_response'}
    return {'direction': direction, 'tree': visit(str(number), 0), 'visited_nodes': len(seen)}
