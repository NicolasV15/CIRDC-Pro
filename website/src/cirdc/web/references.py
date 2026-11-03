"""SELECT-only reference views and a bounded, configured maintenance enqueue bridge."""
import json
import re
import subprocess
import time
from contextlib import closing

from starlette.concurrency import run_in_threadpool
from starlette.routing import Route

from ..store import Store
from .access import SearchRateLimiter


def options(config):
    value = config.web.get('references', {})
    return value if isinstance(value, dict) else {}


def enabled(config):
    return options(config).get('enabled') is True


class ReferenceError(ValueError):
    def __init__(self, code, status):
        self.code, self.status = code, status


def read(config, number, offset=0, limit=50, version=None, order=None):
    if not re.fullmatch('[0-9]{1,64}', number):
        raise ReferenceError('invalid_number', 422)
    if not 0 <= offset <= 10000000 or not 1 <= limit <= 100 or (order is not None and order < 1):
        raise ReferenceError('invalid_reference_page', 422)
    if version is not None and not re.fullmatch('[a-f0-9]{32}', version):
        raise ReferenceError('invalid_reference_version', 422)
    command = options(config).get('read_command')
    if enabled(config) and command:
        if not isinstance(command, list) or any(not isinstance(s, str) or not s for s in command):
            raise ReferenceError('references_unavailable', 503)
        args = [*command, 'references', 'read', number, '--offset', str(offset), '--limit', str(limit)]
        if version:
            args += ['--version', version]
        if order is not None:
            args += ['--order', str(order)]
        try:
            process = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15, check=False)
            value = json.loads(process.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            raise ReferenceError('references_unavailable', 503) from None
        if process.returncode:
            code = value.get('code')
            raise ReferenceError(code if code in ('not_found', 'reference_not_found', 'reference_version_not_found') else 'references_unavailable',
                                 404 if code in ('not_found', 'reference_not_found', 'reference_version_not_found') else 503)
        if value.get('number') != number or not isinstance(value.get('items') if order is None else value.get('item'), list if order is None else dict):
            raise ReferenceError('references_unavailable', 503)
        return {k: v for k, v in value.items() if k in ('number', 'state', 'version', 'total', 'expected_total', 'checked_at', 'error',
                                                      'offset', 'limit', 'next_offset', 'items', 'item','source_presence','empty_reason','availability_checked_at','needs_availability_check')}
    with closing(Store(config)) as store:
        if not store.execute('SELECT number FROM papers WHERE number=%s', (number,)):
            raise ReferenceError('not_found', 404)
        out = {'number': number, 'state': 'missing' if enabled(config) else 'disabled',
               'version': None, 'total': 0, 'expected_total': None, 'checked_at': None,
               'error': None, 'offset': offset, 'limit': limit, 'next_offset': None, 'items': []}
        if not enabled(config):
            return out
        installed = store.execute('SELECT version FROM reference_schema_migrations ORDER BY version')
        if [r['version'] for r in installed] != [1]:
            raise ReferenceError('references_not_initialized', 503)
        rows = store.execute('SELECT * FROM paper_reference_state WHERE number=%s', (number,))
        if rows:
            current = rows[0]
            for key in ('state', 'version', 'total', 'expected_total', 'error'):
                out[key] = current[key]
            out['checked_at'] = current['checked_at'].isoformat() + 'Z' if current['checked_at'] else None
        selected = version or out['version']
        if version:
            snapshots = store.execute('SELECT * FROM paper_reference_snapshots WHERE number=%s AND version=%s', (number, version))
            if not snapshots:
                raise ReferenceError('reference_version_not_found', 404)
            snapshot = snapshots[0]
            if selected != out['version']:
                out.update(state=snapshot['state'], error=None, checked_at=snapshot['fetched_at'].isoformat() + 'Z')
            out.update(version=version, total=snapshot['total'], expected_total=snapshot['expected_total'])
        if not selected:
            if order is not None:
                raise ReferenceError('reference_not_found', 404)
            return out
        if order is not None:
            items = store.execute('SELECT data FROM paper_references WHERE number=%s AND version=%s AND ordinal=%s',
                                  (number, selected, order))
            if not items:
                raise ReferenceError('reference_not_found', 404)
            return {'number': number, 'version': selected, 'item': json.loads(items[0]['data'])}
        items = store.execute('SELECT data FROM paper_references WHERE number=%s AND version=%s ORDER BY ordinal LIMIT %s OFFSET %s',
                              (number, selected, limit, offset))
        out['items'] = [json.loads(r['data']) for r in items]
        end = offset + len(items)
        out['next_offset'] = end if end < out['total'] else None
        return out


def enqueue(config, number):
    current = read(config, number)
    if current['state'] != 'missing' and not current.get('needs_availability_check'):
        return current
    command = options(config).get('enqueue_command')
    if not isinstance(command, list) or not command or any(not isinstance(s, str) or not s for s in command):
        raise ReferenceError('references_queue_unavailable', 503)
    try:
        args = [*command, 'references', 'enqueue', number]
        if current.get('needs_availability_check'):args.append('--check-availability')
        result = subprocess.run(args, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=15, check=False)
        value = json.loads(result.stdout)
        from .task_origins import note_queue_result
        note_queue_result('references', number, value)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise ReferenceError('references_queue_unavailable', 503) from None
    if result.returncode or value.get('status') not in ('queued', 'reused'):
        if value.get('code') == 'worker_busy':
            # A concurrent tab may own the very short enqueue lock. Observe its
            # committed result rather than retrying collection or reporting a failure.
            for _ in range(3):
                time.sleep(0.1)
                current = read(config, number)
                if current['state'] != 'missing':
                    return current
        raise ReferenceError('references_queue_unavailable', 503)
    return read(config, number)


def routes(config, response):
    limiter = SearchRateLimiter(limit=10, interval=60)

    async def listing(request):
        try:
            value = await run_in_threadpool(read, config, request.path_params['number'],
                                           int(request.query_params.get('offset', '0')),
                                           int(request.query_params.get('limit', '50')),
                                           request.query_params.get('version'))
            return response(value)
        except ReferenceError as error:
            return response({'error': error.code}, error.status)
        except ValueError:
            return response({'error': 'invalid_reference_page'}, 422)

    async def item(request):
        try:
            value = await run_in_threadpool(read, config, request.path_params['number'], 0, 50,
                                           request.query_params.get('version'), int(request.path_params['order']))
            return response(value)
        except ReferenceError as error:
            return response({'error': error.code}, error.status)
        except ValueError:
            return response({'error': 'invalid_reference_order'}, 422)

    async def ensure(request):
        try:
            current = await run_in_threadpool(read, config, request.path_params['number'])
            if current['state'] == 'missing' or current.get('needs_availability_check'):
                peer = request.client.host if request.client else 'unknown'
                if not limiter.allow(peer):
                    return response({'error': 'rate_limited'}, 429)
                current = await run_in_threadpool(enqueue, config, request.path_params['number'])
            return response(current, 202 if current['state'] in ('queued', 'fetching') else 200)
        except ReferenceError as error:
            return response({'error': error.code}, error.status)

    return [Route('/api/papers/{number}/references', listing),
            Route('/api/papers/{number}/references/ensure', ensure, methods=['POST']),
            Route('/api/papers/{number}/references/{order}', item)]
