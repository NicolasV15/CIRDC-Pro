import {useEffect,useRef,useState} from 'react';
import {t} from './i18n';
import Icon from './Icon';
import {ResourceFlow,queryDelay,terminal,recoveryLabel,type Feedback} from './resourceRecovery';
import {ResourceFeedback} from './ResourceFeedback';
import './pdfAcquisition.css';
import {PaperPdfLink} from './PaperResourceLinks';
type API=(path:string,method?:string,data?:unknown)=>Promise<any>;
export function PdfAcquisition({href,api,auto=false}:{href:string;api:API;auto?:boolean}){
 const [value,setValue]=useState<any>(),[requestFailure,setRequestFailure]=useState<Feedback>(),[busy,setBusy]=useState(false);
 const flow=useRef<ResourceFlow|null>(null),autoSent=useRef(false),read=useRef<(delay?:number)=>Promise<void>>(async()=>{});
 useEffect(()=>{
  const current=new ResourceFlow(href,'pdf',api);flow.current=current;autoSent.current=false;
  setValue(undefined);setRequestFailure(undefined);setBusy(false);
  let timer:ReturnType<typeof setTimeout>|undefined;
  function schedule(delay:number){if(!current.closed)timer=setTimeout(()=>void poll(),delay);}
  async function poll(){try{
   const v=await current.read();if(current.closed)return;setValue(v);setRequestFailure(current.failure);
   if(!terminal(v)&&(v.next_action==='wait'||['pending','queued','fetching'].includes(v.state)))schedule(queryDelay(v));
  }catch{if(!current.closed){setRequestFailure(current.failure);if(!terminal(current.failure)&&current.failure?.next_action==='wait')schedule(queryDelay(current.failure));}}}
  read.current=async(delay=0)=>{if(timer)clearTimeout(timer);if(delay)schedule(delay);else await poll();};void poll();
  return()=>{current.closed=true;if(timer)clearTimeout(timer);};
 },[href,api]);
 async function acquire(retry=false,automatic=false){
  const current=flow.current;if(!current)return;setBusy(true);setRequestFailure(undefined);
  try{await current.submit(retry,automatic);}catch{if(!current.closed)setRequestFailure(current.failure);}
  finally{if(!current.closed){setBusy(false);if(!terminal(current.failure))await read.current(current.failure?queryDelay(current.failure):0);}}
 }
 useEffect(()=>{
  if(!auto||!value||autoSent.current||requestFailure)return;
  autoSent.current=true;
  if(value.next_action||value.deferred||!['missing','unregistered'].includes(value.state))return;
  void acquire(false,true);
 },[auto,value,requestFailure]);
 const backgroundPending=value?.state==='pending'&&value?.foreground===false;
 const active=busy||!backgroundPending&&(value?.next_action==='wait'||['pending','queued','fetching'].includes(value?.state)||requestFailure?.next_action==='wait');
 if(value?.state==='ready')return <><PaperPdfLink href={value.reader_url}/>{requestFailure&&<ResourceFeedback request={requestFailure}/>}</>;
 const label=recoveryLabel(value);
 return <span className="pdf-acquisition">
  {terminal(value)||terminal(requestFailure)?<span className="hint">{t(value?.state==='unavailable'?(value.unavailable_reason==='institution_not_licensed'?'无可获取 PDF（机构未授权）':'无可获取 PDF'):label||'获取已停止')}</span>:<button type="button" className="detail-pdf-trigger" disabled={active} aria-busy={active||undefined} onClick={()=>void acquire(value?.state==='failed')}>{active?<span className="spinner" aria-hidden="true"/>:<Icon name="download"/>}{t(backgroundPending?'获取 PDF':label||(value?.state==='failed'?'重试获取 PDF':'获取 PDF'))}</button>}
  <ResourceFeedback value={value} request={requestFailure}/>
 </span>;
}
