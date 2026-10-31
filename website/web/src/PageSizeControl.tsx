import {useEffect,useId,useState} from 'react';
import {t,useLanguage} from './i18n';

export const pageSizePreference='cirdc.results.limit.v1';
export const MAX_PAGE_SIZE=100;
const presets=['25','50','100'];
export function normalizePageSize(value:unknown,fallback='25'){
 return typeof value==='string'&&/^\d+$/.test(value)&&Number(value)>=1&&Number(value)<=MAX_PAGE_SIZE?String(Number(value)):fallback;
}
export function storedPageSize(){try{return normalizePageSize(localStorage.getItem(pageSizePreference));}catch{return '25';}}

export default function PageSizeControl({value,onChange}:{value:string;onChange:(value:string)=>void}){
 useLanguage();const [custom,setCustom]=useState(!presets.includes(value)),[draft,setDraft]=useState(value),[error,setError]=useState(false),errorId=useId();
 useEffect(()=>{setDraft(value);setError(false);if(!presets.includes(value))setCustom(true);},[value]);
 function apply(){const next=normalizePageSize(draft,'');if(!next){setError(true);return;}setDraft(next);setError(false);if(next!==value)onChange(next);}
 return <div className="page-size-control"><span className="page-size-label">{t('每页条数')}</span><div className="page-size-options" role="group" aria-label={t('每页条数')}>
  {presets.map(size=><button type="button" key={size} aria-pressed={!custom&&value===size} onClick={()=>{setCustom(false);setDraft(size);setError(false);if(size!==value)onChange(size);}}>{size}</button>)}
  <button type="button" aria-pressed={custom} onClick={()=>{setCustom(true);setDraft(value);setError(false);}}>{t('自定义')}</button>
 </div>{custom&&<div className="page-size-custom"><input type="number" inputMode="numeric" min={1} max={MAX_PAGE_SIZE} step={1} value={draft} aria-label={t('自定义每页条数')} aria-invalid={error} aria-describedby={error?errorId:undefined} placeholder={'1–'+MAX_PAGE_SIZE} onChange={event=>{setDraft(event.target.value);setError(false);}} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();apply();}}}/><button type="button" onClick={apply}>{t('应用条数')}</button></div>}{error&&<p className="page-size-error" id={errorId} role="alert">{t('请输入 1–{n} 之间的整数。',{n:MAX_PAGE_SIZE})}</p>}</div>;
}
