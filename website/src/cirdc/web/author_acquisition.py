"""Public author requests use the configured, authenticated writer coordinator."""
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route
import requests
from urllib.parse import urlsplit
from ..author_profiles import identity, AuthorError
from .access import SearchRateLimiter, ENSURE_REQUESTS_PER_MINUTE


def call(config, operation, aid, refresh=False):
    identity(aid)
    setting=config.web.get('authors',{})
    if setting.get('enabled') is not True:return {'state':'disabled'}
    address=urlsplit(setting.get('coordinator',''))
    if address.scheme!='http' or address.hostname not in ('localhost','127.0.0.1'):raise AuthorError('authors_unavailable')
    with requests.Session() as session:
        session.trust_env=False
        reply=session.post(setting['coordinator'].rstrip('/')+'/v1/workers/author_'+operation,
            json={'slot':'0','author_id':aid,'refresh':refresh},
            headers={'Authorization':'Bearer '+setting['token'],'X-CIRDC-Worker':setting['worker_id']},timeout=(3,15))
        value=reply.json()
        if reply.status_code!=200:raise AuthorError('author_not_indexed' if value.get('error')=='author_not_indexed' else 'authors_unavailable')
        return value


def routes(config,response):
    limiter=SearchRateLimiter(limit=ENSURE_REQUESTS_PER_MINUTE,interval=60)
    async def ensure(request):
        try:
            identity(request.path_params['author_id'],request.path_params['source'])
            data=await request.json()
            if not isinstance(data,dict) or set(data)-{'refresh'} or not isinstance(data.get('refresh',False),bool):raise ValueError()
            peer=request.client.host if request.client else 'unknown'
            if not limiter.allow(peer):
                result=response({'error':'rate_limited'},429);result.headers['Retry-After']=str(limiter.retry_after(peer));return result
            job=await run_in_threadpool(call,config,'ensure',request.path_params['author_id'],data.get('refresh',False))
            if job['state']=='disabled':return response({'error':'authors_disabled'},503)
            return response({'acquisition':job},202 if job['state'] in ('queued','fetching') else 200)
        except AuthorError as error:return response({'error':error.code},404 if error.code=='author_not_indexed' else 422 if error.code=='invalid_author_reference' else 503)
        except (ValueError,TypeError):return response({'error':'invalid_author_request'},422)
        except Exception:return response({'error':'authors_unavailable'},503)
    return [Route('/api/author-profiles/{source}/{author_id}/ensure',ensure,methods=['POST'])]
