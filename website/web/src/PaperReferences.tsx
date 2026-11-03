import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import ScientificTitle from './ScientificTitle';
import {locale,t,useLanguage} from './i18n';
import {REFERENCE_PAGE_SIZE,mergeReferenceItems,mergeReferencePage,referenceLabel,referenceLink,referencesPending,shouldEnsureReferences,referenceCountKnown,type PaperReference,type ReferencesPage,type ReferenceJump} from './paperReferenceData';
type Fetcher=(path:string,method?:string,data?:unknown)=>Promise<any>;
const states:Record<string,string>={missing:'参考文献尚未获取',queued:'参考文献等待获取',fetching:'正在获取参考文献',complete:'参考文献已收录',no_data:'已确认没有参考文献',unavailable:'来源未提供参考文献',partial:'参考文献尚未完整',blocked:'参考文献访问受限',failed:'参考文献获取未完成',disabled:'参考文献功能尚未启用'};
const fmt=(value:number)=>value.toLocaleString(locale());

export default function PaperReferences({number,fetcher,jump}:{number:string;fetcher:Fetcher;jump?:ReferenceJump|null}){
 useLanguage();
 const [expanded,setExpanded]=useState(false),expandedJump=useRef<number|null>(null);
 const [view,setView]=useState<ReferencesPage|null>(null),[loading,setLoading]=useState(true),[more,setMore]=useState(false),[locating,setLocating]=useState(false),[error,setError]=useState(''),[selected,setSelected]=useState<number|null>(null),[notice,setNotice]=useState('');
 const panel=useRef<HTMLElement>(null),current=useRef<ReferencesPage|null>(null),generation=useRef(0),mounted=useRef(false),ensured=useRef(false),timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),navigation=useRef(0);
 const base='/api/papers/'+encodeURIComponent(number)+'/references',panelId='paper-references-'+number,contentId=panelId+'-content';
 function valid(page:ReferencesPage){if(page.number!==number||!Array.isArray(page.items)||!Number.isSafeInteger(page.total)||page.total<0||(!page.version&&page.items.length))throw Error('reference_snapshot_mismatch');}
 function apply(page:ReferencesPage,append=false){
  valid(page);const previous=current.current,next=mergeReferencePage(previous,page,append);
  current.current=next;setView(next);
  if(previous?.version!==next.version){navigation.current++;setSelected(null);setMore(false);setLocating(false);}
 }
 function clearTimer(){if(timer.current!==undefined)clearTimeout(timer.current);timer.current=undefined;}
 function fail(reason:unknown){setError(reason instanceof Error&&reason.message==='reference_snapshot_mismatch'?t('参考文献快照不一致，请刷新状态后重试。'):reason instanceof Error?reason.message:t('参考文献暂不可读取。'));}
 async function readStatus(request:number,allowEnsure:boolean){
  try{
   let page:ReferencesPage=await fetcher(base+'?offset=0&limit='+REFERENCE_PAGE_SIZE);
   if(!mounted.current||request!==generation.current)return;
   apply(page);
   if(allowEnsure&&shouldEnsureReferences(page)&&!ensured.current){
    ensured.current=true;page=await fetcher(base+'/ensure','POST',{});
    if(!mounted.current||request!==generation.current)return;apply(page);
   }
   if(referencesPending(page.state))timer.current=setTimeout(()=>void readStatus(request,false),2000);
  }catch(reason){if(mounted.current&&request===generation.current)fail(reason);}
  finally{if(mounted.current&&request===generation.current)setLoading(false);}
 }
 useEffect(()=>{
  mounted.current=true;ensured.current=false;current.current=null;expandedJump.current=null;setExpanded(false);setView(null);setError('');setLoading(true);setMore(false);setSelected(null);setNotice('');
  const request=++generation.current;void readStatus(request,true);
  return()=>{mounted.current=false;generation.current++;navigation.current++;clearTimer();};
 },[number,fetcher]);
 function refresh(){clearTimer();navigation.current++;setMore(false);setLocating(false);setError('');setLoading(true);void readStatus(++generation.current,false);}
 async function loadMore(){
  const snapshot=current.current;if(!snapshot?.version||snapshot.next_offset===null||more)return;
  const request=generation.current,version=snapshot.version;setMore(true);setError('');
  try{
   const page=await fetcher(base+'?'+new URLSearchParams({offset:String(snapshot.next_offset),limit:String(REFERENCE_PAGE_SIZE),version}));
   if(mounted.current&&request===generation.current&&current.current?.version===version)apply(page,true);
  }catch(reason){if(mounted.current&&request===generation.current)fail(reason);}
  finally{if(mounted.current&&request===generation.current)setMore(false);}
 }
 useEffect(()=>{
  if(!jump)return;
  if(expandedJump.current!==jump.token){expandedJump.current=jump.token;setExpanded(true);}
  const snapshot=current.current,origin=jump.source;
  origin.classList.add('document-citation-origin');setNotice('');setError('');
  if(!snapshot?.version){
   setNotice(!snapshot||referencesPending(snapshot.state)||snapshot.state==='missing'?t('参考文献仍在获取，完成后将定位该条目。'):t('当前没有可定位的参考文献。'));panel.current?.scrollIntoView({block:'start'});
   return()=>origin.classList.remove('document-citation-origin');
  }
  if(referencesPending(snapshot.state)&&jump.order>snapshot.total){setNotice(t('参考文献仍在获取，完成后将定位该条目。'));return()=>origin.classList.remove('document-citation-origin');}
  const version=snapshot.version,request=generation.current,ticket=++navigation.current;
  const existing=snapshot.items.find(item=>item.order===jump.order);
  if(existing){setSelected(jump.order);setLocating(false);}
  else{
   setLocating(true);
   void fetcher(base+'/'+jump.order+'?'+new URLSearchParams({version})).then(value=>{
    if(!mounted.current||request!==generation.current||ticket!==navigation.current||current.current?.version!==version)return;
    if(value.number!==number||value.version!==version||value.item?.order!==jump.order)throw Error('reference_snapshot_mismatch');
    const next={...current.current,items:mergeReferenceItems(current.current.items,[value.item as PaperReference])};current.current=next;setView(next);setSelected(jump.order);
   }).catch(reason=>{if(mounted.current&&request===generation.current&&ticket===navigation.current)fail(reason);}).finally(()=>{if(mounted.current&&request===generation.current&&ticket===navigation.current)setLocating(false);});
  }
  return()=>{navigation.current++;origin.classList.remove('document-citation-origin');};
 },[jump?.token,view?.version,view?.state]);
 useLayoutEffect(()=>{
  if(!expanded||selected===null||selected!==jump?.order)return;
  const target=panel.current?.querySelector<HTMLElement>('[data-reference-order="'+selected+'"]');
  if(target){target.scrollIntoView({block:'center'});target.focus({preventScroll:true});}
 },[expanded,selected,view?.version,jump?.token]);
 function returnToCitation(){if(jump?.source.isConnected){navigation.current++;const source=jump.source;source.dispatchEvent(new Event('cirdc-document-reveal',{bubbles:true}));requestAnimationFrame(()=>{if(source.isConnected){source.scrollIntoView({block:'center'});source.focus({preventScroll:true});}});}}
 const pending=view&&referencesPending(view.state),empty=view&&!view.items.length&&!pending;
 const stateLabel=view?.state==='no_data'&&(view.source_presence==='absent'||view.empty_reason==='section_absent')?states.unavailable:view?.state==='unavailable'&&view.source_presence!=='absent'&&view.empty_reason!=='section_absent'?'参考文献来源状态尚未确认':view?states[view.state]||'参考文献状态暂不可用':'参考文献暂不可读取。';
 return <section id={panelId} ref={panel} className="panel paper-references" aria-label={t('参考文献')}>
  <div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={expanded?t('收起参考文献'):t('展开参考文献')} aria-controls={contentId} aria-expanded={expanded} onClick={()=>setExpanded(value=>!value)}>{t('参考文献')}</button></h2>{view&&referenceCountKnown(view)?<span className="muted">{t('已载入 {loaded} / {total} 条',{loaded:fmt(view.items.length),total:fmt(view.total)})}</span>:view?.source_presence==='absent'?<span className="muted">{t('官网未提供')}</span>:null}</div>
  <div id={contentId} hidden={!expanded}>{expanded&&<>
  <div className="references-status"><span role="status">{loading?t('正在读取参考文献…'):t(stateLabel)}</span><button type="button" className="text-button" disabled={loading||more||locating} onClick={refresh}>{t('刷新状态')}</button></div>
  {view&&['partial','blocked','failed'].includes(view.state)&&<p className="hint">{view.items.length?t('保留已收录的参考文献；后续重试由后台安排。'):t('刷新页面不会连续重试获取参考文献。')}</p>}
  {view?.state==='partial'&&view.expected_total!==null&&<p className="hint">{t('来源记录 {expected} 条，当前已保存 {total} 条。',{expected:fmt(view.expected_total),total:fmt(view.total)})}</p>}
  {error&&<p className="error" role="alert">{t(error)}</p>}{notice&&<p className="hint" role="status">{t(notice)}</p>}
  {locating&&<p className="hint" role="status">{t('正在定位参考文献…')}</p>}
  {jump?.source.isConnected&&<button type="button" className="reference-return" onClick={returnToCitation}>{t('返回引用位置')}</button>}
  {!!view?.items.length&&<ol className="paper-reference-list">{view.items.map(item=>{
   const link=referenceLink(item),content=<ScientificTitle value={item.text||item.title} fallback={t('未提供参考文献文本')}/>;
   return <li key={view.version+':'+item.order} data-reference-order={item.order} className={selected===item.order?'is-highlighted':undefined} tabIndex={-1} aria-current={selected===item.order?'true':undefined}><span className="reference-number">{referenceLabel(item)}</span><div className="reference-text">{link?<a href={link.href} target="_blank" rel="noopener noreferrer" className="paper-reference-link">{content}</a>:content}{link&&<small>{link.kind==='paper'?t('站内论文'):t('Google Scholar 搜索')} ↗</small>}</div></li>;
  })}</ol>}
  {empty&&!error&&<p className="muted references-empty">{view.source_presence==='absent'||view.empty_reason==='section_absent'?t('官网未提供这篇论文的参考文献栏目。'):view.empty_reason==='zero_count'||view.state==='no_data'||(view.state==='complete'&&view.total===0)?t('已确认该论文没有参考文献。'):view.state==='unavailable'?t('尚未确认官网是否提供参考文献。'):t('当前没有可展示的参考文献。')}</p>}
  {view?.version&&view.next_offset!==null&&<button type="button" className="load-more reference-load-more" disabled={more||loading} onClick={()=>void loadMore()}>{more?t('正在载入参考文献…'):t('加载更多参考文献')}</button>}
  </>}</div>
 </section>;
}
