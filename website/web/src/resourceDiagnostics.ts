export type ResourceJob={state?:string;kind?:string;availability_state?:string;is_refresh?:boolean;deferred?:boolean;error?:string;unavailable_reason?:string};

export function pdfStateLabel(state:string){
 return ({ready:'PDF 已就绪',queued:'PDF 等待获取',fetching:'正在获取 PDF',unavailable:'已确认不可获取（机构未授权）',failed:'其他待处理异常'} as Record<string,string>)[state]||state;
}

export function refreshLabel(job:ResourceJob){
 if(!job.is_refresh||job.availability_state!=='ready')return null;
 return ['queued','fetching','body_ready'].includes(job.state||'')?'已有 PDF，正在检查更新':job.state==='ready'?'PDF 更新检查完成':'已有 PDF，更新检查未完成';
}

export type PdfRetryTodo={auto_attempts?:number;auto_max_attempts?:number;auto_retry_eligible?:boolean;auto_retry_exhausted?:boolean;next_retry_at?:number|null};
export function pdfRetryState(todo:PdfRetryTodo){
 if(todo.auto_retry_exhausted)return {label:'次数耗尽，待人工处理',nextAt:null};
 if(todo.auto_retry_eligible)return {label:'等待自动重试',nextAt:todo.next_retry_at??null};
 return {label:todo.auto_retry_eligible===false?'待人工处理':'待后续补全',nextAt:null};
}
