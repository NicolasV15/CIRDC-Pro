import {useEffect,useState} from 'react';
import {t,useLanguage} from './i18n';

export default function PaperSearchBar({number,initialQuery,onSearch}:{number:string;initialQuery:string;onSearch:(query:string)=>void}){
 useLanguage();
 const [query,setQuery]=useState(initialQuery);
 useEffect(()=>setQuery(initialQuery),[number,initialQuery]);
 return <form className="search-box paper-detail-search" role="search" aria-label={t('文献库检索')} onSubmit={event=>{event.preventDefault();if(query.trim())onSearch(query.trim());}}>
  <div className="search-main"><span aria-hidden="true">⌕</span><input type="search" aria-label={t('搜索论文')} placeholder={t('搜索文献库：标题、作者、关键词、编号 / DOI')} maxLength={200} value={query} onChange={event=>setQuery(event.target.value)}/><button type="submit" className="primary" disabled={!query.trim()}>{t('检索')}</button></div>
 </form>;
}
