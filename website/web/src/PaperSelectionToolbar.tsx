import {useEffect,useRef} from 'react';
import {t,useLanguage} from './i18n';
import Icon from './Icon';
export default function PaperSelectionToolbar({total,count,disabled,onAll,onCite,onDownload}:{total:number;count:number;disabled:boolean;onAll:(checked:boolean)=>void;onCite:()=>void;onDownload:()=>void}){
 useLanguage();
 const check=useRef<HTMLInputElement>(null),all=total>0&&count===total;
 useEffect(()=>{if(check.current)check.current.indeterminate=count>0&&!all;},[count,all]);
 return <div className={'paper-selection-toolbar'+(count?' has-selection':'')} role="group" aria-label={t('论文多选操作')}>
  <label className="select-loaded"><input ref={check} type="checkbox" checked={all} disabled={disabled||!total} onChange={e=>onAll(e.target.checked)}/><span>{t('全选已载入')}</span></label>
  <span className="paper-selection-count" role="status" aria-live="polite">{t('已勾选 {n} / 已载入 {total} 篇',{n:count,total})}</span>
  <div className="paper-selection-actions"><button type="button" disabled={disabled||!count} onClick={onCite}><Icon name="quote"/>{t('批量引用')}</button><button type="button" disabled={disabled||!count} onClick={onDownload}><Icon name="download"/>{t('批量下载 PDF')}</button></div>
 </div>;
}
