"""Bounded single-paper maintenance requests; reader credentials remain read-only."""
import re
from urllib.parse import urlsplit
import requests
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route
from .access import ENSURE_REQUESTS_PER_MINUTE, SearchRateLimiter

def options(config):
    value=config.web.get("maintenance",{})
    return value if isinstance(value,dict) else {}

def enabled(config):return options(config).get("enabled") is True

def call(config,operation,number=None):
    setting=options(config)
    if not enabled(config):return {"state":"disabled"}
    base=setting.get("coordinator","")
    address=urlsplit(base)
    if address.scheme!="http" or address.hostname not in ("127.0.0.1","localhost"):
        raise ValueError("maintenance_unavailable")
    headers={"Authorization":"Bearer "+setting.get("token",""),"X-CIRDC-Worker":setting.get("worker_id","")}
    with requests.Session() as session:
        session.trust_env=False
        if operation=="status":
            response=session.get(base.rstrip("/")+"/v1/status",timeout=(3,15))
            response.raise_for_status();value=response.json()
            runtime=value.get("runtime") or {}
            cluster=value.get("cluster") or {}
            return {"service":(value.get("service") or {}).get("status"),
                    "updated":runtime.get("updated"),"jobs":runtime.get("jobs",{}),
                    "pending_results":runtime.get("pending_results"),"requests":runtime.get("requests",{}),
                    "workers":cluster.get("workers",[]),"exits":cluster.get("exits",[]),"dispatch":cluster.get("tasks",{})}
        if not isinstance(number,str) or not re.fullmatch("[0-9]{1,64}",number):raise ValueError("invalid_number")
        response=session.post(base.rstrip("/")+"/v1/workers/"+operation,json={"number":number},headers=headers,timeout=(3,25))
        if response.status_code!=200:raise ValueError("maintenance_unavailable")
        value=response.json()
        return {k:value[k] for k in ("number","abstract_state","keywords_state","job","updated_at") if k in value}

def routes(config,response,interface="reader"):
    limiter=SearchRateLimiter(limit=ENSURE_REQUESTS_PER_MINUTE,interval=60)
    async def status(request):
        try:return response(await run_in_threadpool(call,config,"status"))
        except Exception:return response({"error":"maintenance_unavailable"},503)
    async def single(request):
        if not enabled(config):return response({"state":"disabled"})
        operation="metadata_ensure" if request.method=="POST" else "metadata_read"
        if request.method=="POST":
            peer=request.client.host if request.client else "unknown"
            if not limiter.allow(peer):return response({"error":"rate_limited"},429)
        try:return response(await run_in_threadpool(call,config,operation,request.path_params["number"]))
        except Exception:return response({"error":"maintenance_unavailable"},503)
    if interface=="admin":
        return [Route("/api/admin/maintenance",status)]
    return [Route("/api/papers/{number}/metadata/status",single),
            Route("/api/papers/{number}/metadata/ensure",single,methods=["POST"])]
