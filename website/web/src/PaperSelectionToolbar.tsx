import {useEffect,useRef,type ReactNode} from 'react';
import {t,useLanguage} from './i18n';
import Icon from './Icon';
/** `actions` replaces the citation and download buttons (used by the favorites page). */
export default function PaperSelectionToolbar({total,count,disabled,onAll,onCite,onDownload,actions}:{total:number;count:number;disabled:boolean;onAll:(checked:boolean)=>void;onCite?:()=>void;onDownload?:()=>void;actions?:ReactNode}){
 useLanguage();
 const check=useRef<HTMLInputElement>(null),all=total>0&&count===total;
 useEffect(()=>{if(check.current)check.current.indeterminate=count>0&&!all;},[count,all]);
 return <div className={'paper-selection-toolbar'+(count?' has-selection':'')} role="group" aria-label={t('论文多选操作')}>
  <label className="select-loaded"><input ref={check} type="checkbox" checked={all} disabled={disabled||!total} onChange={e=>onAll(e.target.checked)}/><span>{t('全选已载入')}</span></label>
  <span className="paper-selection-count" role="status" aria-live="polite"><span className="count-full">{t('已勾选 {n} / 已载入 {total} 篇',{n:count,total})}</span><span className="count-short" aria-hidden="true">{count} / {total}</span></span>
  {/* Phones show the short labels; the accessible name stays the full action. */}
  <div className="paper-selection-actions">{actions??<><button type="button" aria-label={t('批量引用')} disabled={disabled||!count} onClick={onCite}><Icon name="quote"/><span className="label-full">{t('批量引用')}</span><span className="label-short" aria-hidden="true">{t('引用')}</span></button><button type="button" aria-label={t('批量下载 PDF')} disabled={disabled||!count} onClick={onDownload}><Icon name="download"/><span className="label-full">{t('批量下载 PDF')}</span><span className="label-short" aria-hidden="true">{t('下载 PDF')}</span></button></>}</div>
 </div>;
}
