import type {FormEvent} from 'react';
import Icon from './Icon';
import {t} from './i18n';
export type SearchOptions={q:string;field:string;sort:string;view:string;k:string;terms:string};
type Props={value:SearchOptions;fields:[string,string][];busy:boolean;invalid?:boolean;placeholder:string;onQuery:(q:string)=>void;onOption:(key:'field'|'sort'|'view'|'k'|'terms',value:string)=>void;onSubmit:(event:FormEvent)=>void};
export default function PaperSearchControls({value,fields,busy,invalid=false,placeholder,onQuery,onOption,onSubmit}:Props){
 return <form className="search-box" role="search" aria-label={t('文献库检索')} onSubmit={onSubmit}>
  <div className="search-main"><Icon name="search" className="search-icon"/><input aria-label={t('搜索论文')} placeholder={placeholder} maxLength={value.field==='body'?600:200} value={value.q} onChange={e=>onQuery(e.target.value)}/><button className="primary" disabled={busy||invalid}>{t('检索')}</button></div>
  <div className="search-options">
   <div className="search-option-section"><span className="search-option-label">{t('检索字段')}</span><div className="search-choice-group field-choices" role="group" aria-label={t('检索字段')}>{fields.map(([v,label])=><button key={v} type="button" className="search-choice" aria-pressed={value.field===v} onClick={()=>onOption('field',v)}>{t(label)}</button>)}</div></div>
   <div className="search-option-section"><span className="search-option-label">{t('结果')}</span><div className="search-choice-group" role="group" aria-label={t('结果视图')}>{[['',t('全部匹配')],['top',t('最相关')]].map(([v,label])=><button key={v||'all'} type="button" className="search-choice" aria-pressed={value.view===v} onClick={()=>onOption('view',v)}>{label}</button>)}</div>{value.view==='top'&&<select className="top-k-select" aria-label={t('返回篇数')} value={value.k||'20'} onChange={e=>onOption('k',e.target.value==='20'?'':e.target.value)}>{['10','20','50','100'].map(k=><option key={k} value={k}>{t('前 {k} 篇',{k})}</option>)}</select>}</div>
   {value.view!=='top'&&<div className="search-option-section"><span className="search-option-label">{t('排序')}</span><div className="search-choice-group" role="group" aria-label={t('排序')}>{[['relevance',t('相关度')],['year',t('年份从新到旧')]].map(([v,label])=><button key={v} type="button" className="search-choice" aria-pressed={value.sort===v} onClick={()=>onOption('sort',v)}>{label}</button>)}</div></div>}
   <label className="alias-toggle" title={t('关闭后只匹配输入的原写法')}><input type="checkbox" checked={value.terms!=='exact'} onChange={e=>onOption('terms',e.target.checked?'':'exact')}/><span>{t('等价写法扩展')}</span></label>
  </div>
 </form>;
}
