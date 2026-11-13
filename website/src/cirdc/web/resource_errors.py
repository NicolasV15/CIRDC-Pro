"""Redacted diagnostics in the existing administrator audit history."""
import json
import logging
import re
import traceback


def redacted_exception(error):
    value = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    value = re.sub(r'(?i)\b(?:https?|socks5?)://[^\s\]\)\'\"]+', '[url]', value)
    value = re.sub(r'''(?ix)(?:authorization|cookie|password|passwd|token|secret|api[_-]?key|host|server|user|username|account)\s*[:=]\s*(?:"[^"\n]*"|'[^'\n]*'|[^\n,;]+)''', '[private value]', value)
    value = re.sub(r'(?<!\w)(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?|\b[0-9a-fA-F]*:[0-9a-fA-F:]+:[0-9a-fA-F:]*\b', '[address]', value)
    value = re.sub(r'(?:[A-Za-z]:[\\/]|/)[^\s\'\"<>]+', '[path]', value)
    value = re.sub(r'\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|edu|internal|local|lan)\b', '[host]', value)
    return value[-6000:]


def record_error(error, **context):
    from .auth import Accounts
    value = {**context, 'error': getattr(error, 'code', 'resource_service_unavailable'),
             'exception': redacted_exception(error)}
    try:
        with Accounts().db() as db:
            db.execute('INSERT INTO audit(at,actor,action,target,detail) VALUES(strftime(\'%s\',\'now\'),?,?,?,?)',
                       ('resource-api', 'resource_api_error', context.get('request_id') or context.get('id') or '', json.dumps(value)))
    except Exception:
        logging.getLogger('cirdc.agent').warning('resource_api_audit_unavailable')
    logging.getLogger('cirdc.agent').warning('resource_api_error %s', json.dumps(value))


def diagnostics():
    from .auth import Accounts
    from .agent_requests import RequestStore
    with Accounts().db() as db:
        events = [dict(row) for row in db.execute("SELECT id,at,action,target,detail FROM audit WHERE actor='resource-api' ORDER BY id DESC LIMIT 100")]
    for event in events:
        event['detail'] = json.loads(event['detail'])
    store = RequestStore()
    from contextlib import closing
    with closing(store.db()) as db:
        receipts = [dict(row) for row in db.execute('SELECT id,number,resources,references_json,history,created,updated FROM requests ORDER BY updated DESC LIMIT 100')]
    for receipt in receipts:
        for key in ('resources', 'references_json', 'history'):
            receipt[key] = json.loads(receipt[key])
    return {'events': events, 'requests': receipts}
