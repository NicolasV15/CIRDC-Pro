"""Associate accepted reader requests with opaque, durable queue identities."""
from contextvars import ContextVar
import ipaddress
import json
import logging
import os
import re
import subprocess
import time
import uuid

from starlette.concurrency import run_in_threadpool

CURRENT = ContextVar('reader_task_request', default=None)
KINDS = {'metadata', 'references', 'citations', 'patent_citations'}


def identifier(value):
    value = str(value or '')
    return value if re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value) else None


def note_queue_result(kind, number, value):
    """Keep only queue identity hints; never retain payloads or subprocess output."""
    context = CURRENT.get()
    if not context or context['kind'] != kind or context['paper'] != number or not isinstance(value, dict):
        return
    run = identifier(value.get('run_id'))
    if run and isinstance(value.get('queued'), list) and number in value['queued']:
        context['created_run'] = run


def request_kind(scope):
    if scope.get('type') != 'http' or scope.get('method') != 'POST':
        return None, None
    found = re.fullmatch(r'/api/papers/([0-9]{1,64})/(metadata|references|citations|patent-citations)/ensure', scope.get('path', ''))
    agent = re.fullmatch(r'/api/agent/v1/papers/([0-9]{1,64})/ensure', scope.get('path', ''))
    if agent:
        return 'agent_resources', agent[1]
    return (found[2].replace('-', '_'), found[1]) if found else (None, None)


def lookup(command, kind, paper):
    if not command or kind not in KINDS:
        return []
    try:
        run = subprocess.run(command, input=json.dumps({'kind': kind, 'paper': paper}),
                             capture_output=True, text=True, timeout=2)
        if run.returncode or len(run.stdout) > 16384:
            return []
        value = json.loads(run.stdout)
        rows = value.get('tasks', []) if value.get('available') is True else []
        return [v for v in rows[:8] if isinstance(v, dict) and v.get('paper') == paper
                and identifier(v.get('id')) and identifier(v.get('run_id')) and identifier(v.get('kind'))]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def response_jobs(value, paper):
    """Only explicit job references returned to this article's accepted request."""
    if not isinstance(value, dict) or str(value.get('number', paper)) != paper:
        return []
    out = []
    job = value.get('job')
    if isinstance(job, dict):
        task = job.get('task') if isinstance(job.get('task'), dict) else job
        task_id = identifier(task.get('id') or task.get('task_id'))
        kind = identifier(task.get('kind'))
        run = identifier(task.get('run_id'))
        if task_id and kind:
            out.append({'queue': 'metadata' if run else 'resource', 'kind': kind,
                        'task_id': task_id, 'run_id': run or '', 'binding': 'response_job'})
    for job in value.get('jobs', []) if isinstance(value.get('jobs'), list) else []:
        if isinstance(job, dict):
            out.extend(response_jobs({'number': paper, 'job': job}, paper))
    # Resource adapters may return an explicit subsidiary queue result.
    for child in value.values():
        if isinstance(child, dict):
            out.extend(response_jobs(child, paper))
    return out[:8]


def resolve_links(context, before, after, value):
    links = response_jobs(value, context['paper']) if context['kind'] not in KINDS else []
    if context['kind'] in KINDS:
        raw_job = value.get('job') if isinstance(value, dict) else None
        if context['kind']=='metadata' and isinstance(raw_job, dict):
            task_id = identifier(raw_job.get('id') or raw_job.get('task_id'))
            run_id = identifier(raw_job.get('run_id'))
            if task_id:
                links.extend({'queue':'metadata','kind':r['kind'],'task_id':str(r['id']),'run_id':r['run_id'],'binding':'response_job'}
                             for r in after if str(r['id'])==task_id and (not run_id or r['run_id']==run_id))
        # A returned run identifies a newly queued task even if it finishes quickly.
        if context.get('created_run'):
            selected = [r for r in after if r['run_id'] == context['created_run']]
            basis = 'created_run'
        else:
            # Do not guess from article/time: the same active identity must be
            # present both before and after a request that joins existing work.
            previous = {(str(r['id']), r['run_id'], r['kind']) for r in before if r.get('state') in ('pending', 'running')}
            selected = [r for r in after if (str(r['id']), r['run_id'], r['kind']) in previous]
            basis = 'stable_existing'
        if context['kind']=='metadata' and not selected and isinstance(value.get('job'),dict):
            # The configured resolver can attest the canonical pointer used by
            # an API that returns state without exposing its queue identity.
            selected=[r for r in after if r.get('canonical') is True]
            basis='canonical_queue'
        if context['kind'] == 'metadata' and len(selected) != 1:
            selected = []
        links.extend({'queue': 'metadata', 'kind': r['kind'], 'task_id': str(r['id']),
                      'run_id': r['run_id'], 'binding': basis} for r in selected)
    return list({(v['queue'], v['kind'], v['task_id'], v['run_id']): v for v in links}.values())


class TaskSourceRecords:
    def __init__(self, app, path):
        from .visits import VisitStore
        self.app, self.store = app, None
        self.command = []
        try:
            command = json.loads(os.environ.get('CIRDC_WEB_TASK_RESOLVER', '[]'))
            if isinstance(command, list) and all(isinstance(v, str) and v for v in command):
                self.command = command
            self.store = VisitStore(path)
        except Exception:
            logging.getLogger('cirdc.visits').warning('Reader task association unavailable')

    async def __call__(self, scope, receive, send):
        if not self.store or scope.get('type') != 'http' or scope.get('method') != 'POST':
            return await self.app(scope, receive, send)
        try:
            address = ipaddress.ip_address(scope['client'][0])
            ip = str(address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped else address)
        except (KeyError, TypeError, ValueError):
            return await self.app(scope, receive, send)
        kind, paper = request_kind(scope)
        context = {'id': uuid.uuid4().hex, 'ip': ip, 'at': time.time(), 'kind': kind, 'paper': paper}
        before = await run_in_threadpool(lookup, self.command, kind, paper) if kind else []
        token = CURRENT.set(context)
        status, content_type, body, overflow = None, '', bytearray(), False
        async def capture(message):
            nonlocal status, content_type, overflow
            if message['type'] == 'http.response.start':
                status = message['status']
                context['response_status'] = status
                content_type = next((v.decode('latin1') for k, v in message.get('headers', []) if k.lower() == b'content-type'), '')
            if message['type'] == 'http.response.body' and 'application/json' in content_type:
                chunk = message.get('body', b'')
                if len(body) + len(chunk) <= 65536 and not overflow:
                    body.extend(chunk)
                else:
                    overflow = True; body.clear()
            await send(message)
        try:
            await self.app(scope, receive, capture)
            try:
                await self.save(scope, context, before, status, content_type, body, overflow)
            except Exception:
                logging.getLogger('cirdc.visits').warning('Reader task association could not be saved')
        finally:
            CURRENT.reset(token)

    async def save(self, scope, context, before, status, content_type, body, overflow):
        kind, paper = context['kind'], context['paper']
        if status not in (200, 202) or overflow or 'application/json' not in content_type:
            return
        paper = paper or str(scope.get('path_params', {}).get('number', ''))
        if not re.fullmatch('[0-9]{1,64}', paper) or scope.get('state', {}).get('content_node'):
            return
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError):
            return
        context['paper'] = paper
        after = await run_in_threadpool(lookup, self.command, kind, paper) if kind else []
        links = resolve_links(context, before, after, value)
        if not kind and not links:
            return
        context.update(kind=kind or links[0]['kind'], status=status,
                       outcome='created' if context.get('created_run') and links else 'associated' if links else 'unresolved')
        await run_in_threadpool(self.store.record_task, context, links)


def enable_task_origins(app, interface):
    path = os.environ.get('CIRDC_WEB_VISITS_FILE')
    if interface == 'reader' and path:
        app.add_middleware(TaskSourceRecords, path=path)
