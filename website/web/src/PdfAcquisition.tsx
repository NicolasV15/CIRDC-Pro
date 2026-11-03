import {useEffect,useRef,useState} from 'react';
import {t} from './i18n';
import Icon from './Icon';
import './pdfAcquisition.css';
type API=(path:string,method?:string,data?:unknown)=>Promise<any>;
export function PdfAcquisition({href,api,auto=false}:{href:string;api:API;auto?:boolean}){
 const [value,setValue]=useState<any>(),[error,setError]=useState(''),[busy,setBusy]=useState(false),[autoBusy,setAutoBusy]=useState(false),[round,setRound]=useState(0);
 const manual=useRef(false),autoSent=useRef(false),generation=useRef(0);
 useEffect(()=>{generation.current++;manual.current=false;autoSent.current=false;setValue(undefined);setError('');return()=>{generation.current++;};},[href]);
 useEffect(()=>{
  let active=true,failures=0,timer:ReturnType<typeof setTimeout>|undefined;
  async function read(){try{const v=await api(href);if(!active)return;failures=0;setValue(v);if(['queued','fetching'].includes(v.state))timer=setTimeout(()=>void read(),2000);}catch(e){if(active){if(manual.current)setError((e as Error).message);if(++failures<3)timer=setTimeout(()=>void read(),4000);else setValue((v:any)=>({...v,state:'unknown'}));}}}
  void read();return()=>{active=false;if(timer)clearTimeout(timer);};
 },[href,api,round]);
 useEffect(()=>{
  if(!auto||!value||autoSent.current)return;
  autoSent.current=true;
  if(value.deferred||['ready','queued','fetching','unknown','unavailable'].includes(value.state))return;
  const current=generation.current;setAutoBusy(true);
  void api(href+'/ensure','POST',{automatic:true}).then(v=>{if(current===generation.current){setValue(v);setRound(n=>n+1);}}).catch(()=>{/* A background failure never interrupts the reader. */}).finally(()=>{if(current===generation.current)setAutoBusy(false);});
 },[auto,value?.state,value?.deferred,href,api]);
 async function acquire(){
  const current=generation.current;manual.current=true;setBusy(true);setError('');
  try{const v=await api(href+'/ensure','POST',{});if(current===generation.current){setValue(v);setRound(n=>n+1);}}
  catch(e){if(current===generation.current)setError((e as Error).message);}
  finally{if(current===generation.current)setBusy(false);}
 }
 const active=busy||autoBusy||['queued','fetching'].includes(value?.state),quiet=!manual.current&&(autoBusy||value?.request_origin==='automatic');
 const deferred=value?.deferred&&(manual.current||value?.request_origin==='manual');
 const restricted=['access_restricted','access_denied'].includes(value?.job?.error);
 if(value?.state==='ready')return <a className="button detail-pdf-trigger" href={value.reader_url} target="_blank" rel="noopener noreferrer"><Icon name="file"/>{t('阅读 PDF')}<Icon name="external" className="icon-trailing"/></a>;
 if(value?.state==='unavailable')return <span className="pdf-acquisition pdf-acquisition-unavailable" role="status"><Icon name="file"/>{t(value.unavailable_reason==='institution_not_licensed'?'无可获取 PDF（机构未授权）':'无可获取 PDF')}</span>;
 return <span className="pdf-acquisition"><button type="button" className="detail-pdf-trigger" disabled={active} aria-busy={active||undefined} onClick={()=>void acquire()}>{active?<span className="spinner" aria-hidden="true"/>:<Icon name="download"/>}{t(quiet?'获取 PDF':value?.state==='queued'?'PDF 等待获取':value?.state==='fetching'?'正在获取 PDF':value?.state==='failed'?'重试获取 PDF':'获取 PDF')}</button>
  {deferred?<span className="hint" role="status">{t(restricted?'来源访问受限，已加入后续 PDF 补全清单；补全后重新打开即可阅读。':'暂时未能获取 PDF，已加入后续补全清单；补全后重新打开即可阅读。')}</span>:error&&<span className="hint" role="status">{t(error)}</span>}
 </span>;
}
