import {useState} from 'react';
import {t,useLanguage} from './i18n';
import Icon from './Icon';
import {arxivCategoryName,circuitCategories,isArxivArchive} from './arxivTaxonomy';

/** Category label shown in chips and result rows: the code, with the official name when one exists. */
export function arxivCategoryLabel(code:string){
 const name=arxivCategoryName(code);
 return isArxivArchive(code)?t('{code} 全部分类',{code}):name?code+' · '+name:code;
}

/** Quick subject-class choices for circuit and device research; one category applies at a time. */
export function ArxivCategoryFilter({value,onChange}:{value:string;onChange:(value:string)=>void}){
 useLanguage();
 const [open,setOpen]=useState(true),current=value.toLowerCase();
 const choices=['eess',...circuitCategories];
 return <details className="venue-family-filter arxiv-category-filter" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
  <summary><span className="venue-family-heading"><span>{t('电路相关分类')}</span></span><small>{value?arxivCategoryLabel(value):t('全部 arXiv 分类')}</small><Icon name="down" className="disclosure-caret"/></summary>
  <div className="venue-family-body"><div className="venue-family-choices" role="group" aria-label={t('电路相关分类')}>
   {choices.map(code=>{const selected=current===code.toLowerCase();return <button type="button" className="venue-family-choice" key={code} aria-pressed={selected} title={arxivCategoryLabel(code)} onClick={()=>onChange(selected?'':code)}>{selected&&<Icon name="check"/>}{isArxivArchive(code)?t('{code} 全部',{code}):code}</button>;})}
  </div></div>
 </details>;
}
