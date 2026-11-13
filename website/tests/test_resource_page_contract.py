"""Built reader -> real HTTP Agent API -> delayed provider/receipt recovery."""
import os
from pathlib import Path
import subprocess
import threading
import time

import pytest
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from cirdc.web.app import create_app
from test_agent import agent_site, website  # noqa: F401
from test_agent_clients import serve


@pytest.mark.skipif(os.environ.get('CIRDC_BROWSER')!='1', reason='Set CIRDC_BROWSER=1 with Playwright for built-reader integration')
def test_reader_api_late_receipt_recovery_and_terminal_polling(agent_site, monkeypatch):
    config,provider,resources=agent_site
    release,entered=threading.Event(),threading.Event()
    original=provider.agent_ensure
    def delayed(aid,kind,peer,retry=False):
        entered.set()
        assert release.wait(10)
        value=original(aid,kind,peer,retry)
        provider.current[kind]['retry_after_seconds']=.05
        return value
    provider.agent_ensure=delayed
    provider.links=lambda numbers:{str(n):[{'kind':'document','href':f'/api/content/{n}'}] for n in numbers}
    counters={'read':0,'receipts':0}
    def status(request):
        counters['read']+=1
        state=provider.current['content']
        result={'state':state['state'],'job':state.get('jobs',[None])[-1] if state.get('jobs') else None,'retry_after_seconds':.05}
        result.update({k:state[k] for k in ['next_action','next_retry_at','retry_attempts','max_retry_attempts'] if k in state})
        if entered.is_set():release.set()
        return JSONResponse(result)
    def phase(request):
        name=request.path_params['phase']
        if name in ('wait','stop'):
            provider.finish('content','failed')
            provider.current['content'].update(next_action='wait' if name=='wait' else 'contact_administrator',
                retry_attempts=1 if name=='wait' else 10,max_retry_attempts=10,next_retry_at=time.time()+60 if name=='wait' else None)
        return JSONResponse({'calls':len(provider.calls),'read':counters['read']})
    provider.routes=lambda:[Route('/api/content/{number}',status),Route('/fixture/{phase}',phase)]
    monkeypatch.setattr('cirdc.web.agent.OVERHEAD',.2)
    script=Path(__file__).parents[1]/'web/tests/resourceApiLinked.browser.cjs'
    with serve(create_app(config,resource_providers=resources,reader_auth='public')) as origin:
        try:
            result=subprocess.run(['node',str(script)],env={**os.environ,'CIRDC_LINKED_ORIGIN':origin},capture_output=True,text=True,timeout=40)
            assert result.returncode==0,result.stdout+result.stderr
            assert len(provider.calls)==1
        finally:release.set()
