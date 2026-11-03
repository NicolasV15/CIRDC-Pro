import {useEffect,useRef,useState} from 'react';
import ScientificTitle from './ScientificTitle';
import {citationNotice,citationTime,type CitationSummary} from './citationSummary';
import {locale,t,useLanguage} from './i18n';
import {referenceLabel,referenceLink} from './paperReferenceData';
import {CITATION_GROUPS,CITATION_PAGE_SIZE,citationCount,citationGroupState,citationItemKey,citationsPending,initialCitationGroup,showCitationGroups,mergeCitationPage,validateCitationPage,type CitationGroup,type CitationsPage} from './paperCitationData';
type Fetcher=(path:string,method?:string,data?:unknown)=>Promise<any>;
type Pages=Record<CitationGroup,CitationsPage|null>;
const emptyPages=():Pages=>({ieee:null,nonIeee:null});
const groupName=(group:CitationGroup)=>t(group==='ieee'?'IEEE 文献':'非 IEEE 文献');
const fmt=(value:number)=>value.toLocaleString(locale());
function date(value:string|null){if(!value)return t('尚未检查');const parsed=new Date(value);return Number.isNaN(parsed.getTime())?t('尚未检查'):parsed.toLocaleString(locale());}

export default function PaperCitations({number,fetcher,embedded=false,onSummary}:{number:string;fetcher:Fetcher;embedded?:boolean;onSummary?:(value:CitationSummary)=>void}){
 useLanguage();
 const [expanded,setExpanded]=useState(false),[group,setGroup]=useState<CitationGroup>('ieee'),[pages,setPages]=useState<Pages>(emptyPages);
 const [loading,setLoading]=useState(true),[more,setMore]=useState<Record<CitationGroup,boolean>>({ieee:false,nonIeee:false}),[error,setError]=useState('');
 const current=useRef<Pages>(emptyPages()),generation=useRef(0),mounted=useRef(false),ensured=useRef(false),timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),paging=useRef(new Set<CitationGroup>());
 const groupChosen=useRef(false);
 const base='/api/papers/'+encodeURIComponent(number)+'/citations',panelId='paper-citations-'+number,contentId=panelId+'-content';
 function clearTimer(){if(timer.current!==undefined)clearTimeout(timer.current);timer.current=undefined;}
 function fail(reason:unknown){setError(reason instanceof Error&&reason.message==='citation_snapshot_mismatch'?t('被引论文快照不一致，请刷新状态后重试。'):reason instanceof Error?reason.message:t('被引论文暂不可读取。'));}
 function applyPair(first:CitationsPage,second:CitationsPage){
  validateCitationPage(first,number,'ieee');validateCitationPage(second,number,'nonIeee');
  if(first.version!==second.version)throw Error('citation_snapshot_mismatch');
  const next={ieee:mergeCitationPage(current.current.ieee,first),nonIeee:mergeCitationPage(current.current.nonIeee,second)};
  if(next.ieee?.version!==current.current.ieee?.version||next.nonIeee?.version!==current.current.nonIeee?.version){paging.current.clear();setMore({ieee:false,nonIeee:false});}
  if(!groupChosen.current){const initial=initialCitationGroup(next);if(initial){groupChosen.current=true;setGroup(initial);}}
  current.current=next;setPages(next);
 }
 function query(group:CitationGroup,version?:string|null){return base+'?'+new URLSearchParams({group,offset:'0',limit:String(CITATION_PAGE_SIZE),...(version?{version}:{})});}
 async function readStatus(request:number,action:'open'|'status'|'update'){
  let pending=false,ensureFailed=false;
  try{
   let first:CitationsPage;
   if(action==='update')first=await fetcher(base+'/ensure','POST',{refresh:true});
   else{
    first=await fetcher(query('ieee'));
    if(!mounted.current||request!==generation.current)return;
    if(action==='open'&&first.state!=='disabled'&&!ensured.current){
     ensured.current=true;
     try{first=await fetcher(base+'/ensure','POST',{});}catch(reason){ensureFailed=true;if(mounted.current&&request===generation.current)fail(reason);}
    }
   }
   if(!mounted.current||request!==generation.current)return;
   validateCitationPage(first,number,'ieee');pending=citationsPending(first);
   const second:CitationsPage=await fetcher(query('nonIeee',first.version));
   if(!mounted.current||request!==generation.current)return;
   validateCitationPage(second,number,'nonIeee');
   if(!first.version&&second.version){
    first=await fetcher(query('ieee',second.version));
    if(!mounted.current||request!==generation.current)return;
    validateCitationPage(first,number,'ieee');
   }
   applyPair(first,{...second,state:first.state,group_states:first.group_states,last_attempt_at:first.last_attempt_at,next_check_at:first.next_check_at,stale:first.stale,error:first.error});
   pending=citationsPending(first);if(!ensureFailed)setError('');
  }catch(reason){if(mounted.current&&request===generation.current)fail(reason);}
  finally{
   if(mounted.current&&request===generation.current){setLoading(false);if(pending)timer.current=setTimeout(()=>void readStatus(request,'status'),2000);}
  }
 }
 useEffect(()=>{
  mounted.current=true;ensured.current=false;groupChosen.current=false;current.current=emptyPages();paging.current.clear();setPages(emptyPages());setExpanded(false);setGroup('ieee');setLoading(true);setMore({ieee:false,nonIeee:false});setError('');
  void readStatus(++generation.current,'open');
  return()=>{mounted.current=false;generation.current++;clearTimer();};
 },[number,fetcher]);
 function refresh(action:'status'|'update'){
  clearTimer();paging.current.clear();setMore({ieee:false,nonIeee:false});setError('');setLoading(true);void readStatus(++generation.current,action);
 }
 function chooseGroup(value:CitationGroup){groupChosen.current=true;setGroup(value);}
 async function loadMore(){
  const snapshot=current.current[visibleGroup];if(!snapshot?.version||snapshot.next_offset===null||paging.current.has(visibleGroup))return;
  const key=visibleGroup,request=generation.current,version=snapshot.version;paging.current.add(key);setMore(previous=>({...previous,[key]:true}));setError('');
  try{
   const page:CitationsPage=await fetcher(base+'?'+new URLSearchParams({group:key,offset:String(snapshot.next_offset),limit:String(CITATION_PAGE_SIZE),version}));
   if(!mounted.current||request!==generation.current||current.current[key]?.version!==version)return;
   validateCitationPage(page,number,key);const next={...current.current,[key]:mergeCitationPage(current.current[key],page,true)};current.current=next;setPages(next);
  }catch(reason){if(mounted.current&&request===generation.current)fail(reason);}
  finally{if(mounted.current&&request===generation.current&&current.current[key]?.version===version){paging.current.delete(key);setMore(previous=>({...previous,[key]:false}));}}
 }
 const groupsVisible=showCitationGroups(pages),visibleGroup=groupsVisible?group:initialCitationGroup(pages)||group;
 const view=pages[visibleGroup],status=view?citationGroupState(view):'',pending=CITATION_GROUPS.some(key=>citationsPending(pages[key]));
 const count=citationCount(view,visibleGroup),counts=CITATION_GROUPS.map(key=>citationCount(pages[key],key)),total=counts.every(value=>value!==undefined)?counts.reduce<number>((n,value)=>n+(value||0),0):undefined;
 const absent=!!view&&(view.source_presence==='absent'||view.empty_reason==='section_absent');
 const globalState=pages.ieee?.state||'missing',noticeState=pending||['failed','blocked'].includes(globalState)?globalState:['failed','blocked','unavailable'].includes(status)?status:globalState;
 const notice=citationNotice({kind:'papers',state:noticeState,absent,count,hasSnapshot:!!view?.version,hasItems:!!view?.items.length,stale:!!view?.stale,error:view?.error||null});
 const checked=citationTime(view),showCount=!!view&&!absent&&(count!==undefined||view.items.length>0);
 const sourceAbsent=pages.ieee?.source_presence==='absent';
 useEffect(()=>onSummary?.({count:total??null,absent:sourceAbsent}),[total,sourceAbsent,onSummary]);
 const contentExpanded=embedded||expanded;
 return <section id={panelId} className={embedded?'paper-citations citation-content-embedded':'panel paper-citations'} aria-label={t('被引论文')}>
  {!embedded&&<div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={expanded?t('收起被引论文'):t('展开被引论文')} aria-controls={contentId} aria-expanded={expanded} onClick={()=>setExpanded(value=>!value)}>{t('被引论文')}</button></h2>{!expanded&&(total!==undefined?<span className="muted">{t('共 {total} 条',{total:fmt(total)})}</span>:pages.ieee?.source_presence==='absent'?<span className="muted">{t('官网未提供')}</span>:null)}</div>}
  <div id={contentId} hidden={!contentExpanded}>{contentExpanded&&<>
   <div className="references-status">{!error&&<span role="status">{loading?t('正在读取被引论文…'):t(notice)}</span>}<div className="citation-update-actions"><button type="button" className="text-button" disabled={loading} onClick={()=>refresh('status')}>{t('刷新状态')}</button><button type="button" disabled={loading||pending||pages.ieee?.state==='disabled'} onClick={()=>refresh('update')}>{t('更新被引论文')}</button></div></div>
   {groupsVisible&&<div className="citation-groups" role="tablist" aria-label={t('被引论文分组')}>{CITATION_GROUPS.map(key=><button type="button" role="tab" key={key} id={panelId+'-tab-'+key} aria-selected={group===key} aria-controls={panelId+'-group-'+key} tabIndex={group===key?0:-1} onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'ieee':event.key==='End'?'nonIeee':key==='ieee'?'nonIeee':'ieee';chooseGroup(next);document.getElementById(panelId+'-tab-'+next)?.focus();}}} onClick={()=>chooseGroup(key)}>{groupName(key)}<span>{citationCount(pages[key],key)!==undefined?fmt(citationCount(pages[key],key)!):pages[key]?.source_presence==='absent'?t('官网未提供'):t('待确认')}</span></button>)}</div>}
   <div id={panelId+'-group-'+visibleGroup} role={groupsVisible?'tabpanel':undefined} aria-labelledby={groupsVisible?panelId+'-tab-'+visibleGroup:undefined} aria-busy={loading}>
    {(showCount||checked)&&<div className="citation-snapshot-meta">{showCount&&<span>{count!==undefined?t('已载入 {loaded} / {total} 条',{loaded:fmt(view!.items.length),total:fmt(count)}):t('已载入 {loaded} 条',{loaded:fmt(view!.items.length)})}</span>}{checked&&<time dateTime={checked.value} title={view?.last_attempt_at&&view.last_attempt_at!==checked.value?t('最近更新尝试：{time}',{time:date(view.last_attempt_at)}):undefined}>{t(checked.checked?'检查：{time}':'尝试：{time}',{time:date(checked.value)})}</time>}</div>}
    {error&&<p className="error" role="alert">{t(error)}</p>}
    {!!view?.items.length&&<ol className="paper-reference-list paper-citation-list">{view.items.map(item=>{
     const link=referenceLink(item),content=<ScientificTitle value={item.text||item.title} fallback={t('未提供被引论文文本')}/>;
     return <li key={view.version+':'+citationItemKey(item)} data-citation-group={item.group} data-citation-item={citationItemKey(item)}><span className="reference-number">{referenceLabel(item)}</span><div className="reference-text">{link?<a href={link.href} target="_blank" rel="noopener noreferrer" className="paper-reference-link">{content}</a>:content}{link&&<small>{link.kind==='paper'?t('站内论文'):t('Google Scholar 搜索')} ↗</small>}</div></li>;
    })}</ol>}
    {view?.version&&view.next_offset!==null&&<button type="button" className="load-more reference-load-more" disabled={more[visibleGroup]||loading} onClick={()=>void loadMore()}>{more[visibleGroup]?t('正在载入被引论文…'):t('加载更多被引论文')}</button>}
   </div>
   {groupsVisible&&<div id={panelId+'-group-'+(visibleGroup==='ieee'?'nonIeee':'ieee')} role="tabpanel" aria-labelledby={panelId+'-tab-'+(visibleGroup==='ieee'?'nonIeee':'ieee')} hidden/>}
  </>}</div>
 </section>;
}
