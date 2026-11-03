"""OpenAPI is served from the same distribution as its implementation."""


def specification():
    def parameter(name, kind='string', location='query', **schema):
        return {'name': name, 'in': location, 'required': location == 'path', 'schema': {'type': kind, **schema}}

    def operation(name, parameters=(), body=None, binary=None):
        response = {'description': 'Result; inspect resource states and completeness.',
                    'content': {binary or 'application/json': {'schema': {'type': 'string', 'format': 'binary'} if binary else {'type': 'object'}}}}
        if binary and binary.startswith('text/'):
            response['content'][binary]['schema'] = {'type': 'string'}
        value = {'operationId': name, 'parameters': list(parameters), 'responses': {'200': response}}
        for code, description in [('401', 'Authentication required'), ('403', 'Access denied'), ('202', 'Pending; follow status_url and Retry-After'), ('404', 'Not indexed or unknown request/version'),
                                  ('409', 'Resource not ready'), ('422', 'Invalid request or cursor'),
                                  ('429', 'Rate limited'), ('503', 'Resource service unavailable')]:
            value['responses'][code] = {'description': description, 'content': {'application/json': {'schema': {'type': 'object'}}}}
        if body:
            value['requestBody'] = {'required': True, 'content': {'application/json': {'schema': body}}}
        return value

    number = parameter('number', location='path', pattern='^[0-9]{1,64}$')
    search = [parameter(k) for k in ('q', 'field', 'sort', 'kind', 'venue', 'venue_tags', 'author_id',
                                    'author_source', 'abstract_state', 'keywords_state', 'cursor')]
    search += [parameter(k, 'integer') for k in ('limit', 'year_from', 'year_to')]
    ensure = {'type': 'object', 'additionalProperties': False, 'properties': {
        'resources': {'type': 'array', 'items': {'type': 'string', 'enum': ['content', 'pdf']},
                      'minItems': 1, 'maxItems': 2, 'uniqueItems': True, 'default': ['content']},
        'wait_seconds': {'type': 'number', 'minimum': 0, 'maximum': 30, 'default': 10},
        'retry': {'type': 'boolean', 'default': False}}}
    spec = {'openapi': '3.1.0', 'info': {'title': 'CIRDC-Pro Research API', 'version': '1.0.0',
            'description': 'Public access to indexed papers and on-demand resources. GET is read-only. '
                           'Resource requests return durable receipts; follow next_action during bounded backend recovery. No credentials required.'},
            'servers': [{'url': '/api/agent/v1'}], 'security': [], 'paths': {
                '/capabilities': {'get': operation('capabilities')},
                '/papers': {'get': operation('search_papers', search)},
                '/papers/{number}': {'get': operation('get_paper', [number])},
                '/papers/{number}/ensure': {'post': operation('ensure_resources', [number], ensure)},
                '/requests/{request_id}': {'get': operation('get_request', [parameter('request_id', location='path')])},
                '/papers/{number}/content': {'get': operation('read_content', [number, parameter('version'), parameter('cursor'),
                    parameter('format', enum=['markdown', 'text', 'html'], default='markdown'),
                    parameter('limit', 'integer', minimum=1000, maximum=48000, default=12000)])},
                '/papers/{number}/pdf': {method: operation(('download' if method == 'get' else 'check') + '_pdf', [number], binary='application/pdf')
                                       for method in ('get', 'head')},
                '/papers/{number}/assets/{asset_id}': {'get': operation('read_asset', [number,
                    parameter('asset_id', location='path'), {**parameter('version'), 'required': True}], binary='application/octet-stream')},
                '/skills/cirdc-research/SKILL.md': {'get': operation('read_skill', binary='text/markdown')},
                '/skills/cirdc-research/references/api.md': {'get': operation('read_skill_reference', binary='text/markdown')},
                '/mcp': {'post': {'operationId': 'research_mcp',
                    'description': 'MCP Streamable HTTP endpoint. Use an MCP client for initialize, tools/list and tools/call.',
                    'requestBody': {'required': True, 'content': {'application/json': {'schema': {'type': 'object',
                        'properties': {'jsonrpc': {'const': '2.0'}, 'method': {'type': 'string'}, 'params': {'type': 'object'}},
                        'required': ['jsonrpc', 'method']}}}},
                    'responses': {'200': {'description': 'MCP JSON-RPC result or error'},
                                  '202': {'description': 'MCP notification accepted'},
                                  '400': {'description': 'Invalid MCP message'},
                                  '413': {'description': 'Request body too large'}}}},
                '/openapi.json': {'get': operation('openapi')}}}
    string = {'type': 'string'}
    nullable_string = {'type': ['string', 'null']}
    integer = {'type': 'integer'}
    def obj(properties, required=()):
        return {'type': 'object', 'properties': properties, 'required': list(required)}
    def ref(name):
        return {'$ref': '#/components/schemas/' + name}
    resource_map = obj({'content': ref('ResourceStatus'), 'pdf': ref('ResourceStatus')})
    spec['components'] = {'schemas': {
        'Job': obj({'id': string, 'kind': string, 'state': string, 'error': nullable_string,
                    'parent_id': string, 'updated': {'type': 'number'}}, ['id', 'kind', 'state']),
        'ResourceStatus': obj({'state': {'type': 'string', 'enum': ['missing', 'pending', 'ready', 'partial', 'unavailable', 'failed']},
            'phase': nullable_string, 'reason': nullable_string, 'retryable': {'type': 'boolean'},
            'retry_after_seconds': integer, 'message': string, 'next_action': {'type': 'string', 'enum': ['wait', 'contact_administrator', 'stop']},
            'retry_attempts': integer, 'max_retry_attempts': integer, 'next_retry_at': {'type': ['number', 'null']},
            'transient': {'type': 'boolean'}, 'source': nullable_string, 'version': nullable_string,
            'url': string, 'media_type': string, 'bytes': {'type': ['integer', 'null']},
            'sha256': nullable_string, 'assets_ready': {'type': ['integer', 'null']},
            'assets_total': {'type': ['integer', 'null']}, 'jobs': {'type': 'array', 'items': ref('Job')}}, ['state', 'jobs']),
        'Receipt': obj({'api_version': string, 'request_id': string, 'number': string, 'resources': resource_map,
            'status_url': string, 'complete': {'type': 'boolean'}, 'pending': {'type': 'boolean'},
            'retry_after_seconds': {'type': ['integer', 'null']}, 'created_at': {'type': 'number'},
            'updated_at': {'type': 'number'}, 'prior_attempts': integer},
            ['request_id', 'number', 'resources', 'status_url', 'complete', 'pending']),
        'ContentPage': obj({'api_version': string, 'number': string, 'version': string, 'source': nullable_string,
            'format': {'type': 'string', 'enum': ['markdown', 'text', 'html']}, 'state': string,
            'sha256': string, 'toc': {'type': 'array', 'items': {'type': 'object'}},
            'content': string, 'blocks': {'type': 'array', 'items': obj({'id': string, 'section_id': nullable_string,
                'content': string}, ['id', 'content'])},
            'assets': {'type': 'array', 'items': obj({'url': string, 'alt': string}, ['url'])},
            'assets_ready': {'type': ['integer', 'null']}, 'assets_total': {'type': ['integer', 'null']},
            'warnings': {'type': 'array', 'items': string}, 'offset': integer, 'total_blocks': integer,
            'next_cursor': nullable_string, 'citation': {'type': 'object'}},
            ['number', 'version', 'source', 'format', 'blocks', 'content', 'next_cursor', 'warnings']),
        'PaperDetail': obj({'paper': {'type': 'object'}, 'resources': resource_map, 'source_url': string}, ['paper', 'resources']),
        'SearchResult': obj({'items': {'type': 'array', 'items': {'type': 'object'}}, 'total': {'type': ['integer', 'null']},
            'next_cursor': nullable_string, 'partial': {'type': 'boolean'}}, ['items']),
        'Capabilities': obj({'authentication': {'const': 'none'}, 'resources': {'type': 'object'},
            'formats': {'type': 'array', 'items': string}, 'limits': {'type': 'object'},
            'openapi_url': string, 'skill_url': string, 'mcp_url': string, 'mcp_transport': {'const': 'streamable-http'},
            'guide_url': string, 'instructions_url': string,
            'scope': {'const': 'indexed_papers_only'}}, ['authentication', 'resources', 'formats', 'limits']),
        'Error': obj({'api_version': string, 'error': string, 'message': string,
            'next_action': {'type': 'string', 'enum': ['wait', 'ensure', 'stop', 'contact_administrator']},
            'retry_after_seconds': integer, 'accepted': {'type': ['boolean', 'null']},
            'request_id': string, 'status_url': string}, ['error'])}}
    shapes = {'capabilities': 'Capabilities', 'search_papers': 'SearchResult', 'get_paper': 'PaperDetail',
              'ensure_resources': 'Receipt', 'get_request': 'Receipt', 'read_content': 'ContentPage'}
    for path in spec['paths'].values():
        for op in path.values():
            if op['operationId'] == 'research_mcp':
                continue
            shape = shapes.get(op['operationId'])
            if shape:
                op['responses']['200']['content']['application/json']['schema'] = ref(shape)
            for code in ('401', '403', '404', '409', '422', '429', '503'):
                # A service outage can retain a durable receipt and per-resource errors.
                op['responses'][code]['content']['application/json']['schema'] = {'anyOf': [ref('Error'), ref('Receipt')]} if code == '503' else ref('Error')
            for code in ('429', '503'):
                op['responses'][code]['headers'] = {'Retry-After': {'schema': integer}}
            if op['operationId'] in ('ensure_resources', 'get_request'):
                op['responses']['202']['content']['application/json']['schema'] = ref('Receipt')
                op['responses']['202']['headers'] = {'Retry-After': {'schema': integer, 'description': 'Suggested poll interval in seconds'}}
    return spec
