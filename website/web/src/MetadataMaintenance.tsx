import {useEffect,useRef,useState} from 'react';
import {t} from './i18n';
type Fetcher=(path:string,method?:string,data?:unknown)=>Promise<any>;
export default function MetadataMaintenance({number,fetcher,onReady}:{number:string;fetcher:Fetcher;onReady:()=>void}){
 const [value,setValue]=useState<any>(),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const ready=useRef(onReady);ready.current=onReady;
 useEffect(()=>{
  let active=true,timer:ReturnType<typeof setTimeout>|undefined,wasPending=false;
  async function poll(){
   try{
    const data=await fetcher('/api/papers/'+encodeURIComponent(number)+'/metadata/status');
    if(!active)return;
    setValue(data);
    const pending=['pending','running'].includes(data.job?.status);
    if(wasPending&&!pending&&data.job?.status==='done')ready.current();
    wasPending=pending;
    if(pending)timer=setTimeout(()=>void poll(),3000);
   }catch{if(active)setError(t('暂时无法读取补全状态'));}
  }
  void poll();return()=>{active=false;if(timer)clearTimeout(timer);};
 },[number,fetcher,busy]);
 if(!value||value.state==='disabled')return error?<p className="hint">{error}</p>:null;
 const labels:Record<string,string>={complete:'已获取',no_data:'来源未提供',pending:'待补全',failed:'获取失败',blocked:'访问受限',running:'正在获取',done:'已完成'};
 const waiting=value.job?.status==='running'||(value.job?.status==='pending'&&value.job?.foreground);
 const missing=['abstract_state','keywords_state'].some(key=>!['complete','no_data'].includes(value[key]));
 async function ensure(){
  setBusy(true);setError('');
  try{setValue(await fetcher('/api/papers/'+encodeURIComponent(number)+'/metadata/ensure','POST',{}));}
  catch{setError(t('暂时无法提交补全请求'));}
  finally{setBusy(false);}
 }
 return <div className="hint metadata-maintenance" aria-live="polite">
  <span>{t('摘要')}：{t(labels[value.abstract_state]||'待补全')} · {t('关键词')}：{t(labels[value.keywords_state]||'待补全')}</span>
  {missing&&<button type="button" disabled={busy||waiting||['failed','blocked'].includes(value.job?.status)} onClick={()=>void ensure()}>
   {t(waiting?'已排队补全':value.job?.status==='pending'?'优先补全':'获取完整元数据')}</button>}
  {value.job?.status&&<span> · {t(labels[value.job.status]||'待补全')}</span>}
  {value.updated_at&&<span> · {t("记录更新")}：{value.updated_at}</span>}
  {error&&<span role="alert">{error}</span>}
 </div>;
}
