import FavoriteButton from './FavoriteButton';
import {useFavoriteStates,type FavoriteTarget} from './favorites';
import {useAccount} from './account';
import React,{useCallback,useEffect,useId,useMemo,useRef,useState} from 'react';
import ArxivPage from './ArxivPage';
import {t,useLanguage,localizedText,contentTypeLabel} from './i18n';
import {api} from './api';
import {fmt,contentStateNames} from './format';
import Icon from './Icon';
import ScientificTitle from './ScientificTitle';
import AbstractPreview from './AbstractPreview';
import BackToTop from './BackToTop';
import SelectionCopy from './SelectionCopy';
import PageSizeControl,{normalizePageSize,storedPageSize,pageSizePreference} from './PageSizeControl';
import PaperSelectionToolbar from './PaperSelectionToolbar';
import {OverviewCards} from './Overview';
import SearchInsights,{MatchReasons,PassageHits,Highlighted} from './SearchInsights';
import PaperDetail,{readingHref} from './PaperDetail';
import PaperSearchControls from './PaperSearchControls';
import {AuthorLinks,AuthorSearch} from './AuthorSearch';
import {VenueFamilyFilter,VenueTags} from './VenueTags';
import {orderVenueFamilies,selectedVenueFamilies,venueFamilies,venueNumbers} from './venueFamilies';
import {ArxivCategoryFilter,arxivCategoryLabel} from './ArxivCategoryFilter';
import {arxivCategories,arxivCategoryName,selectedArxivCategories,toggleArxivCategory} from './arxivTaxonomy';
import {arxivCitationRecord} from './arxivCitations';
import {decodeTexAccents} from './texAccents';
import {arxivDate} from './arxivDate';
import {resultSelection} from './resultSelection';
import {activeEntries,allSources,effectiveSort,fieldOnlySource,fieldsFor,filtersFromSearch,blankFilters,paperKey,parsePaperKey,requestParams,searchHref,selectedSources,toggleSource,unavailableSources,type Source,type SourceNote,type SourceStatus,type UnifiedFilters} from './unifiedSearch';
import type {FulltextStatus,Index,Paper,QueryInfo,Venue} from './types';
import './arxiv.css';
const BatchDownloadDialog=React.lazy(()=>import('./BatchDownloadDialog'));
const CitationDialog=React.lazy(()=>import('./CitationDialog'));
const sidebarQuery='(min-width:1024px)',restoreKey='cirdc.search.restore.v1';
type ArxivRow={paper_id:string;arxiv_id:string;title:string;authors_raw:string;abstract:string;categories:string[];year:number;submitted_at?:string|null;position?:number;requested_version?:number};
type Row={number:string;source:'ieee';paper:Paper}|{number:string;source:'arxiv';paper:ArxivRow};
type SourceInfo=Partial<Record<Source,SourceStatus>>;
const draftKeys=['kind','year_from','year_to','abstract_state','keywords_state','category'] as const;
const sourceLabel:Record<Source,string>={ieee:'IEEE',arxiv:'arXiv'};
function invalidYearRange(f:Pick<UnifiedFilters,'year_from'|'year_to'>){return !!f.year_from&&!!f.year_to&&Number(f.year_from)>Number(f.year_to);}
function toRow(item:any):Row{return item.source==='arxiv'?{number:paperKey('arxiv',item.paper_id),source:'arxiv',paper:{...item,paper_id:String(item.paper_id)}}:{number:paperKey('ieee',item.number),source:'ieee',paper:item};}
function favoriteTarget(row:Row):FavoriteTarget{return row.source==='ieee'?{source:'ieee',paperId:String(row.paper.number)}:{source:'arxiv',paperId:row.paper.paper_id,version:row.paper.requested_version||'latest'};}

export default function ReaderPage(){
 return /^\/arxiv\/papers\/\d+$/.test(location.pathname)?<ArxivPage/>:<UnifiedSearchPage/>;
}
function SourcePicker({value,disabled,onChange}:{value:string;disabled:boolean;onChange:(value:string)=>void}){
 const chosen=selectedSources(value);
 return <fieldset className="search-sources" disabled={disabled}><legend className="sr-only">{t('检索来源')}</legend>{allSources.map(source=>{const only=chosen.length===1&&chosen[0]===source;return <label key={source} className="search-source" title={only?t('至少保留一个来源'):undefined}><input type="checkbox" checked={chosen.includes(source)} aria-disabled={only||undefined} onChange={e=>{if(!only)onChange(toggleSource(value,source,e.target.checked));}}/><span>{sourceLabel[source]}</span></label>;})}</fieldset>;
}
function SourceBadge({source}:{source:Source}){return <span className="source-badge" data-source={source}>{sourceLabel[source]}</span>;}

function UnifiedSearchPage(){
 useLanguage();
 const browseTop=useRef<HTMLHeadingElement>(null),resultsTitle=useRef<HTMLHeadingElement>(null),formId=useId();
 const [citationKeys,setCitationKeys]=useState<string[]>([]),[downloadKeys,setDownloadKeys]=useState<string[]|null>(null);
 // Selection belongs to the rows on screen, never to a hidden cross-search basket.
 const [results,dispatchResults]=React.useReducer(resultSelection<Row>,{rows:[],selected:[]});
 const {rows}=results,selectedKeys=new Set(results.selected);
 useFavoriteStates(rows.map(favoriteTarget),!!useAccount().user);
 useEffect(()=>{try{sessionStorage.removeItem('cirdc.selected-papers.v1');sessionStorage.removeItem('cirdc.arxiv.search.v3');}catch{/* Legacy baskets are never restored. */}},[]);
 // The sidebar is always shown on wide screens; narrower screens fold it into a disclosure.
 const [filtersOpen,setFiltersOpen]=useState(()=>window.matchMedia(sidebarQuery).matches);
 useEffect(()=>{const media=window.matchMedia(sidebarQuery),change=()=>{if(media.matches)setFiltersOpen(true);};media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
 const latestRequest=useRef(0),countAbort=useRef<AbortController|null>(null),countFrames=useRef<number[]>([]),venuesRequest=useRef<Promise<void>|null>(null);
 const [countFailed,setCountFailed]=useState(false),[venuesFailed,setVenuesFailed]=useState(false);
 const [insight,setInsight]=useState<{query?:QueryInfo;fulltext?:FulltextStatus|null;exact:boolean}>({exact:true});
 const initial=useMemo(()=>{const f=filtersFromSearch(location.search,storedPageSize());f.limit=normalizePageSize(f.limit);f.venue_tags=selectedVenueFamilies(f.venue_tags).map(x=>x.key).join(',');return f;},[]);
 const [filters,setFilters]=useState<UnifiedFilters>(initial),[applied,setApplied]=useState<UnifiedFilters>(initial),[venueText,setVenueText]=useState(initial.venue),[venues,setVenues]=useState<Venue[]>([]),[index,setIndex]=useState<Index>(),[arxivIndexed,setArxivIndexed]=useState<number>();
 const [cursor,setCursor]=useState<string|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[total,setTotal]=useState<number|null>(null),[rowInfo,setRowInfo]=useState<SourceInfo>(),[countInfo,setCountInfo]=useState<SourceInfo>(),[notes,setNotes]=useState<SourceNote[]>([]);
 const [detail,setDetail]=useState<string|null>(window.location.pathname.match(/^\/papers\/(\d+)/)?.[1]||null);
 const sources=selectedSources(applied.sources),draftSources=selectedSources(filters.sources),ieee=draftSources.includes('ieee'),arxiv=draftSources.includes('arxiv'),both=ieee&&arxiv;
 useEffect(()=>{try{localStorage.setItem(pageSizePreference,applied.limit);}catch{/* The URL still preserves this setting. */}},[applied.limit]);
 function cancelCount(){countAbort.current?.abort();countFrames.current.forEach(cancelAnimationFrame);countFrames.current=[];}
 useEffect(()=>()=>cancelCount(),[]);
 async function readCount(f:UnifiedFilters,request:number){
  if(request!==latestRequest.current)return;
  countAbort.current?.abort();const controller=new AbortController();countAbort.current=controller;setCountFailed(false);
  try{
   const params=requestParams(f,venueNumbers);params.delete('limit');params.set('totals','only');
   const value=await api('/api/search/unified?'+params,'GET',undefined,controller.signal);
   if(request!==latestRequest.current||controller.signal.aborted)return;
   setCountInfo(value.sources);setTotal(typeof value.total==='number'?value.total:null);setInsight(old=>({...old,exact:value.total_exact!==false}));
   if(!value.partial&&typeof value.total!=='number')setCountFailed(true);
  }catch{if(request===latestRequest.current&&!controller.signal.aborted)setCountFailed(true);}
 }
 // Leave one painted frame for the current rows before counting all matches.
 function queueCount(f:UnifiedFilters,request:number){countFrames.current.push(requestAnimationFrame(()=>{countFrames.current.push(requestAnimationFrame(()=>void readCount(f,request)));}));}
 function ensureVenues(){
  if(venuesRequest.current)return venuesRequest.current;
  setVenuesFailed(false);
  const pending=api('/api/venues').then(value=>{if(!Array.isArray(value.items))throw Error('invalid_venues');setVenues(value.items);}).catch(()=>{venuesRequest.current=null;setVenuesFailed(true);});
  venuesRequest.current=pending;return pending;
 }
 async function load(f:UnifiedFilters,more?:string){
  const request=++latestRequest.current;cancelCount();setCountFailed(false);setBusy(true);setError('');
  if(!more){setCursor(null);setTotal(null);setCountInfo(undefined);setRowInfo(undefined);setNotes([]);dispatchResults({type:'reset'});}
  if(invalidYearRange(f)){setBusy(false);setCountFailed(true);setError(t('起始年份不能晚于结束年份。'));return;}
  try{
   const params=requestParams(f,venueNumbers);
   if(more)params.set('cursor',more);
   params.set('totals','defer');
   const r=await api('/api/search/unified?'+params);
   if(request!==latestRequest.current)return;
   dispatchResults({type:more?'append':'replace',rows:r.items.map(toRow)});
   setInsight(old=>({query:r.query,fulltext:r.fulltext,exact:more?old.exact:true}));
   setCursor(r.next_cursor);setRowInfo(r.sources||{});setNotes(r.source_notes||[]);
   if(!more)queueCount(f,request);
  }catch(e){
   if(request===latestRequest.current){setError((e as Error).message);setCountFailed(true);}
  }finally{
   if(request===latestRequest.current)setBusy(false);
  }
 }
 // The arXiv count is read once, when a list that includes arXiv is first shown.
 const arxivOverview=useRef(false);
 useEffect(()=>{if(detail||arxivOverview.current||!selectedSources(applied.sources).includes('arxiv'))return;arxivOverview.current=true;void api('/api/arxiv/overview').then(v=>setArxivIndexed(v.indexed)).catch(()=>{});},[detail,applied.sources]);
 async function overview(){try{const r=await api('/api/overview');setIndex(r.index);}catch(e){setError((e as Error).message);}}
 /** Returning from an arXiv detail page restores the list that opened it, when its query still matches. */
 function restore(f:UnifiedFilters){
  if(new URLSearchParams(location.search).get('restore')!=='1')return false;
  history.replaceState({},'',searchHref(f));
  try{const s=JSON.parse(sessionStorage.getItem(restoreKey)||'null');if(s?.key!==searchHref(f))return false;
   dispatchResults({type:'replace',rows:s.rows});setCursor(s.cursor);setTotal(s.total);setRowInfo(s.rowInfo);setCountInfo(s.countInfo);setNotes(s.notes||[]);setInsight(s.insight||{exact:true});
   requestAnimationFrame(()=>window.scrollTo(0,s.scroll));return true;}catch{return false;}
 }
 function remember(){try{sessionStorage.setItem(restoreKey,JSON.stringify({key:searchHref(applied),rows,cursor,total,rowInfo,countInfo,notes,insight,scroll:scrollY}));}catch{/* The query URL remains available. */}}
 useEffect(()=>{
  void overview();
  if(!detail&&!restore(initial)){history.replaceState({},'',searchHref(initial));void load(initial);}
  const timer=setInterval(()=>void overview(),60000);
  const pop=()=>{
   const number=window.location.pathname.match(/^\/papers\/(\d+)/)?.[1]||null;setDetail(number);
   if(!number){const next=filtersFromSearch(location.search,storedPageSize());next.limit=normalizePageSize(next.limit);next.venue_tags=selectedVenueFamilies(next.venue_tags).map(f=>f.key).join(',');setFilters(next);setApplied(next);setVenueText(next.venue);void load(next);}
  };
  window.addEventListener('popstate',pop);return()=>{clearInterval(timer);window.removeEventListener('popstate',pop);};
 },[]);
 function applySearch(next:UnifiedFilters,venueInput=venueText){
  if(invalidYearRange(next)){setError(t('起始年份不能晚于结束年份。'));return;}
  const value=selectedSources(next.sources).includes('ieee')?venueInput.split(' · ')[0].trim():next.venue;
  if(value&&!/^\d+$/.test(value)){setError(t('请从候选列表选择刊会，或输入刊会编号。'));return;}
  const resetAuthor=next.field==='authors'&&next.q!==applied.q;
  const f={...next,venue:value,...(resetAuthor?{author_source:'',author_id:'',author_unidentified:''}:{})};
  setFilters(f);setApplied(f);history.replaceState({},'',searchHref(f));void load(f);
 }
 function submit(e:React.FormEvent){e.preventDefault();applySearch(filters);}
 function updateSearchOption(key:'field'|'sort'|'view'|'k'|'terms',value:string){
  // Picking the order the query would use anyway keeps the automatic choice.
  const stored=key==='sort'&&value===effectiveSort({q:filters.q,sort:''})?'':value;
  if(filters[key]===stored)return;applySearch({...filters,[key]:stored});
 }
 function changeSources(value:string){const next={...filters,sources:value};if(!fieldsFor(selectedSources(value)).includes(next.field))next.field='all';applySearch(next);}
 function update(k:keyof UnifiedFilters,v:string){setFilters(f=>({...f,[k]:v}));if(k==='year_from'||k==='year_to')setError('');}
 // A removed control would drop keyboard focus to the page; continue from the results instead.
 function keepFocus(){requestAnimationFrame(()=>{if(!document.activeElement||document.activeElement===document.body)resultsTitle.current?.focus({preventScroll:true});});}
 // Removing one applied condition keeps the other applied values and discards unapplied drafts.
 function removeFilter(patch:Partial<UnifiedFilters>){const next={...applied,...patch};if('venue' in patch)setVenueText(next.venue);applySearch(next,next.venue);keepFocus();}
 function clearAll(){const cleared={...blankFilters(applied.limit),sources:applied.sources};setVenueText('');applySearch(cleared,'');keepFocus();}
 function open(number:string,href='/papers/'+number){history.pushState({},'',href);setDetail(number);window.scrollTo(0,0);}
 function back(){setDetail(null);history.pushState({},'',searchHref(applied));if(!rows.length)void load(applied);}
 function searchFromPaper(text:string){
  const next={...blankFilters(applied.limit),sources:applied.sources,q:text};
  setFilters(next);setApplied(next);setVenueText('');setDetail(null);
  history.pushState({},'',searchHref(next));
  void load(next);window.scrollTo(0,0);
 }
 // Citation and download dialogs read each selected paper from its own source.
 const versions=useMemo(()=>new Map(rows.flatMap(row=>row.source==='arxiv'?[[row.paper.paper_id,row.paper.requested_version]]:[])),[rows]);
 const fetchPaper=useCallback(async(path:string,method='GET',data?:unknown,resources=false)=>{
  const match=/^\/api\/papers\/([^/]+)$/.exec(path);
  if(!match)return api(path,method,data);
  const {source,id}=parsePaperKey(decodeURIComponent(match[1]));
  if(source!=='arxiv')return api('/api/papers/'+encodeURIComponent(id));
  const value=await api('/api/arxiv/papers/'+id),p=value.paper,v=versions.get(id)||Math.max(...p.versions.map((x:any)=>x.version));
  const paper:any={number:id,record:arxivCitationRecord(p,v),resources:[]};
  if(resources){const status=await api('/api/arxiv/papers/'+id+'/versions/'+v+'/resources');if(status.resources?.pdf?.state==='ready'){const base='/api/resources/arxiv/papers/'+id+'/versions/'+v+'/pdf';paper.resources=[{id:'arxiv:'+id+':v'+v,kind:'pdf',media_type:'application/pdf',href:base,reader_href:base+'/reader',archive_prepare_href:'/api/resources/arxiv/versions/'+v+'/archives'}];}}
  return {paper};
 },[versions]);
 const citationFetcher=useCallback((path:string)=>fetchPaper(path),[fetchPaper]);
 const downloadFetcher=useCallback((path:string,method='GET',data?:unknown)=>fetchPaper(path,method,data,true),[fetchPaper]);
 if(detail)return <><PaperDetail number={detail} back={back} initialQuery={applied.q} onSearch={searchFromPaper}/><SelectionCopy/></>;

 const choices=venues.filter(v=>(!filters.kind||v.kind===filters.kind)&&(!venueText||(v.number+' '+v.title).toLowerCase().includes(venueText.toLowerCase()))).slice(0,80);
 const firstYear=ieee?1800:1991,latestYear=Math.min(2200,Math.max(new Date().getFullYear(),index?.year_range?.max||0,Number(filters.year_from)||0,Number(filters.year_to)||0));
 const years=Array.from({length:latestYear-firstYear+1},(_,i)=>latestYear-i);
 const pending=draftKeys.some(key=>filters[key]!==applied[key])||(ieee&&venueText.split(' · ')[0].trim()!==applied.venue);
 const appliedIeee=sources.includes('ieee'),appliedArxiv=sources.includes('arxiv'),appliedBoth=appliedIeee&&appliedArxiv;
 const families=appliedIeee?orderVenueFamilies(selectedVenueFamilies(applied.venue_tags)):[];
 const kindLabel=(kind:string)=>kind==='Journals'?t('期刊'):kind==='Conferences'?t('会议'):kind;
 const chips:{key:string;label:string;source?:Source;remove:Partial<UnifiedFilters>}[]=[
  ...(applied.year_from||applied.year_to?[{key:'years',label:applied.year_from&&applied.year_to?applied.year_from+'–'+applied.year_to:applied.year_from?t('{year} 年起',{year:applied.year_from}):t('至 {year} 年',{year:applied.year_to}),remove:{year_from:'',year_to:''}}]:[]),
  ...(appliedIeee?[
   ...(applied.kind?[{key:'kind',label:kindLabel(applied.kind),source:'ieee' as const,remove:{kind:''}}]:[]),
   ...(applied.venue?[{key:'venue',label:venues.find(v=>v.number===applied.venue)?.title||t('刊会编号 {n}',{n:applied.venue}),source:'ieee' as const,remove:{venue:''}}]:[]),
   ...(applied.abstract_state?[{key:'abstract',label:t('摘要：')+t(contentStateNames[applied.abstract_state]||applied.abstract_state),source:'ieee' as const,remove:{abstract_state:''}}]:[]),
   ...(applied.keywords_state?[{key:'keywords',label:t('关键词：')+t(contentStateNames[applied.keywords_state]||applied.keywords_state),source:'ieee' as const,remove:{keywords_state:''}}]:[]),
   ...families.map(f=>({key:'family-'+f.key,label:f.label,source:'ieee' as const,remove:{venue_tags:venueFamilies.filter(x=>x.key!==f.key&&families.some(s=>s.key===x.key)).map(x=>x.key).join(',')}})),
  ]:[]),
  ...(appliedArxiv?selectedArxivCategories(applied.category).map(code=>({key:'category:'+code,label:arxivCategoryLabel(code),source:'arxiv' as const,remove:{category:toggleArxivCategory(applied.category,code)}})):[]),
 ];
 const activeCount=chips.length,topView=applied.view==='top';
 const fieldLabels:Record<string,string>={all:t('全部'),title:t('标题'),authors:t('作者'),keywords:t('关键词'),abstract:t('摘要'),body:t('正文'),categories:t('学科分类')};
 const fields=fieldsFor(draftSources).map(field=>[field,fieldLabels[field]] as [string,string]);
 const chronological=both?t('时间从新到旧'):arxiv?t('最新投稿'):t('年份从新到旧');
 const placeholder=filters.field==='authors'?(arxiv&&!ieee?t('输入作者姓名'):t('输入作者姓名或 IEEE 作者 ID')):filters.field==='body'?t('输入正文中的词、短语或一句原文'):both?t('搜索标题、作者、摘要，或输入编号 / DOI / arXiv 编号'):arxiv?t('搜索标题、作者、摘要，或输入 arXiv 编号'):t('搜索论文、作者、关键词，或输入编号 / DOI');
 const title=both?t('IEEE 与 arXiv 论文检索'):arxiv?t('arXiv 论文检索'):t('IEEE Xplore 论文检索');
 const unavailable=unavailableSources(rowInfo),partial=unavailable.length>0;
 const fieldNote=notes.find(note=>note.code==='field_not_supported');
 const onlySource=fieldNote?allSources.find(source=>source!==fieldNote.source&&sources.includes(source)):fieldOnlySource(applied.field,sources);
 const unconfigured=notes.some(note=>note.code==='source_unconfigured'&&note.source==='arxiv');
 const counted=sources.filter(source=>countInfo?.[source]?.status==='ok'&&typeof countInfo[source]?.total==='number');
 const breakdown=sources.length>1&&(counted.length>1||partial)?counted.map(source=>sourceLabel[source]+' '+fmt(countInfo![source]!.total!)):[];
 const totalText=countFailed?t('总数暂不可用'):partial?(counted.length?'':total===null&&!countInfo?t('正在统计总数…'):''):total===null?t('正在统计总数…'):topView?t('前 {k} 篇 · 共 {n} 篇匹配',{k:fmt(rows.length),n:fmt(total)}):insight.exact?t('共 {n} 条',{n:fmt(total)}):t('至少 {n} 条',{n:fmt(total)});
 const known=new Set(arxivCategories.map(category=>category.code)),categoryChoices=[...arxivCategories.map(category=>({code:category.code,name:category.name})),...[...new Set(rows.flatMap(row=>row.source==='arxiv'?row.paper.categories||[]:[]))].filter(code=>!known.has(code)).sort().map(code=>({code,name:''}))];
 const selectedRows=rows.filter(row=>selectedKeys.has(row.number));
 const linkParams=new URLSearchParams(activeEntries(applied));
 return <><main id="main" className="workspace reader-workspace" data-copy-scope>
  <div className="reader-hero"><div className="reader-hero-title"><h1 className="search-page-title" ref={browseTop} tabIndex={-1}>{title}</h1></div>{both?<OverviewCards overview={index?.overview} compact arxiv={arxivIndexed??null}/>:ieee?<OverviewCards overview={index?.overview} compact/>:<div className="stats stats-compact" role="group" aria-label={t('数据库概览')} style={{'--overview-columns':2} as React.CSSProperties}><div className="stat"><span>{t('已索引论文')}</span><strong>{arxivIndexed===undefined?'—':fmt(arxivIndexed)}</strong></div><div className="stat"><span>{t('检索范围')}</span><strong>{t('元数据')}</strong></div></div>}</div>
  <PaperSearchControls chronologicalLabel={chronological} defaultSort={effectiveSort({q:filters.q,sort:''})} value={{...filters,sort:effectiveSort(filters)}} fields={fields} busy={busy} invalid={invalidYearRange(filters)} placeholder={placeholder} scope={<SourcePicker value={filters.sources} disabled={busy&&!rows.length} onChange={changeSources}/>} onQuery={q=>update('q',q)} onOption={updateSearchOption} onSubmit={submit}/>

  <div className="reader-layout">
   <aside className="reader-sidebar" aria-label={t('筛选')}>
    <details className="filter-disclosure" open={filtersOpen} onToggle={e=>setFiltersOpen(e.currentTarget.open)}>
     <summary><Icon name="filter"/><span>{t('筛选')}</span>{activeCount>0&&<span className="count-badge" aria-label={t('{n} 个条件生效中',{n:activeCount})}>{activeCount}</span>}<Icon name="down" className="disclosure-caret"/></summary>
     <div className="filter-panel">
      {ieee&&<section key="ieee" className={'filter-source-group'+(both?' is-grouped':'')} aria-label={both?t('IEEE 筛选'):undefined}>
       {both&&<h2 className="filter-source-heading"><SourceBadge source="ieee"/>{t('刊会与类型')}</h2>}
       <VenueFamilyFilter value={filters.venue_tags} defaultOpen={!both||!!filters.venue_tags} onChange={value=>applySearch({...filters,venue_tags:value})}/>
       {!both&&<h2 className="filter-heading">{t('更多条件')}</h2>}
       <fieldset className="segmented-field" form={formId}><legend>{t('出版物类型')}</legend><div className="segmented">{[['',t('全部类型')],['Journals',t('期刊')],['Conferences',t('会议')]].map(([v,l])=><label key={v||'all'}><input type="radio" form={formId} name="kind" value={v} checked={filters.kind===v} onChange={()=>{update('kind',v);setVenueText('');update('venue','');}}/><span>{l}</span></label>)}</div></fieldset>
       <label>{t('期刊 / 会议系列')}<input form={formId} list="venues" value={venueText} onFocus={()=>void ensureVenues()} onChange={e=>{setVenueText(e.target.value);void ensureVenues();}} placeholder={t('输入名称或编号')}/><datalist id="venues">{choices.map(v=><option key={v.kind+v.number} value={v.number+' · '+v.title}/>)}</datalist>{venuesFailed&&<span className="hint" role="status">{t('刊会列表暂不可用，可输入刊会编号。')}</span>}</label>
       {(['abstract_state','keywords_state'] as const).map(k=><label key={k}>{k==='abstract_state'?t('摘要状态'):t('关键词状态')}<select form={formId} value={filters[k]} onChange={e=>update(k,e.target.value)}><option value="">{t('全部状态')}</option>{['complete','pending','no_data','failed'].map(s=><option key={s} value={s}>{t(contentStateNames[s])}</option>)}</select></label>)}
      </section>}
      {arxiv&&<section key="arxiv" className={'filter-source-group'+(both?' is-grouped':'')} aria-label={both?t('arXiv 筛选'):undefined}>
       {both&&<h2 className="filter-source-heading"><SourceBadge source="arxiv"/>{t('学科分类')}</h2>}
       <ArxivCategoryFilter value={filters.category} defaultOpen={!both||!!filters.category} onChange={category=>applySearch({...filters,category})}/>
       {!both&&<h2 className="filter-heading">{t('更多条件')}</h2>}
       <label>{t('分类代码')}<input form={formId} list="arxiv-categories" value={filters.category} onChange={e=>update('category',e.target.value.trim())} placeholder={t('如 eess.SP,cs.AR（逗号分隔）')}/><datalist id="arxiv-categories">{categoryChoices.map(category=><option key={category.code} value={category.code} label={category.name||undefined}/>)}</datalist></label>
      </section>}
      <form id={formId} className="filter-form" aria-labelledby={both?'filter-form-title':undefined} aria-label={both?undefined:t('更多条件')} onSubmit={e=>{e.preventDefault();applySearch(filters);}}>
       {both&&<h2 id="filter-form-title" className="filter-source-heading">{t('年份')}</h2>}
       <div className="year-range"><label>{t('起始年份')}<select aria-label={t('起始年份')} value={filters.year_from} onChange={e=>update('year_from',e.target.value)}><option value="">{t('不限')}</option>{years.map(year=><option key={year} value={year} disabled={!!filters.year_to&&year>Number(filters.year_to)}>{year}</option>)}</select></label><label>{t('结束年份')}<select aria-label={t('结束年份')} value={filters.year_to} onChange={e=>update('year_to',e.target.value)}><option value="">{t('不限')}</option>{years.map(year=><option key={year} value={year} disabled={!!filters.year_from&&year<Number(filters.year_from)}>{year}</option>)}</select></label></div>
       <div className="filter-actions"><button type="submit" className="primary" disabled={busy||invalidYearRange(filters)}>{t('应用筛选')}</button><button type="button" className="ghost" onClick={clearAll}>{t('清除全部条件')}</button></div>
       {pending&&<p className="filter-pending" role="status">{t('有未应用的更改')}</p>}
      </form>
     </div>
    </details>
   </aside>
   <section className="results" aria-labelledby="results-title">
    {appliedIeee&&applied.field==='authors'&&(applied.q.trim()||applied.author_id)&&<AuthorSearch query={applied.q} authorId={applied.author_id} source={applied.author_source||'ieee'} fetcher={api} onSelect={author=>applySearch({...filters,field:'authors',q:applied.q,author_source:author.source,author_id:author.author_id,author_unidentified:''})} onUnknown={()=>applySearch({...filters,field:'authors',q:applied.q,author_source:'',author_id:'',author_unidentified:'1'})}/>}
    {appliedIeee&&(applied.author_id||applied.author_unidentified)&&<div className="selected-author" role="status"><Icon name="user"/><span>{applied.author_id?t('当前限定作者：IEEE ID ')+applied.author_id:t('当前查看：未提供作者 ID 的署名记录')}</span><button type="button" className="ghost" onClick={()=>{applySearch({...filters,author_id:'',author_source:'',author_unidentified:''});keepFocus();}}>{t('清除作者限定')}</button></div>}
    {activeCount>0&&<div className="active-filters" role="group" aria-label={t('当前条件')}><span className="active-filters-label">{t('当前条件')}</span>{chips.map(chip=><button type="button" key={chip.key} className="filter-chip" aria-label={t('移除条件：{name}',{name:(appliedBoth&&chip.source?sourceLabel[chip.source]+' ':'')+chip.label})} onClick={()=>removeFilter(chip.remove)}>{appliedBoth&&chip.source&&<SourceBadge source={chip.source}/>}<span>{chip.label}</span><Icon name="close"/></button>)}<button type="button" className="text-button" onClick={clearAll}>{t('清除全部条件')}</button></div>}
    {applied.q.trim()&&<SearchInsights query={insight.query} fulltext={insight.fulltext} field={applied.field} onTerm={term=>applySearch({...filters,q:term})}/>}
    <div className="result-toolbar"><h2 id="results-title" ref={resultsTitle} tabIndex={-1}>{topView?t('最相关论文'):applied.q?t('检索结果'):t('浏览论文')}</h2><span className="result-count" role="status">{totalText&&<span className="result-total">{totalText}{countFailed&&rowInfo&&<button type="button" className="text-button" onClick={()=>void readCount(applied,latestRequest.current)}>{t('重试统计')}</button>}</span>}{breakdown.length>0&&<span className="result-sources">{breakdown.join(' · ')}</span>}<span className="result-loaded">{t('已载入 {n} 条',{n:fmt(rows.length)})}</span></span>{!topView&&<PageSizeControl value={applied.limit} onChange={limit=>applySearch({...applied,limit},applied.venue)}/>}</div>
    {partial&&<div className="source-alert" role="alert"><Icon name="info"/><span>{t('{source} 暂时无法检索，当前结果不含该来源。',{source:unavailable.map(source=>sourceLabel[source]).join(' / ')})}</span><button type="button" className="text-button" disabled={busy} onClick={()=>void load(applied)}>{t('重试')}</button></div>}
    {onlySource&&!partial&&<p className="source-note" role="status">{t('当前字段仅匹配 {source} 论文',{source:sourceLabel[onlySource]})}</p>}
    {unconfigured&&<p className="source-note" role="status">{t('arXiv 检索暂未启用')}</p>}
    <PaperSelectionToolbar total={rows.length} count={selectedRows.length} disabled={busy} onAll={checked=>dispatchResults({type:'all',checked})} onCite={()=>setCitationKeys(selectedRows.map(row=>row.number))} onDownload={()=>setDownloadKeys(selectedRows.map(row=>row.number))}/>
    {error&&<div className="error-box" role="alert"><span>{t(error)}</span>{!busy&&<button type="button" className="text-button" onClick={()=>void load(applied)}>{t('重试')}</button>}</div>}
    {busy&&!rows.length?<div className="paper-list is-loading" role="status"><span className="sr-only">{t('正在检索…')}</span>{[0,1,2].map(i=><div className="paper-skeleton" key={i} aria-hidden="true"><i/><i/><i/></div>)}</div>
    :!rows.length?(!error&&<div className="empty"><Icon name="search"/><h3>{applied.field==='body'&&!applied.q.trim()?t('输入要在正文中查找的词句'):t('当前范围未找到记录')}</h3>{!(applied.field==='body'&&!applied.q.trim())&&<p>{applied.field==='body'?t('仅检索已索引正文，可尝试其他词句或切换元数据检索。'):appliedBoth?t('试试其他搜索词，或放宽筛选条件。'):appliedArxiv?t('试试其他搜索词，或放宽分类和年份条件。'):t('试试其他搜索词，或放宽刊会和年份条件。')}</p>}{activeCount>0&&<button type="button" onClick={clearAll}>{t('清除全部条件')}</button>}</div>)
    :<div className="paper-list">{rows.map(row=>{const checked=selectedKeys.has(row.number);
     if(row.source==='ieee'){const p=row.paper;return <article className={'paper-row'+(checked?' paper-selected':'')} data-source="ieee" key={row.number}>
      <label className="paper-selection-control"><input type="checkbox" checked={checked} disabled={busy} aria-label={t('选择论文：')+(p.title||p.number)} onChange={e=>dispatchResults({type:'select',numbers:[row.number],checked:e.target.checked})}/></label>
      <div className="paper-body">
       <a className="paper-title" data-copy-content="title" href={'/papers/'+p.number} onClick={e=>{if(e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();open(p.number);}}><ScientificTitle value={p.title} fallback={t('未提供标题')}/></a>
       <AuthorLinks references={p.author_refs} fallback={p.authors}/>
       <div className="paper-source"><SourceBadge source="ieee"/>{p.position&&<span className="paper-position">#{p.position}</span>}<span className="paper-year">{p.year||'—'}</span>{p.kind&&<span className="paper-kind">{contentTypeLabel(p.kind)}</span>}<div className="publication-line"><VenueTags paper={p}/><p className="publication">{p.publication}</p></div></div>
       {topView&&<MatchReasons paper={p}/>}
       {applied.field==='body'?<PassageHits paper={p} query={applied.q} terms={applied.terms} onOpen={open}/>:p.excerpt?<p className="match-excerpt"><span>{t(p.excerpt.field==='keywords'?'关键词':'摘要')}</span><Highlighted value={p.excerpt}/></p>:p.snippet&&<AbstractPreview number={p.number} preview={p.snippet} fetcher={api}/>}
       <div className="paper-meta"><button type="button" className="citation-trigger" aria-label={t('获取引用格式：')+(p.title||p.number)} onClick={()=>setCitationKeys([row.number])}><Icon name="quote"/>{t('引用')}</button><FavoriteButton target={favoriteTarget(row)} title={p.title||p.number}/>{p.resources?.[0]&&readingHref(p.resources[0])&&<a className="button resource-shortcut" href={readingHref(p.resources[0])} target="_blank" rel="noopener noreferrer"><Icon name="file"/>{localizedText(p.resources[0].label_i18n,p.resources[0].label)}<Icon name="external" className="icon-trailing"/></a>}<code className="paper-number" title={t('论文编号')}>{p.number}</code></div>
      </div>
     </article>;}
     const p=row.paper,href=new URLSearchParams(linkParams);if(p.requested_version)href.set('v',String(p.requested_version));
     return <article className={'paper-row'+(checked?' paper-selected':'')} data-source="arxiv" key={row.number}>
      <label className="paper-selection-control"><input type="checkbox" checked={checked} disabled={busy} aria-label={t('选择论文：')+(p.title||p.arxiv_id)} onChange={e=>dispatchResults({type:'select',numbers:[row.number],checked:e.target.checked})}/></label>
      <div className="paper-body">
       <a className="paper-title" data-copy-content="title" href={'/arxiv/papers/'+p.paper_id+(String(href)?'?'+href:'')} onClick={remember}><ScientificTitle value={p.title} fallback={t('未提供标题')}/></a>
       <p className="authors">{decodeTexAccents(p.authors_raw||'')}</p>
       <div className="paper-source"><SourceBadge source="arxiv"/>{p.position&&<span className="paper-position">#{p.position}</span>}<time className="paper-year" dateTime={p.submitted_at||undefined} title={t('首次投稿日期（UTC+8）')}>{arxivDate(p.submitted_at,t('日期未提供'))}</time><div className="publication-line arxiv-categories">{(p.categories||[]).map(code=><button type="button" className={'arxiv-category-tag'+(appliedArxiv&&selectedArxivCategories(applied.category).includes(code)?' is-active':'')} key={code} title={arxivCategoryName(code)} aria-label={t('按分类筛选：{name}',{name:arxivCategoryLabel(code)})} onClick={()=>applySearch({...applied,category:toggleArxivCategory(applied.category,code)},applied.venue)}>{code}</button>)}</div></div>
       <AbstractPreview number={p.paper_id} preview={p.abstract||''} fetcher={async()=>({paper:{record:{abstract:p.abstract}}})}/>
       <div className="paper-meta"><button type="button" className="citation-trigger" aria-label={t('获取引用格式：')+(p.title||p.arxiv_id)} onClick={()=>setCitationKeys([row.number])}><Icon name="quote"/>{t('引用')}</button><FavoriteButton target={favoriteTarget(row)} title={p.title||p.arxiv_id}/><code className="paper-number" title={t('论文编号')}>{p.arxiv_id}</code></div>
      </div>
     </article>;})}</div>}
    {cursor&&<button className="load-more" disabled={busy} onClick={()=>void load(applied,cursor)}>{busy?t('加载中…'):t('加载更多论文')}</button>}
   </section>
  </div>
 </main><SelectionCopy/><BackToTop target={browseTop}/>
 {citationKeys.length>0&&<React.Suspense fallback={<p className="hint" role="status">{t('正在生成引用…')}</p>}><CitationDialog numbers={citationKeys} fetcher={citationFetcher} filenamePrefix={citationKeys.every(key=>parsePaperKey(key).source==='arxiv')?'arxiv':'ieee'} onClose={()=>setCitationKeys([])}/></React.Suspense>}
 {downloadKeys&&<React.Suspense fallback={<p className="hint" role="status">{t('正在读取下载信息…')}</p>}><BatchDownloadDialog selected={rows.filter(row=>downloadKeys.includes(row.number)).map(row=>({number:row.number,title:row.paper.title,year:row.paper.year}))} fetcher={downloadFetcher} source={downloadKeys.every(key=>parsePaperKey(key).source==='arxiv')?'arxiv':'ieee'} onClose={()=>setDownloadKeys(null)}/></React.Suspense>}
 </>;
}
