import type {BatchResource,LoadedPaper} from './paperBatch';
export type FileStatus='ready'|'not_available'|'file_missing'|'file_unavailable'|'unverified';
export type FileCheck={number:string;status:FileStatus;resource?:BatchResource};
export const fileStatusLabels:Record<FileStatus,string>={ready:'文件已核实，可下载',not_available:'未关联 PDF',file_missing:'关联文件不存在',file_unavailable:'文件暂不可读取',unverified:'无法核实 PDF，请重试'};
export function safeResourceHref(value:unknown):string|null{
 return typeof value==='string'&&/^\/api\/resources\/[^\s\\?#]+$/.test(value)?value:null;
}
export type HeadReader=(path:string)=>Promise<{status:number;headers:{get:(name:string)=>string|null}}>;

/** Bound each HEAD request and cancel it when its dialog closes. */
export async function readPdfHead(path:string,signal:AbortSignal,timeoutMs=15000):Promise<Response>{
 const controller=new AbortController(),abort=()=>controller.abort();
 signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();
 const timer=setTimeout(abort,timeoutMs);
 try{return await fetch(path,{method:'HEAD',credentials:'same-origin',cache:'no-store',signal:controller.signal});}
 finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
}

/** An advertised link is a hint. Check the actual file, without downloading its body. */
export async function checkDownloads(items:LoadedPaper[],head:HeadReader,progress:(done:number)=>void=()=>{},cancelled:()=>boolean=()=>false):Promise<FileCheck[]>{
 const checks=new Map<string,FileCheck>();let cursor=0,done=0;
 await Promise.all(Array.from({length:Math.min(3,items.length)},async()=>{
  while(!cancelled()){
   const item=items[cursor++];if(!item)return;
   const resource=item.paper.resources?.find(r=>r.kind!=='document'&&r.media_type==='application/pdf'&&safeResourceHref(r.href)&&safeResourceHref(r.archive_prepare_href));
   let status:FileStatus=item.paper.resource_notice?'unverified':'not_available';
   if(resource){
    try{
     const response=await head(resource.href),type=response.headers.get('content-type')?.split(';')[0].trim().toLowerCase(),length=response.headers.get('content-length');
     status=response.status===200&&type==='application/pdf'&&!!length&&/^\d+$/.test(length)&&Number(length)>0?'ready':response.status===404||response.status===410?'file_missing':response.status>=500?'file_unavailable':'unverified';
    }catch{status='file_unavailable';}
   }
   checks.set(item.number,{number:item.number,status,resource});done++;if(!cancelled())progress(done);
  }
 }));
 return items.flatMap(item=>checks.has(item.number)?[checks.get(item.number)!]:[]);
}

export type DownloadName={number:string;filename:string};
export type DownloadGroup={endpoint:string;items:DownloadName[];ready:number;key:string};
/** Respect each archive request's 100-item bound without truncating loaded selections. */
export function downloadGroups(names:DownloadName[],checks:FileCheck[]):DownloadGroup[]{
 const byNumber=new Map(checks.map(check=>[check.number,check])),groups:DownloadGroup[]=[];
 for(let i=0;i<names.length;i+=100){
  const batch=names.slice(i,i+100),endpoints=new Set(batch.map(item=>byNumber.get(item.number)).filter(check=>check?.status==='ready').map(check=>check!.resource!.archive_prepare_href!));
  for(const endpoint of endpoints){
   const items=batch.filter(item=>{const check=byNumber.get(item.number);return check?.status==='ready'&&check.resource?.archive_prepare_href===endpoint;});
   const ready=items.filter(item=>byNumber.get(item.number)?.status==='ready').length;
   groups.push({endpoint,items,ready,key:endpoint+':'+items[0].number});
  }
 }
 return groups;
}
