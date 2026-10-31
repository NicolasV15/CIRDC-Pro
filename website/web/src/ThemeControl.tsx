import {useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {themeSpecs,type ThemePreference} from './themeCatalog';
import {t,useLanguage} from './i18n';
declare global{interface Window{CIRDCTheme?:{getSnapshot:()=>string;setPreference:(value:ThemePreference)=>void;subscribe:(listener:()=>void)=>()=>void}}}
const subscribe=(listener:()=>void)=>window.CIRDCTheme?.subscribe(listener)||(()=>{});
const getSnapshot=()=>window.CIRDCTheme?.getSnapshot()||'system/plain-white';
function AppearanceDialog({snapshot,onClose}:{snapshot:string;onClose:()=>void}){
 const language=useLanguage(),dialog=useRef<HTMLDialogElement>(null),close=useRef<HTMLButtonElement>(null),[preference,effective]=snapshot.split('/');
 const effectiveTheme=themeSpecs.find(theme=>theme.id===effective)||themeSpecs[1];
 useEffect(()=>{const box=dialog.current;if(!box)return;const opener=document.activeElement instanceof HTMLElement?document.activeElement:null,overflow=document.body.style.overflow;box.showModal();document.body.style.overflow='hidden';close.current?.focus();return()=>{if(box.open)box.close();document.body.style.overflow=overflow;if(opener?.isConnected)opener.focus({preventScroll:true});};},[]);
 return <dialog ref={dialog} className="citation-dialog theme-dialog" aria-labelledby="theme-dialog-title" onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target!==e.currentTarget)return;const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}>
  <header className="citation-header"><div><h2 id="theme-dialog-title">{t('外观与主题')}</h2><p>{t('选择后立即生效，并在此浏览器记住。')}</p></div><button type="button" ref={close} className="citation-close" aria-label={t('关闭外观设置')} onClick={onClose}>×</button></header>
  <div className="citation-body"><div className="theme-choices" role="group" aria-label={t('选择主题')}>
   <button type="button" className="theme-system-choice" aria-pressed={preference==='system'} onClick={()=>window.CIRDCTheme?.setPreference('system')}><span>{t('跟随系统')}</span><small>{t('当前：{theme}',{theme:language==='en'?effectiveTheme.english:effectiveTheme.name})}</small></button>
   <div className="theme-card-grid">{themeSpecs.map(theme=><button type="button" className="theme-card" key={theme.id} data-theme-choice={theme.id} aria-pressed={preference===theme.id} onClick={()=>window.CIRDCTheme?.setPreference(theme.id)}>
    <span className={'theme-swatch swatch-'+theme.id} aria-hidden="true"><span className="theme-swatch-panel"><i/><b/><b/></span><span className="theme-swatch-accent"/></span>
    <span className="theme-card-label"><strong>{language==='en'?theme.english:theme.name}</strong><span>{t(theme.scheme==='dark'?'深色':'浅色')}</span><span className="theme-card-check" aria-hidden="true">{preference===theme.id?'✓':''}</span></span>
   </button>)}</div>
  </div><p className="hint">{t('跟随系统时自动切换简洁白与石墨黑。')}</p></div>
 </dialog>;
}
export default function ThemeControl(){useLanguage();const snapshot=useSyncExternalStore(subscribe,getSnapshot,getSnapshot),[open,setOpen]=useState(false);
 return <><button type="button" className="appearance-trigger" aria-label={t('外观')} title={t('外观')} aria-haspopup="dialog" aria-expanded={open} onClick={()=>setOpen(true)}><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" strokeLinejoin="round"><path d="M10 2h4l.6 2.7 1.7 1 2.7-.9 2 3.4-2.1 1.8v4l2.1 1.8-2 3.4-2.7-.9-1.7 1L14 22h-4l-.6-2.7-1.7-1-2.7.9-2-3.4L5.1 14v-4L3 8.2l2-3.4 2.7.9 1.7-1Z"/><circle cx="12" cy="12" r="3.2"/></svg><span>{t('外观')}</span></button>{open&&<AppearanceDialog snapshot={snapshot} onClose={()=>setOpen(false)}/>}</>;
}
