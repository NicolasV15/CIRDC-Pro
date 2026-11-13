// Recovery reads first. Ordinary ensure may acquire missing data or join active work.
export type Feedback={kind?:string;state?:string;phase?:string;next_action?:string;reason?:string;error?:string;message?:string;accepted?:boolean|null;retry_after_seconds?:number;next_retry_at?:number|null;retry_attempts?:number;max_retry_attempts?:number;request_id?:string;status_url?:string;job?:{kind?:string;state?:string;error?:string};pdf_acquisition?:{state?:string;job?:{kind?:string;state?:string;error?:string}};document?:unknown};
export function terminal(value?:Feedback){return ['stop','contact_administrator'].includes(value?.next_action||'')||value?.state==='unavailable';}
export function queryDelay(value?:Feedback){const seconds=value?.retry_after_seconds;return (typeof seconds==='number'&&Number.isFinite(seconds)&&seconds>0?seconds:2)*1000;}
export function recoveryLabel(value?:Feedback){
 if(value?.next_action==='contact_administrator')return '需要管理员处理';
 if(value?.state==='unavailable')return '已确认不可获取';
 if(value?.next_action==='stop')return '获取已停止';
 if(value?.state==='ready')return '';
 const phase=value?.phase?.split(':').pop();
 const kind=value?.phase?.includes(':')?value.phase.split(':')[0]:value?.job?.kind||value?.kind;
 if(value?.next_action==='wait'&&value.next_retry_at!=null)return '等待自动重试';
 if(phase==='retry_wait'||phase==='assets_retry_wait')return '等待任务状态更新';
 if(phase==='downloading')return '正在下载 PDF';
 if(['uploading','publishing','registering'].includes(phase||''))return '正在保存 PDF';
 if(phase==='waiting_node')return '等待下载服务就绪';
 if(phase==='conversion_pending')return 'PDF 已获取，等待生成正文';
 const active=['pending','queued','fetching','body_ready'];
 const state=active.includes(phase||'')?phase:value?.job?.state||value?.state;
 if(kind==='pdf_parse'){
  if(state==='queued'||state==='pending')return 'PDF 已获取，等待生成正文';
  if(state==='fetching')return 'PDF 已获取，正在生成正文';
 }
 if(kind==='ieee_pdf'&&state==='fetching')return '正在下载 PDF';
 if(active.includes(state||''))return state==='queued'?'任务已排队':state==='body_ready'?'正文已就绪，正在补齐图片':'任务处理中';
 if(value?.next_action==='wait')return '等待任务状态更新';
 return '';
}
export function failureReason(value?:Feedback){
 const job=['failed','partial','unavailable'].includes(value?.job?.state||value?.state||'')?value?.job:value?.pdf_acquisition?.job;
 const code=(['failed','partial','unavailable'].includes(job?.state||value?.state||'')?job?.error:undefined)||value?.reason||value?.error;
 return ({network_error:'获取时网络连接失败',access_restricted:'来源暂时限制访问',access_denied:'来源拒绝访问',rate_limited:'请求过于频繁，服务繁忙',capacity_limited:'请求容量已满，服务繁忙',source_route_mismatch:'执行节点的网络出口校验未通过',source_route_unavailable:'执行节点的网络出口暂不可用',source_route_not_configured:'执行节点尚未配置网络出口',pdf_storage_unavailable:'PDF 存储暂不可用',pdf_service_not_configured:'PDF 转换服务尚未配置',parse_failed:'正文解析未完成',invalid_pdf:'取得的 PDF 文件无效',assets_incomplete:'部分图片未能取得',provider_not_configured:'资源服务尚未配置'} as Record<string,string>)[code||'']||(['failed','partial'].includes(value?.job?.state||value?.state||'')?'获取未完成，原因尚未确认':'');
}
export function requestLabel(value?:Feedback){
 if(!value)return '';
 if(value.request_id&&terminal(value))return '回执查询未完成，已停止自动查询';
 if(value.request_id)return '已取得回执，将继续查询原请求';
 if(value.accepted===null)return '接口未及时返回，是否已受理尚未确认';
 if(value.accepted===false)return '本次请求未受理';
 return ['hook_timeout','request_timeout','request_deadline_exceeded'].includes(value.reason||'')?'接口查询超时，后台任务状态尚未确认':'接口暂不可用，后台任务状态尚未确认';
}
type API=(path:string,method?:string,data?:unknown)=>Promise<any>;
export class ResourceFlow {
 receipt='';failure?:Feedback;recover=false;closed=false;lastValue:any;
 href:string;kind:'content'|'pdf';api:API;
 constructor(href:string,kind:'content'|'pdf',api:API){
  this.href=href;this.kind=kind;this.api=api;
  try{const saved=sessionStorage.getItem('cirdc.receipt:'+kind+':'+href);if(saved&&/^\/api\/agent\/v1\/requests\/[a-f0-9]{32}$/.test(saved))this.receipt=saved;}catch{/* Storage is optional. */}
 }
 private remember(value:any){
  if(value.request_id&&/^[a-f0-9]{32}$/.test(value.request_id)){
   this.receipt='/api/agent/v1/requests/'+value.request_id;
   try{sessionStorage.setItem('cirdc.receipt:'+this.kind+':'+this.href,this.receipt);}catch{/* Storage is optional. */}
  }
 }
 private failed(error:any,submitting=false){
  this.failure={...(error?.value||{error:'connection_failed',next_action:'wait',retry_after_seconds:5}),...(submitting&&(!error?.value||!Object.hasOwn(error.value,'accepted'))?{accepted:null}:{})};
  if(this.receipt)this.failure={...this.failure,request_id:this.receipt.split('/').pop()};
  this.remember(this.failure);if(submitting||!this.receipt&&this.failure?.next_action==='wait')this.recover=true;
  throw error;
 }
 async submit(retry=false,automatic=false){
  const number=this.href.match(/\/content\/([0-9]+)/)?.[1];if(!number)throw Error('Invalid resource URL');
  let clientId='browser';
  try{clientId=localStorage.getItem('cirdc.client-id')||crypto.randomUUID();localStorage.setItem('cirdc.client-id',clientId);}catch{/* Optional persistence. */}
  try{const response=await this.api('/api/agent/v1/papers/'+number+'/ensure','POST',{resources:[this.kind],wait_seconds:0,automatic,client_id:clientId,channel:'browser'});this.remember(response);this.failure=undefined;this.recover=false;return response;}
  catch(error){return this.failed(error,true);}
 }
 async read():Promise<any>{
  if(this.closed)return;
  let status:any;
  try{
   if(this.receipt){status=await this.api(this.receipt);this.remember(status);}
   const resource=status?.resources?.[this.kind];
   let value:any;
   try{value=await this.api(this.href);}catch(error:any){
    if(resource&&terminal(resource)){
     this.failure={...(error?.value||{}),next_action:'stop',request_id:this.receipt.split('/').pop()};
     return {...this.lastValue,...resource};
    }
    throw error;
   }
   this.failure=undefined;
   if(this.recover&&!this.receipt){
    this.recover=false;
    const active=['pending','queued','fetching','body_ready'].includes(value.job?.state||value.state);
    if(!terminal(value)&&!value.document&&(!value.next_action||active)&&(['missing','unregistered'].includes(value.state)||active)){
     // Ordinary ensure joins confirmed active work and returns its saved receipt.
     await this.submit(false);return this.read();
    }
   }
   if(resource)for(const key of ['next_action','next_retry_at','retry_after_seconds','retry_attempts','max_retry_attempts','reason','phase'])if(resource[key]!==undefined)value[key]=resource[key];
   this.lastValue=value;return value;
  }catch(error){return this.failed(error);}
 }
}
