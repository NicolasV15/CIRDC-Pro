import {useId} from 'react';
import {t,useLanguage} from './i18n';

export const pageSizePreference='cirdc.results.limit.v1';
const presets=['25','50','100'];
export function normalizePageSize(value:unknown,fallback='25'){
 const normalized=typeof value==='string'&&/^\d+$/.test(value)?String(Number(value)):'';
 return presets.includes(normalized)?normalized:presets.includes(fallback)?fallback:'25';
}
export function storedPageSize(){try{return normalizePageSize(localStorage.getItem(pageSizePreference));}catch{return '25';}}

export default function PageSizeControl({value,onChange}:{value:string;onChange:(value:string)=>void}){
 useLanguage();const id=useId();
 return <div className="page-size-control"><label className="page-size-label" htmlFor={id}>{t('每页条数')}</label><select id={id} value={normalizePageSize(value)} onChange={event=>{if(event.target.value!==value)onChange(event.target.value);}}>
  {presets.map(size=><option key={size} value={size}>{size}</option>)}
 </select></div>;
}
