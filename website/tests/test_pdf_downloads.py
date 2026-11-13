"""PDF outputs share a signature check; acquisition status is independent."""
import asyncio
import importlib.util
import io
from email.message import Message

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from cirdc.web.app import create_app
from cirdc.web.agent import PREFIX
from test_agent import agent_site, client_for, ensure, website
from test_agent_clients import serve, client_script


def test_api_checks_signature_once_for_each_output_and_preserves_ready_receipt(agent_site,monkeypatch):
    import cirdc.web.agent as module
    original=module.pdf_file_stat;checks=[]
    def checked(path,**kwargs):
        checks.append(kwargs['signature']);return original(path,**kwargs)
    monkeypatch.setattr(module,'pdf_file_stat',checked)
    provider=agent_site[1];path=provider.root/'original.pdf'
    with client_for(agent_site) as client:
        receipt=ensure(client,['pdf']).json();provider.finish('pdf')
        for method,headers,status in [('GET',{},200),('HEAD',{},200),('GET',{'Range':'bytes=0-7'},206)]:
            before=len(checks)
            response=client.request(method,PREFIX+'/papers/100/pdf',headers=headers)
            assert response.status_code==status and len(checks)==before+1
            assert response.headers['content-type']=='application/pdf'
        path.write_bytes(b'not a PDF but still a readable local file')
        assert client.get(PREFIX+'/papers/100/pdf').status_code==503
        assert client.get(receipt['status_url']).json()['complete']
        assert provider.current['pdf']['state']=='ready'
        path.unlink()
        assert client.head(PREFIX+'/papers/100/pdf').status_code==503


def test_cli_output_download_uses_one_get_and_accepts_server_pdf_header(agent_site,client_script,tmp_path,monkeypatch):
    import subprocess,sys
    config,provider,resources=agent_site;provider.finish('pdf')
    payload=b'leading bytes\n%PDF-1.4\nfixture\n%%EOF'
    (provider.root/'original.pdf').write_bytes(payload)
    app=create_app(config,resource_providers=resources);methods=[]
    async def observe(request,call_next):
        if request.url.path==PREFIX+'/papers/100/pdf':methods.append(request.method)
        return await call_next(request)
    from starlette.middleware.base import BaseHTTPMiddleware
    app.add_middleware(BaseHTTPMiddleware,dispatch=observe)
    with serve(app) as origin:
        target=tmp_path/'download.pdf'
        result=subprocess.run([sys.executable,'-I',str(client_script),'--base-url',origin,
            'pdf','100','--wait-seconds','0','--output',str(target)],capture_output=True,text=True,timeout=15)
        assert result.returncode==0,result.stdout+result.stderr
        assert target.read_bytes()==payload and methods==['GET']


def test_cli_pdf_descriptor_failure_keeps_completed_acquisition(agent_site,client_script,tmp_path):
    import subprocess,sys,json
    config,provider,resources=agent_site;provider.finish('pdf')
    (provider.root/'original.pdf').write_bytes(b'local bytes without a PDF signature')
    with serve(create_app(config,resource_providers=resources)) as origin:
        result=subprocess.run([sys.executable,'-I',str(client_script),'--base-url',origin,
            'pdf','100','--wait-seconds','0'],capture_output=True,text=True,timeout=15)
        assert result.returncode==0,result.stdout+result.stderr
        value=json.loads(result.stdout)
        assert value['complete'] and value['resources']['pdf']['state']=='ready'
        assert value['download_error']['http_status']==503


@pytest.mark.parametrize('mime,length,error',[('text/html','20','invalid_pdf_response'),('application/pdf','99','incomplete_download')])
def test_client_download_validates_actual_response_and_removes_partial_file(client_script,tmp_path,monkeypatch,mime,length,error):
    spec=importlib.util.spec_from_file_location('pdf_client',client_script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Reply(io.BytesIO):
        headers=Message()
    response=Reply(b'%PDF-1.4\nfixture')
    response.headers['Content-Type']=mime;response.headers['Content-Length']=length
    methods=[]
    def fetch(request,**kwargs):methods.append(request.get_method());return response
    monkeypatch.setattr(module,'urlopen',fetch)
    with pytest.raises(module.ClientError) as exc:
        module.Client('http://example.test').download('100',tmp_path/'output.pdf')
    assert exc.value.value['error']==error and methods==['GET']
    assert not (tmp_path/'output.pdf').exists()
    assert not list(tmp_path.glob('tmp*'))


def test_mcp_reuses_download_response_without_overriding_acquisition_success(agent_site):
    config,provider,resources=agent_site;provider.finish('pdf')
    with serve(create_app(config,resource_providers=resources)) as origin:
        async def exercise():
            async with httpx.AsyncClient(trust_env=False) as http,streamable_http_client(
                    origin+PREFIX+'/mcp',http_client=http) as (read,write,_):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    value=(await session.call_tool('get_pdf',{'number':'100','wait_seconds':0})).structuredContent
                    assert value['complete'] and value['download']['bytes']==(provider.root/'original.pdf').stat().st_size
                    assert value['download']['media_type']=='application/pdf'
                    (provider.root/'original.pdf').write_bytes(b'no PDF signature here')
                    failure=(await session.call_tool('get_pdf',{'number':'100','wait_seconds':0})).structuredContent
                    assert failure['complete'] and failure['resources']['pdf']['state']=='ready'
                    assert failure['download_error']['http_status']==503
        asyncio.run(exercise())
