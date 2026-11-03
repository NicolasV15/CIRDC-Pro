import json
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from cirdc.web import patent_citations as api
from cirdc.web.app import create_app
from test_web import website as website


def view(**kwargs):
    return {'number': '100', 'state': 'complete', 'version': 'a'*32, 'group': 'patent',
            'total': 1, 'expected_total': 1, 'items': [], 'source_presence': 'present',
            'empty_reason': None, 'next_check_at': (datetime.now(timezone.utc)+timedelta(days=7)).isoformat(), **kwargs}


def test_patents_have_independent_ttl_and_force_respects_inflight():
    for state in ['complete','no_data','unavailable','partial','blocked','failed']:
        assert not api.due(view(state=state))
        assert api.due(view(state=state), True)
        assert api.due(view(state=state,next_check_at='2000-01-01T00:00:00Z'))
    for state in ['queued','fetching','disabled']:assert not api.due(view(state=state), True)


def test_routes_paging_fresh_reuse_and_explicit_update(website, monkeypatch):
    website.web['patent_citations'] = {'enabled': True}
    calls = []
    def read(config, number, offset=0, limit=50, version=None):
        calls.append(('read',number,offset,limit,version));return view()
    def enqueue(config,number,refresh=False):
        calls.append(('enqueue',number,refresh));return view(state='queued')
    monkeypatch.setattr(api,'read',read);monkeypatch.setattr(api,'enqueue',enqueue)
    with TestClient(create_app(website,reader_auth='public')) as client:
        assert client.get('/api/papers/100/patent-citations?offset=2&limit=1&version='+'a'*32).status_code == 200
        assert calls[-1] == ('read','100',2,1,'a'*32)
        assert client.get('/api/papers/100/patent-citations?group=ieee').status_code == 422
        assert client.post('/api/papers/100/patent-citations/ensure',json={}).status_code == 403
        headers = {'Origin':'http://testserver'}
        assert client.post('/api/papers/100/patent-citations/ensure',json={},headers=headers).status_code == 200
        assert not any(v[0]=='enqueue' for v in calls)
        assert client.post('/api/papers/100/patent-citations/ensure',json={'refresh':True},headers=headers).status_code == 202
        assert calls[-1] == ('enqueue','100',True)
        assert client.post('/api/papers/100/patent-citations/ensure',json={'refresh':'yes'},headers=headers).status_code == 422


def test_read_bridge_has_separate_command_and_filters_private_fields(website, monkeypatch):
    website.web['patent_citations'] = {'enabled':True,'read_command':['maintenance']}
    calls = []
    def run(command,**kwargs):
        calls.append(command)
        return type('Result',(),{'returncode':0,'stdout':json.dumps({**view(),'private_profile':'secret'})})()
    monkeypatch.setattr(api.subprocess,'run',run)
    value = api.read(website,'100',offset=2,limit=1,version='a'*32)
    assert 'private_profile' not in value and calls[0][1] == 'patent-citations'
    assert '--group' not in calls[0] and calls[0][-2:] == ['--version','a'*32]
    for kwargs in [{'limit':101},{'offset':-1},{'version':'wrong'}]:
        with pytest.raises(api.ReferenceError):api.read(website,'100',**kwargs)
