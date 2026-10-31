import {useEffect,useRef,useState} from 'react';
import {t,useLanguage} from './i18n';
import {loadReaderLayout,normalizeReaderLayout,readerLayoutDefaults,readerLayoutPreference,readerLayoutRanges,type ReaderLayout} from './readerLayout';

export function useReaderLayout(){
 const [layout,setLayout]=useState(loadReaderLayout);
 useEffect(()=>{
  const sync=(event:StorageEvent)=>{if(event.key===readerLayoutPreference||event.key===null)setLayout(loadReaderLayout());};
  window.addEventListener('storage',sync);return()=>window.removeEventListener('storage',sync);
 },[]);
 function update(patch:Partial<ReaderLayout>){const next=normalizeReaderLayout({...layout,...patch});setLayout(next);try{localStorage.setItem(readerLayoutPreference,JSON.stringify(next));}catch{/* Keep in-memory preferences when browser storage is blocked. */}}
 return {layout,update,reset:()=>update({...readerLayoutDefaults})};
}

export default function ReaderLayoutControls({layout,onChange,onReset}:{layout:ReaderLayout;onChange:(value:Partial<ReaderLayout>)=>void;onReset:()=>void}){
 useLanguage();const details=useRef<HTMLDetailsElement>(null),[position,setPosition]=useState({top:12,right:12});
 function place(){const box=details.current;if(!box?.open)return;const anchor=box.querySelector('summary')!.getBoundingClientRect(),panel=box.querySelector<HTMLElement>('.reader-layout-popover'),viewport=document.documentElement.clientWidth,width=Math.min(320,viewport-24),height=panel?.getBoundingClientRect().height||400;setPosition({top:Math.max(12,Math.min(anchor.bottom+8,innerHeight-height-12)),right:Math.min(Math.max(12,viewport-anchor.right),viewport-width-12)});}
 useEffect(()=>{const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!details.current?.contains(event.target)&&details.current)details.current.open=false;};document.addEventListener('pointerdown',outside);window.addEventListener('resize',place);return()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',place);};},[]);
 return <details className="reader-layout-controls" ref={details} onToggle={place} onKeyDown={event=>{if(event.key==='Escape'&&details.current?.open){event.preventDefault();details.current.open=false;details.current.querySelector('summary')?.focus();}}}>
  <summary>{t('阅读布局')}</summary>
  <div className="reader-layout-popover" style={position} role="group" aria-label={t('阅读布局')}>
   {(['fontScale','pageWidth','tocWidth','infoWidth'] as const).map(key=><label key={key} data-width={key}><span className="reader-layout-label"><span>{t(key==='fontScale'?'字体大小':key==='pageWidth'?'阅读宽度':key==='tocWidth'?'目录宽度':'出版信息宽度')}</span><output>{layout[key]}{key==='fontScale'?'%':' px'}</output></span><input type="range" {...readerLayoutRanges[key]} value={layout[key]} disabled={key==='infoWidth'&&!layout.infoOpen} aria-label={t(key==='fontScale'?'字体大小':key==='pageWidth'?'阅读宽度':key==='tocWidth'?'目录宽度':'出版信息宽度')} onChange={event=>onChange({[key]:Number(event.target.value)})}/>{key==='fontScale'&&<span className="reader-layout-font-hint">{t('正文、摘要与公式同步调整。')}</span>}</label>)}
   <label className="reader-layout-info-toggle"><input type="checkbox" checked={layout.infoOpen} onChange={event=>onChange({infoOpen:event.target.checked})}/><span>{t('显示出版信息')}</span></label>
   <button type="button" className="reader-layout-reset" onClick={onReset}>{t('恢复默认布局')}</button>
  </div>
 </details>;
}
