import React,{useEffect,useRef,useState} from 'react';
import {t,useLanguage,localizedText,contentTypeLabel} from './i18n';
import {api} from './api';
import {fmt,time,contentStateNames} from './format';
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
import {AuthorLinks,AuthorSearch} from './AuthorSearch';
import {VenueFamilyFilter,VenueTags} from './VenueTags';
import {orderVenueFamilies,selectedVenueFamilies,venueFamilies,venueNumbers} from './venueFamilies';
import {resultSelection} from './resultSelection';
import type {SelectedPaper} from './paperBatch';
import type {Filters,FulltextStatus,Index,Paper,QueryInfo,Venue} from './types';
const BatchDownloadDialog=React.lazy(()=>import('./BatchDownloadDialog'));
const CitationDialog=React.lazy(()=>import('./CitationDialog'));
const sidebarQuery='(min-width:1024px)';
const draftKeys=['kind','year_from','year_to','abstract_state','keywords_state'] as const;
function invalidYearRange(f:Pick<Filters,'year_from'|'year_to'>){return !!f.year_from&&!!f.year_to&&Number(f.year_from)>Number(f.year_to);}
function query(f:Filters){return '/?'+new URLSearchParams(Object.entries(f).filter(([key,value])=>key!=='cursor'&&!!value));}

export default function ReaderPage(){
 useLanguage();
 const browseTop=useRef<HTMLHeadingElement>(null),resultsTitle=useRef<HTMLHeadingElement>(null);
 const [citationNumbers,setCitationNumbers]=useState<string[]>([]),[downloadSelection,setDownloadSelection]=useState<SelectedPaper[]|null>(null);
 // Selection belongs to the rows on screen, never to a hidden cross-search basket.
 const [results,dispatchResults]=React.useReducer(resultSelection<Paper>,{rows:[],selected:[]});
 const {rows}=results,selectedKeys=new Set(results.selected);
 function snapshot(p:Paper):SelectedPaper{return {number:p.number,title:p.title,year:p.year,kind:p.kind,venue:p.venue,venue_series:p.venue_series,publication:p.publication};}
 const selected=rows.filter(p=>selectedKeys.has(p.number)).map(snapshot);
 function selectPapers(papers:Paper[],checked:boolean){dispatchResults({type:'select',numbers:papers.map(p=>p.number),checked});}
 useEffect(()=>{try{sessionStorage.removeItem('cirdc.selected-papers.v1');}catch{/* Legacy baskets are never restored. */}},[]);
 // The sidebar is always shown on wide screens; narrower screens fold it into a disclosure.
 const [filtersOpen,setFiltersOpen]=useState(()=>window.matchMedia(sidebarQuery).matches);
 useEffect(()=>{const media=window.matchMedia(sidebarQuery),change=()=>{if(media.matches)setFiltersOpen(true);};media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
 const latestRequest=useRef(0);
 const totalAbort=useRef<AbortController|null>(null),totalFrames=useRef<number[]>([]),totalUrl=useRef(''),venuesRequest=useRef<Promise<void>|null>(null);
 const [totalFailed,setTotalFailed]=useState(false),[venuesFailed,setVenuesFailed]=useState(false);
 const [insight,setInsight]=useState<{query?:QueryInfo;fulltext?:FulltextStatus|null;exact:boolean}>({exact:true});
 function cancelTotal(){totalAbort.current?.abort();totalFrames.current.forEach(cancelAnimationFrame);totalFrames.current=[];}
 useEffect(()=>()=>cancelTotal(),[]);
 async function readTotal(url:string,request:number){
  if(request!==latestRequest.current)return;
  totalAbort.current?.abort();const controller=new AbortController();totalAbort.current=controller;setTotalFailed(false);
  try{const value=await api(url,'GET',undefined,controller.signal);if(typeof value.total!=='number')throw Error('missing_total');if(request===latestRequest.current&&!controller.signal.aborted)setTotal(value.total);}
  catch{if(request===latestRequest.current&&!controller.signal.aborted)setTotalFailed(true);}
 }
 function queueTotal(params:URLSearchParams,request:number){
  const count=new URLSearchParams(params);count.delete('cursor');count.delete('limit');count.set('totals','only');const url='/api/papers?'+count;totalUrl.current=url;
  // Leave one painted frame for the current rows before counting all matches.
  totalFrames.current.push(requestAnimationFrame(()=>{totalFrames.current.push(requestAnimationFrame(()=>void readTotal(url,request)));}));
 }
 function ensureVenues(){
  if(venuesRequest.current)return venuesRequest.current;
  setVenuesFailed(false);
  const pending=api('/api/venues').then(value=>{if(!Array.isArray(value.items))throw Error('invalid_venues');setVenues(value.items);}).catch(()=>{venuesRequest.current=null;setVenuesFailed(true);});
  venuesRequest.current=pending;return pending;
 }
 const defaults:Filters={limit:storedPageSize(),venue_tags:'',q:'',field:'all',kind:'',venue:'',year_from:'',year_to:'',abstract_state:'',keywords_state:'',sort:'relevance',author_source:'',author_id:'',author_unidentified:'',view:'',k:'',terms:''};
 const initial={...defaults,...Object.fromEntries(new URLSearchParams(window.location.search))};
 initial.limit=normalizePageSize(initial.limit,defaults.limit);
 initial.venue_tags=selectedVenueFamilies(initial.venue_tags).map(f=>f.key).join(',');
 const [filters,setFilters]=useState<Filters>(initial),[applied,setApplied]=useState<Filters>(initial),[venueText,setVenueText]=useState(initial.venue),[venues,setVenues]=useState<Venue[]>([]),[index,setIndex]=useState<Index>(),[cursor,setCursor]=useState<string|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[partial,setPartial]=useState(false),[total,setTotal]=useState<number|null>(null),[detail,setDetail]=useState<string|null>(window.location.pathname.match(/^\/papers\/(\d+)/)?.[1]||null);
 useEffect(()=>{try{localStorage.setItem(pageSizePreference,applied.limit);}catch{/* The URL still preserves this setting. */}},[applied.limit]);
 function changePageSize(limit:string){
  const next={...applied,limit};setFilters(old=>({...old,limit}));setApplied(next);
  history.replaceState({},'',query(next));
  void load(next);
 }
 function update(k:keyof Filters,v:string){setFilters(f=>({...f,[k]:v}));if(k==='year_from'||k==='year_to')setError('');}
 async function load(f:Filters,more?:string){const request=++latestRequest.current;cancelTotal();totalUrl.current='';setTotalFailed(false);setBusy(true);setError('');if(!more){
  setCursor(null);setTotal(null);dispatchResults({type:'reset'});
 }if(invalidYearRange(f)){
  setBusy(false);setTotalFailed(true);setError(t('起始年份不能晚于结束年份。'));return;
 }try{
  const {venue_tags,...query}=f;
  const params=new URLSearchParams(Object.entries(query).filter(([key,v])=>key!=='cursor'&&!!v));
  const publicationIds=venueNumbers(venue_tags);
  if(publicationIds.length)params.set('venue_any',publicationIds.join(','));
  if(more)params.set('cursor',more);
  params.set('totals','defer');
  const r=await api('/api/papers?'+params);
  if(request!==latestRequest.current)return;
  dispatchResults({type:more?'append':'replace',rows:r.items});
  setInsight({query:r.query,fulltext:r.fulltext,exact:r.total_exact!==false});
  setCursor(r.next_cursor);
  if(typeof r.total==='number')setTotal(r.total);else queueTotal(params,request);
  setPartial(!!r.partial);
 }catch(e){
  if(request===latestRequest.current){setError((e as Error).message);setTotalFailed(true);}
 }finally{
  if(request===latestRequest.current)setBusy(false);
 }}
 async function overview(){try{const r=await api('/api/overview');setIndex(r.index);}catch(e){setError((e as Error).message);}}
 useEffect(()=>{void overview();if(!detail){const params=new URLSearchParams(window.location.search);params.set('limit',initial.limit);params.delete('cursor');history.replaceState({},'','/?'+params);void load(initial);}const timer=setInterval(()=>void overview(),60000);const pop=()=>{
  const number=window.location.pathname.match(/^\/papers\/(\d+)/)?.[1]||null;setDetail(number);
  if(!number){
   const next={...defaults,limit:storedPageSize(),...Object.fromEntries(new URLSearchParams(window.location.search))};
   next.limit=normalizePageSize(next.limit);next.venue_tags=selectedVenueFamilies(next.venue_tags).map(f=>f.key).join(',');
   setFilters(next);setApplied(next);setVenueText(next.venue);void load(next);
  }
 };window.addEventListener('popstate',pop);return()=>{clearInterval(timer);window.removeEventListener('popstate',pop);};},[]);
 function applySearch(next:Filters,venueInput=venueText){if(invalidYearRange(next)){setError(t('起始年份不能晚于结束年份。'));return;}const value=venueInput.split(' · ')[0].trim();if(value&&!/^\d+$/.test(value)){
  setError(t('请从候选列表选择刊会，或输入刊会编号。'));
  return;
 }const resetAuthor=next.field==='authors'&&next.q!==applied.q;const f={...next,venue:value,...(resetAuthor?{author_source:'',author_id:'',author_unidentified:''}:{})};setFilters(f);setApplied(f);history.replaceState({},'',query(f));void load(f);}
 function submit(e:React.FormEvent){e.preventDefault();applySearch(filters);}
 function updateSearchOption(key:'field'|'sort'|'view'|'k'|'terms',value:string){if(filters[key]===value)return;const next={...filters,[key]:value};setFilters(next);applySearch(next);}
 // A removed control would drop keyboard focus to the page; continue from the results instead.
 function keepFocus(){requestAnimationFrame(()=>{if(!document.activeElement||document.activeElement===document.body)resultsTitle.current?.focus({preventScroll:true});});}
 // Removing one applied condition keeps the other applied values and discards unapplied drafts.
 function removeFilter(patch:Partial<Filters>){const next={...applied,...patch};if('venue' in patch)setVenueText(next.venue);applySearch(next,next.venue);keepFocus();}
 function clearAll(){const cleared={...defaults,limit:applied.limit};setFilters(cleared);setVenueText('');setApplied(cleared);history.replaceState({},'','/?limit='+cleared.limit);void load(cleared);keepFocus();}
 function open(number:string,href='/papers/'+number){history.pushState({},'',href);setDetail(number);window.scrollTo(0,0);}
 function back(){setDetail(null);history.pushState({},'',query(applied));if(!rows.length)void load(applied);}
 function searchFromPaper(text:string){
  const next={...defaults,limit:applied.limit,q:text,field:'all',sort:'relevance'};
  setFilters(next);setApplied(next);setVenueText('');setDetail(null);
  history.pushState({},'',query(next));
  void load(next);window.scrollTo(0,0);
 }
 if(detail)return <><PaperDetail number={detail} back={back} initialQuery={applied.q} onSearch={searchFromPaper}/><SelectionCopy/></>;
 const choices=venues.filter(v=>(!filters.kind||v.kind===filters.kind)&&(!venueText||(v.number+' '+v.title).toLowerCase().includes(venueText.toLowerCase()))).slice(0,80);
 const latestYear=Math.min(2200,Math.max(new Date().getFullYear(),index?.year_range?.max||0,Number(filters.year_from)||0,Number(filters.year_to)||0));
 const years=Array.from({length:latestYear-1800+1},(_,i)=>latestYear-i);
 const pending=draftKeys.some(key=>filters[key]!==applied[key])||venueText.split(' · ')[0].trim()!==applied.venue;
 const families=orderVenueFamilies(selectedVenueFamilies(applied.venue_tags));
 const kindLabel=(kind:string)=>kind==='Journals'?t('期刊'):kind==='Conferences'?t('会议'):kind;
 const chips:{key:string;label:string;remove:Partial<Filters>}[]=[
  ...(applied.kind?[{key:'kind',label:kindLabel(applied.kind),remove:{kind:''}}]:[]),
  ...(applied.venue?[{key:'venue',label:venues.find(v=>v.number===applied.venue)?.title||t('刊会编号 {n}',{n:applied.venue}),remove:{venue:''}}]:[]),
  ...(applied.year_from||applied.year_to?[{key:'years',label:applied.year_from&&applied.year_to?applied.year_from+'–'+applied.year_to:applied.year_from?t('{year} 年起',{year:applied.year_from}):t('至 {year} 年',{year:applied.year_to}),remove:{year_from:'',year_to:''}}]:[]),
  ...(applied.abstract_state?[{key:'abstract',label:t('摘要：')+t(contentStateNames[applied.abstract_state]||applied.abstract_state),remove:{abstract_state:''}}]:[]),
  ...(applied.keywords_state?[{key:'keywords',label:t('关键词：')+t(contentStateNames[applied.keywords_state]||applied.keywords_state),remove:{keywords_state:''}}]:[]),
  ...families.map(f=>({key:'family-'+f.key,label:f.label,remove:{venue_tags:venueFamilies.filter(x=>x.key!==f.key&&families.some(s=>s.key===x.key)).map(x=>x.key).join(',')}})),
 ];
 const activeCount=chips.length,topView=applied.view==='top';
 return <><main id="main" className="workspace reader-workspace" data-copy-scope>
  <div className="reader-hero"><div className="reader-hero-title"><h1 ref={browseTop} tabIndex={-1}>{t('论文检索')}</h1><p className="muted">{t('从标题到摘要，查找你关心的电路、方法与作者。')}</p></div><OverviewCards overview={index?.overview} compact/></div>
  <form className="search-box" role="search" aria-label={t('文献库检索')} onSubmit={submit}>
   <div className="search-main"><Icon name="search" className="search-icon"/><input aria-label={t('搜索论文')} placeholder={filters.field==='authors'?t('输入作者姓名或 IEEE 作者 ID'):filters.field==='body'?t('输入正文中的词、短语或一句原文'):t('搜索论文、作者、关键词，或输入编号 / DOI')} maxLength={filters.field==='body'?600:200} value={filters.q} onChange={e=>update('q',e.target.value)}/><button className="primary" disabled={busy||invalidYearRange(filters)}>{t('检索')}</button></div>
   <div className="search-options">
    <div className="search-option-section"><span className="search-option-label">{t('检索字段')}</span><div className="search-choice-group field-choices" role="group" aria-label={t('检索字段')}>{[['all',t('全部')],['title',t('标题')],['authors',t('作者')],['keywords',t('关键词')],['abstract',t('摘要')],['body',t('正文')]].map(([v,l])=><button key={v} type="button" className="search-choice" aria-pressed={filters.field===v} onClick={()=>updateSearchOption('field',v)}>{l}</button>)}</div></div>
    <div className="search-option-section"><span className="search-option-label">{t('结果')}</span><div className="search-choice-group" role="group" aria-label={t('结果视图')}>{[['',t('全部匹配')],['top',t('最相关')]].map(([v,l])=><button key={v||'all'} type="button" className="search-choice" aria-pressed={filters.view===v} onClick={()=>updateSearchOption('view',v)}>{l}</button>)}</div>{filters.view==='top'&&<select className="top-k-select" aria-label={t('返回篇数')} value={filters.k||'20'} onChange={e=>updateSearchOption('k',e.target.value==='20'?'':e.target.value)}>{['10','20','50','100'].map(k=><option key={k} value={k}>{t('前 {k} 篇',{k})}</option>)}</select>}</div>
    {filters.view!=='top'&&<div className="search-option-section"><span className="search-option-label">{t('排序')}</span><div className="search-choice-group" role="group" aria-label={t('排序')}>{[['relevance',t('相关度')],['year',t('年份从新到旧')]].map(([v,l])=><button key={v} type="button" className="search-choice" aria-pressed={filters.sort===v} onClick={()=>updateSearchOption('sort',v)}>{l}</button>)}</div></div>}
    <label className="alias-toggle" title={t('关闭后只匹配输入的原写法')}><input type="checkbox" checked={filters.terms!=='exact'} onChange={e=>updateSearchOption('terms',e.target.checked?'':'exact')}/><span>{t('等价写法扩展')}</span></label>
   </div>
  </form>
  <div className="reader-layout">
   <aside className="reader-sidebar" aria-label={t('筛选')}>
    <details className="filter-disclosure" open={filtersOpen} onToggle={e=>setFiltersOpen(e.currentTarget.open)}>
     <summary><Icon name="filter"/><span>{t('筛选')}</span>{activeCount>0&&<span className="count-badge" aria-label={t('{n} 个条件生效中',{n:activeCount})}>{activeCount}</span>}<Icon name="down" className="disclosure-caret"/></summary>
     <div className="filter-panel">
      <VenueFamilyFilter value={filters.venue_tags} onChange={value=>applySearch({...filters,venue_tags:value})}/>
      <form className="filter-form" aria-labelledby="filter-form-title" onSubmit={e=>{e.preventDefault();applySearch(filters);}}>
       <h2 id="filter-form-title" className="filter-heading">{t('更多条件')}</h2>
       <fieldset className="segmented-field"><legend>{t('出版物类型')}</legend><div className="segmented">{[['',t('全部类型')],['Journals',t('期刊')],['Conferences',t('会议')]].map(([v,l])=><label key={v||'all'}><input type="radio" name="kind" value={v} checked={filters.kind===v} onChange={()=>{update('kind',v);setVenueText('');update('venue','');}}/><span>{l}</span></label>)}</div></fieldset>
       <label>{t('期刊 / 会议系列')}<input list="venues" value={venueText} onFocus={()=>void ensureVenues()} onChange={e=>{setVenueText(e.target.value);void ensureVenues();}} placeholder={t('输入名称或编号')}/><datalist id="venues">{choices.map(v=><option key={v.kind+v.number} value={v.number+' · '+v.title}/>)}</datalist>{venuesFailed&&<span className="hint" role="status">{t('刊会列表暂不可用，可输入刊会编号。')}</span>}</label>
       <div className="year-range"><label>{t('起始年份')}<select value={filters.year_from} onChange={e=>update('year_from',e.target.value)}><option value="">{t('不限')}</option>{years.map(year=><option key={year} value={year} disabled={!!filters.year_to&&year>Number(filters.year_to)}>{year}</option>)}</select></label><label>{t('结束年份')}<select value={filters.year_to} onChange={e=>update('year_to',e.target.value)}><option value="">{t('不限')}</option>{years.map(year=><option key={year} value={year} disabled={!!filters.year_from&&year<Number(filters.year_from)}>{year}</option>)}</select></label></div>
       {(['abstract_state','keywords_state'] as const).map(k=><label key={k}>{k==='abstract_state'?t('摘要状态'):t('关键词状态')}<select value={filters[k]} onChange={e=>update(k,e.target.value)}><option value="">{t('全部状态')}</option>{['complete','pending','no_data','failed'].map(s=><option key={s} value={s}>{t(contentStateNames[s])}</option>)}</select></label>)}
       <div className="filter-actions"><button type="submit" className="primary" disabled={busy||invalidYearRange(filters)}>{t('应用筛选')}</button><button type="button" className="ghost" onClick={clearAll}>{t('清除全部条件')}</button></div>
       {pending&&<p className="filter-pending" role="status">{t('有未应用的更改')}</p>}
      </form>
     </div>
    </details>
   </aside>
   <section className="results" aria-labelledby="results-title">
    {applied.field==='authors'&&(applied.q.trim()||applied.author_id)&&<AuthorSearch query={applied.q} authorId={applied.author_id} source={applied.author_source||'ieee'} fetcher={api} onSelect={author=>applySearch({...filters,field:'authors',q:applied.q,author_source:author.source,author_id:author.author_id,author_unidentified:''})} onUnknown={()=>applySearch({...filters,field:'authors',q:applied.q,author_source:'',author_id:'',author_unidentified:'1'})}/>}
    {(applied.author_id||applied.author_unidentified)&&<div className="selected-author" role="status"><Icon name="user"/><span>{applied.author_id?t('当前限定作者：IEEE ID ')+applied.author_id:t('当前查看：未提供作者 ID 的署名记录')}</span><button type="button" className="ghost" onClick={()=>{applySearch({...filters,author_id:'',author_source:'',author_unidentified:''});keepFocus();}}>{t('清除作者限定')}</button></div>}
    {activeCount>0&&<div className="active-filters" role="group" aria-label={t('当前条件')}><span className="active-filters-label">{t('当前条件')}</span>{chips.map(chip=><button type="button" key={chip.key} className="filter-chip" aria-label={t('移除条件：{name}',{name:chip.label})} onClick={()=>removeFilter(chip.remove)}><span>{chip.label}</span><Icon name="close"/></button>)}<button type="button" className="text-button" onClick={clearAll}>{t('清除全部条件')}</button></div>}
    {applied.q.trim()&&<SearchInsights query={insight.query} fulltext={insight.fulltext} field={applied.field} onTerm={term=>applySearch({...filters,q:term})}/>}
    <div className="result-toolbar"><h2 id="results-title" ref={resultsTitle} tabIndex={-1}>{topView?t('最相关论文'):applied.q?t('检索结果'):t('浏览论文')}</h2><span className="result-count" role="status"><span className="result-total">{totalFailed?t('总数暂不可用'):total===null?t('正在统计总数…'):topView?t('前 {k} 篇 · 共 {n} 篇匹配',{k:fmt(rows.length),n:fmt(total)}):insight.exact?t('共 {n} 条',{n:fmt(total)}):t('至少 {n} 条（近似候选已截断）',{n:fmt(total)})}{totalFailed&&totalUrl.current&&<button type="button" className="text-button" onClick={()=>void readTotal(totalUrl.current,latestRequest.current)}>{t('重试统计')}</button>}</span><span className="result-loaded">{t('已载入 {n} 条',{n:fmt(rows.length)})}</span>{partial&&<span className="result-partial">{t('索引覆盖或同步尚未完成')}</span>}</span>{!topView&&<PageSizeControl value={applied.limit} onChange={changePageSize}/>}</div>
    <PaperSelectionToolbar total={rows.length} count={selected.length} disabled={busy} onAll={checked=>dispatchResults({type:'all',checked})} onCite={()=>setCitationNumbers(selected.map(p=>p.number))} onDownload={()=>setDownloadSelection(selected)}/>
    {error&&<div className="error-box" role="alert">{t(error)}</div>}
    {busy&&!rows.length?<div className="paper-list is-loading" role="status"><span className="sr-only">{t('正在检索…')}</span>{[0,1,2].map(i=><div className="paper-skeleton" key={i} aria-hidden="true"><i/><i/><i/></div>)}</div>:!rows.length?<div className="empty"><Icon name="search"/><h3>{applied.field==='body'&&!applied.q.trim()?t('输入要在正文中查找的词句'):t('当前范围未找到记录')}</h3><p>{applied.field==='body'?t('正文检索只覆盖已获取并已索引的正文；未出现不代表论文中不存在该内容。'):partial?t('搜索索引仍在构建或同步，可直接输入论文编号查看。'):t('试试其他搜索词，或放宽刊会和年份条件。')}</p>{activeCount>0&&<button type="button" onClick={clearAll}>{t('清除全部条件')}</button>}</div>:<div className="paper-list">{rows.map(p=><article className={'paper-row'+(selectedKeys.has(p.number)?' paper-selected':'')} key={p.number}>
     <label className="paper-selection-control"><input type="checkbox" checked={selectedKeys.has(p.number)} disabled={busy} aria-label={t('选择论文：')+(p.title||p.number)} onChange={e=>selectPapers([p],e.target.checked)}/></label>
     <div className="paper-body">
      <a className="paper-title" data-copy-content="title" href={'/papers/'+p.number} onClick={e=>{if(e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();open(p.number);}}><ScientificTitle value={p.title} fallback={t('未提供标题')}/></a>
      <AuthorLinks references={p.author_refs} fallback={p.authors}/>
      <div className="paper-source">{p.position&&<span className="paper-position">#{p.position}</span>}<span className="paper-year">{p.year||'—'}</span>{p.kind&&<span className="paper-kind">{contentTypeLabel(p.kind)}</span>}<div className="publication-line"><VenueTags paper={p}/><p className="publication">{p.publication}</p></div></div>
      {topView&&<MatchReasons paper={p}/>}
      {applied.field==='body'?<PassageHits paper={p} query={applied.q} terms={applied.terms} onOpen={open}/>:p.excerpt?<p className="match-excerpt"><span>{t(p.excerpt.field==='keywords'?'关键词':'摘要')}</span><Highlighted value={p.excerpt}/></p>:p.snippet&&<AbstractPreview number={p.number} preview={p.snippet} fetcher={api}/>}
      <div className="paper-meta"><button type="button" className="citation-trigger" aria-label={t('获取引用格式：')+(p.title||p.number)} onClick={()=>setCitationNumbers([p.number])}><Icon name="quote"/>{t('引用')}</button>{p.resources?.[0]&&readingHref(p.resources[0])&&<a className="button resource-shortcut" href={readingHref(p.resources[0])} target="_blank" rel="noopener noreferrer"><Icon name="file"/>{localizedText(p.resources[0].label_i18n,p.resources[0].label)}<Icon name="external" className="icon-trailing"/></a>}<code className="paper-number" title={t('论文编号')}>{p.number}</code></div>
     </div>
    </article>)}</div>}
    {cursor&&<button className="load-more" disabled={busy} onClick={()=>void load(applied,cursor)}>{busy?t('加载中…'):t('加载更多论文')}</button>}
    <p className="hint result-note">{t('统计采样于 ')}{time(index?.overview?.sampled_at)}{t('。统计仅反映已有元数据，不代表本轮新抓取或已人工验证。')}</p>
   </section>
  </div>
 </main><SelectionCopy/><BackToTop target={browseTop}/>{citationNumbers.length>0&&<React.Suspense fallback={<p className="hint" role="status">{t('正在生成引用…')}</p>}><CitationDialog numbers={citationNumbers} fetcher={api} onClose={()=>setCitationNumbers([])}/></React.Suspense>}{downloadSelection&&<React.Suspense fallback={<p className="hint" role="status">{t('正在读取下载信息…')}</p>}><BatchDownloadDialog selected={downloadSelection} fetcher={api} onClose={()=>setDownloadSelection(null)}/></React.Suspense>}</>;
}
