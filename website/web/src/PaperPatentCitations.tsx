import {useEffect,useRef,useState} from 'react';
import ScientificTitle from './ScientificTitle';
import {citationNotice,citationTime,type CitationSummary} from './citationSummary';
import {locale,t,useLanguage} from './i18n';
import {PATENT_CITATION_PAGE_SIZE,mergePatentCitationPage,patentCitationCount,patentCitationLabel,patentCitationLink,patentCitationsPending,patentSourceAbsent,validatePatentCitationPage,type PatentCitationsPage} from './patentCitationData';
type Fetcher=(path:string,method?:string,data?:unknown)=>Promise<any>;
const fmt=(value:number)=>value.toLocaleString(locale());
function date(value:string|null){const parsed=value?new Date(value):null;return !parsed||Number.isNaN(parsed.getTime())?t('尚未检查'):parsed.toLocaleString(locale());}

export default function PaperPatentCitations({number,fetcher,embedded=false,onSummary}:{number:string;fetcher:Fetcher;embedded?:boolean;onSummary?:(value:CitationSummary)=>void}){
 useLanguage();
 const [expanded,setExpanded]=useState(false),[page,setPage]=useState<PatentCitationsPage|null>(null),[loading,setLoading]=useState(true),[more,setMore]=useState(false),[error,setError]=useState('');
 const current=useRef<PatentCitationsPage|null>(null),generation=useRef(0),mounted=useRef(false),ensured=useRef(false),paging=useRef(false),timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
 const base='/api/papers/'+encodeURIComponent(number)+'/patent-citations',panelId='paper-patent-citations-'+number,contentId=panelId+'-content';
 function clearTimer(){if(timer.current!==undefined)clearTimeout(timer.current);timer.current=undefined;}
 function active(request:number){return mounted.current&&request===generation.current;}
 function fail(reason:unknown){setError(reason instanceof Error&&reason.message==='patent_citation_snapshot_mismatch'?t('专利被引快照不一致，请刷新状态后重试。'):t('专利被引暂不可读取。'));}
 function apply(value:PatentCitationsPage){
  validatePatentCitationPage(value,number);const next=mergePatentCitationPage(current.current,value);
  if(next.version!==current.current?.version){paging.current=false;setMore(false);}
  current.current=next;setPage(next);
 }
 async function readStatus(request:number,action:'open'|'status'|'update'){
  let pending=patentCitationsPending(current.current);
  try{
   const first:PatentCitationsPage=action==='update'?await fetcher(base+'/ensure','POST',{refresh:true}):await fetcher(base+'?'+new URLSearchParams({offset:'0',limit:String(PATENT_CITATION_PAGE_SIZE)}));
   if(!active(request))return;
   apply(first);pending=patentCitationsPending(first);setError('');
   if(action==='open'&&first.state!=='disabled'&&!ensured.current){
    ensured.current=true;const ensuredPage:PatentCitationsPage=await fetcher(base+'/ensure','POST',{});
    if(!active(request))return;
    apply(ensuredPage);pending=patentCitationsPending(ensuredPage);
   }
  }catch(reason){pending=false;if(active(request))fail(reason);}
  finally{if(active(request)){setLoading(false);if(pending)timer.current=setTimeout(()=>void readStatus(request,'status'),2000);}}
 }
 useEffect(()=>{
  mounted.current=true;ensured.current=false;current.current=null;paging.current=false;setPage(null);setExpanded(false);setLoading(true);setMore(false);setError('');
  void readStatus(++generation.current,'open');
  return()=>{mounted.current=false;generation.current++;clearTimer();};
 },[number,fetcher]);
 function refresh(action:'status'|'update'){
  if(action==='update'&&(current.current?.state==='disabled'||patentCitationsPending(current.current)))return;
  clearTimer();paging.current=false;setMore(false);setError('');setLoading(true);void readStatus(++generation.current,action);
 }
 async function loadMore(){
  const snapshot=current.current;if(!snapshot?.version||snapshot.next_offset===null||paging.current)return;
  const request=generation.current,version=snapshot.version;paging.current=true;setMore(true);setError('');
  try{
   const next:PatentCitationsPage=await fetcher(base+'?'+new URLSearchParams({offset:String(snapshot.next_offset),limit:String(PATENT_CITATION_PAGE_SIZE),version}));
   if(!active(request)||current.current?.version!==version)return;
   validatePatentCitationPage(next,number);const merged=mergePatentCitationPage(current.current,next,true);current.current=merged;setPage(merged);
  }catch(reason){if(active(request))fail(reason);}
  finally{if(active(request)&&current.current?.version===version){paging.current=false;setMore(false);}}
 }
 const pending=patentCitationsPending(page),count=patentCitationCount(page),absent=!!page&&patentSourceAbsent(page);
 const heading=absent?t('官网未提供'):page?.total?count===page.total?t('共 {total} 条',{total:fmt(page.total)}):t('已保存 {total} 条',{total:fmt(page.total)}):count===0?t('共 {total} 条',{total:'0'}):null;
 useEffect(()=>onSummary?.({count:count??null,absent}),[count,absent,onSummary]);
 const contentExpanded=embedded||expanded;
 const notice=citationNotice({kind:'patents',state:page?.state||'missing',absent,count,hasSnapshot:!!page?.version,hasItems:!!page?.items.length,stale:!!page?.stale,error:page?.error||null});
 const checked=citationTime(page),showCount=!!page&&!absent&&(count!==undefined||page.items.length>0);
 return <section id={panelId} className={embedded?'paper-patent-citations citation-content-embedded':'panel paper-patent-citations'} aria-label={t('专利被引')}>
  {!embedded&&<div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={expanded?t('收起专利被引'):t('展开专利被引')} aria-controls={contentId} aria-expanded={expanded} onClick={()=>setExpanded(value=>!value)}>{t('专利被引')}</button></h2>{!expanded&&heading&&<span className="muted">{heading}</span>}</div>}
  <div id={contentId} hidden={!contentExpanded}>{contentExpanded&&<>
   <div className="references-status">{!error&&<span role="status">{loading?t('正在读取专利被引…'):t(notice)}</span>}<div className="citation-update-actions"><button type="button" className="text-button" disabled={loading} onClick={()=>refresh('status')}>{t('刷新状态')}</button><button type="button" disabled={loading||pending||!page||page.state==='disabled'} onClick={()=>refresh('update')}>{t('更新专利被引')}</button></div></div>
   {(showCount||checked)&&<div className="citation-snapshot-meta patent-snapshot-meta">{showCount&&<span>{count!==undefined?t('已载入 {loaded} / {total} 条',{loaded:fmt(page!.items.length),total:fmt(count)}):t('已载入 {loaded} 条',{loaded:fmt(page!.items.length)})}</span>}{checked&&<time dateTime={checked.value} title={page?.last_attempt_at&&page.last_attempt_at!==checked.value?t('最近更新尝试：{time}',{time:date(page.last_attempt_at)}):undefined}>{t(checked.checked?'检查：{time}':'尝试：{time}',{time:date(checked.value)})}</time>}</div>}
   {error&&<p className="error" role="alert">{t(error)}</p>}
   {!!page?.items.length&&<ol className="paper-reference-list paper-patent-citation-list">{page.items.map(item=>{
    const link=patentCitationLink(item),content=<ScientificTitle value={item.text||item.title} fallback={t('未提供专利被引文本')}/>;
    const metadata=[item.publication_number,item.country,item.publication_date,item.inventors?.join(', '),item.assignee].filter(Boolean).join(' · ');
    return <li key={page.version+':'+item.order} data-patent-citation-order={item.order}><span className="reference-number">{patentCitationLabel(item)}</span><div className="reference-text">{link?<a href={link.href} target="_blank" rel="noopener noreferrer" className="paper-reference-link">{content}</a>:content}{metadata&&<small className="patent-citation-metadata">{metadata}</small>}{link&&<small>{link.kind==='patent'?t('Google Patents 专利'):t('Google Patents 搜索')} ↗</small>}</div></li>;
   })}</ol>}
   {page?.version&&page.next_offset!==null&&<button type="button" className="load-more reference-load-more" disabled={more||loading} onClick={()=>void loadMore()}>{more?t('正在载入专利被引…'):t('加载更多专利被引')}</button>}
  </>}</div>
 </section>;
}
