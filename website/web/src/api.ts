import {errorMessage} from './i18n';

let csrf='';
export class ApiError extends Error {
 value:Record<string,any>;status:number;
 constructor(value:Record<string,any>,status=0){super(errorMessage(value));this.value=value;this.status=status;}
}
export function setCsrf(value:string|undefined){csrf=value||'';}
export async function api(path:string,method='GET',data?:unknown,signal?:AbortSignal){
 const bounded=/^\/api\/(?:content\/|agent\/v1\/)/.test(path),controller=new AbortController();
 const abort=()=>controller.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
 const timer=bounded?setTimeout(abort,12000):undefined;
 try {
 const response=await fetch(path,{method,signal:bounded?controller.signal:signal,credentials:'same-origin',headers:{'Content-Type':'application/json',...(method!=='GET'?{'X-CSRF-Token':csrf}:{})},...(data!==undefined?{body:JSON.stringify(data)}:{})});
 let result;try{result=await response.json();}catch{throw new ApiError({error:'invalid_response',next_action:response.status>=500?'wait':'stop',retry_after_seconds:5,...(method==='POST'?{accepted:null}:{})},response.status);}
 if(response.status===401&&!path.startsWith('/api/auth/'))window.dispatchEvent(new Event('cirdc-auth-expired'));
 if(!response.ok)throw new ApiError({next_action:[429,503].includes(response.status)?'wait':'stop',...result,...(!result.retry_after_seconds&&response.headers.get('Retry-After')?{retry_after_seconds:Number(response.headers.get('Retry-After'))}:{})},response.status);
 return result;
 }catch(error){if(error instanceof ApiError)throw error;if(signal?.aborted)throw error;throw new ApiError({error:'connection_failed',reason:controller.signal.aborted?'request_timeout':'connection_failed',next_action:'wait',retry_after_seconds:5,...(method==='POST'?{accepted:null}:{})});}
 finally{if(timer)clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
