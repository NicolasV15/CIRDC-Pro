import {errorMessage} from './i18n';

let csrf='';
export function setCsrf(value:string|undefined){csrf=value||'';}
export async function api(path:string,method='GET',data?:unknown,signal?:AbortSignal){
 const response=await fetch(path,{method,signal,credentials:'same-origin',headers:{'Content-Type':'application/json',...(method!=='GET'?{'X-CSRF-Token':csrf}:{})},...(data!==undefined?{body:JSON.stringify(data)}:{})});
 const result=await response.json();
 if(response.status===401&&!path.startsWith('/api/auth/'))window.dispatchEvent(new Event('cirdc-auth-expired'));
 if(!response.ok)throw new Error(errorMessage(result));
 return result;
}
