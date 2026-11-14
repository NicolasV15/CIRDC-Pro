import {lazy,Suspense,useState} from 'react';
import {t,useLanguage} from './i18n';
import Icon from './Icon';
import {arxivCategoryName,arxivCategoryGroups,quickArxivCategories,isArxivArchive,selectedArxivCategories,toggleArxivCategory} from './arxivTaxonomy';
const ArxivCategoryGuide=lazy(()=>import('./ArxivCategoryGuide'));

/** Category label shown in chips and result rows: the code, with the official name when one exists. */
export function arxivCategoryLabel(code:string){
 const name=arxivCategoryName(code);
 return isArxivArchive(code)?t('{code} 全部分类',{code}):name?code+' · '+name:code;
}

/** Multiple subject classes are combined with OR; the generic archive shortcut is unnecessary. */
export function ArxivCategoryFilter({value,onChange}:{value:string;onChange:(value:string)=>void}){
 const lang=useLanguage(),zh=lang==='zh',[open,setOpen]=useState(true),[guideOpen,setGuideOpen]=useState(false),selected=selectedArxivCategories(value),keys=new Set(selected);
 const info=zh?'电路相关分类介绍':'Circuit-related category guide';
 return <><details className="venue-family-filter arxiv-category-filter" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
  <summary><span className="venue-family-heading"><span>{t('电路相关分类')}</span><button type="button" className="venue-guide-trigger" aria-label={info} title={info} aria-haspopup="dialog" aria-controls="arxiv-category-guide-dialog" aria-expanded={guideOpen} onClick={e=>{e.preventDefault();e.stopPropagation();setGuideOpen(true);}} onKeyDown={e=>{if(e.key==='Enter'||e.key===' ')e.stopPropagation();}}><Icon name="info"/></button></span><small>{selected.length?(zh?`已选 ${selected.length} 个分类`:`${selected.length} categories selected`):t('全部 arXiv 分类')}</small><Icon name="down" className="disclosure-caret"/></summary>
  <div className="venue-family-body"><div className="venue-family-actions"><button type="button" className="text-button" onClick={()=>onChange(selectedArxivCategories([...selected,...quickArxivCategories].join(',')).join(','))} disabled={quickArxivCategories.every(code=>keys.has(code))}>{zh?'选择全部相关分类':'Select all related categories'}</button><button type="button" className="text-button" onClick={()=>onChange('')} disabled={!selected.length}>{zh?'清除分类':'Clear categories'}</button></div><div role="group" aria-label={t('电路相关分类')}>
   {arxivCategoryGroups.map(group=><section className="venue-family-group" key={group.key}><h3>{group.name[lang]}</h3><div className="venue-family-choices">{group.codes.map(code=><button type="button" className="venue-family-choice" key={code} aria-pressed={keys.has(code)} title={arxivCategoryLabel(code)} onClick={()=>onChange(toggleArxivCategory(value,code))}>{keys.has(code)&&<Icon name="check"/>}{code}</button>)}</div></section>)}
  </div></div>
 </details>{guideOpen&&<Suspense fallback={<p className="hint" role="status">{zh?'正在加载分类介绍…':'Loading category guide…'}</p>}><ArxivCategoryGuide onClose={()=>setGuideOpen(false)}/></Suspense>}</>;
}
