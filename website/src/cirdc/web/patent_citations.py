"""Independent patent citation reads/enqueues via the maintenance bridge."""
import json
import re
import subprocess
import time
from contextlib import closing
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool
from starlette.routing import Route
from ..store import Store
from .access import SearchRateLimiter
from .references import ReferenceError


def options(config):
    value = config.web.get('patent_citations', {})
    return value if isinstance(value, dict) else {}


def enabled(config):
    return options(config).get('enabled') is True


def read(config, number, offset=0, limit=50, version=None):
    if not re.fullmatch('[0-9]{1,64}', number) or not 0 <= offset <= 10000000 or not 1 <= limit <= 100:
        raise ReferenceError('invalid_patent_citation_page', 422)
    if version is not None and not re.fullmatch('[a-f0-9]{32}', version):
        raise ReferenceError('invalid_patent_citation_version', 422)
    if not enabled(config):
        with closing(Store(config)) as store:
            if not store.execute('SELECT number FROM papers WHERE number=%s', (number,)):
                raise ReferenceError('not_found', 404)
        return {'number': number, 'state': 'disabled', 'version': None, 'group': 'patent', 'total': 0, 'expected_total': None,
                'counts': {'patent': None, 'total': None}, 'stored_counts': {'patent': 0, 'total': 0},
                'group_states': {'patent': 'disabled'}, 'source_presence': 'unknown', 'empty_reason': None,
                'checked_at': None, 'last_attempt_at': None, 'next_check_at': None, 'stale': False, 'error': None,
                'offset': offset, 'limit': limit, 'next_offset': None, 'items': []}
    args = ['read', number, '--offset', str(offset), '--limit', str(limit)]
    if version:args += ['--version', version]
    value = call(config, 'read_command', args)
    if value.get('number') != number or not isinstance(value.get('items'), list):
        raise ReferenceError('patent_citations_unavailable', 503)
    fields = ('number','state','version','group','total','expected_total','counts','stored_counts','group_states',
              'source_presence','empty_reason','checked_at','last_attempt_at','next_check_at','stale','error','offset','limit','next_offset','items')
    return {k: v for k, v in value.items() if k in fields}


def call(config, setting, args):
    command = options(config).get(setting)
    if not isinstance(command, list) or not command or any(not isinstance(s, str) or not s for s in command):
        raise ReferenceError('patent_citations_unavailable', 503)
    try:
        result = subprocess.run([*command, 'patent-citations', *args], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=15, check=False)
        value = json.loads(result.stdout)
        from .task_origins import note_queue_result
        note_queue_result('patent_citations', args[1] if len(args)>1 and args[0]=='enqueue' else '', value)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise ReferenceError('patent_citations_unavailable', 503) from None
    if result.returncode:
        code = value.get('code')
        if code == 'worker_busy':raise ReferenceError('worker_busy', 409)
        if code in ('not_found', 'patent_citation_version_not_found'):raise ReferenceError(code, 404)
        raise ReferenceError('patent_citations_unavailable', 503)
    return value


def due(current, refresh=False):
    if current['state'] in ('disabled','queued','fetching'):
        return False
    if refresh or current['state'] == 'missing':
        return True
    value = current.get('next_check_at')
    return not value or datetime.fromisoformat(value.replace('Z','+00:00')) <= datetime.now(timezone.utc)


def enqueue(config, number, refresh=False):
    current = read(config, number)
    if not due(current, refresh):return current
    try:call(config, 'enqueue_command', ['enqueue', number] + (['--retry'] if refresh else []))
    except ReferenceError as error:
        if error.code != 'worker_busy':raise
        for _ in range(3):
            time.sleep(.1);current = read(config, number)
            if not due(current, False):return current
        raise ReferenceError('patent_citations_queue_unavailable', 503) from None
    return read(config, number)


def routes(config, response):
    limiter = SearchRateLimiter(limit=10, interval=60)
    async def listing(request):
        try:
            q = request.query_params
            if set(q)-{'offset','limit','version'}:raise ValueError('invalid query')
            value = await run_in_threadpool(read, config, request.path_params['number'], int(q.get('offset','0')), int(q.get('limit','50')), q.get('version'))
            return response(value)
        except ReferenceError as error:return response({'error':error.code},error.status)
        except ValueError:return response({'error':'invalid_patent_citation_page'},422)
    async def ensure(request):
        try:
            data = await request.json()
            if not isinstance(data,dict) or set(data)-{'refresh'} or not isinstance(data.get('refresh',False),bool):
                return response({'error':'invalid_patent_citation_request'},422)
            current = await run_in_threadpool(read,config,request.path_params['number'])
            if due(current,data.get('refresh',False)):
                if not limiter.allow(request.client.host if request.client else 'unknown'):
                    return response({'error':'rate_limited'},429)
                current = await run_in_threadpool(enqueue,config,request.path_params['number'],data.get('refresh',False))
            return response(current,202 if current['state'] in ('queued','fetching') else 200)
        except ReferenceError as error:return response({'error':error.code},error.status)
        except ValueError:return response({'error':'invalid_patent_citation_request'},422)
    return [Route('/api/papers/{number}/patent-citations',listing),Route('/api/papers/{number}/patent-citations/ensure',ensure,methods=['POST'])]
