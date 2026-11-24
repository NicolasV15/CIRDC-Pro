import {lazy,Suspense,useEffect,useReducer,useRef,useState} from 'react';
import {api} from './api';
import {fmt} from './format';
import {locale,t,useLanguage} from './i18n';
import Icon from './Icon';
import PaperSelectionToolbar from './PaperSelectionToolbar';
import ScientificTitle from './ScientificTitle';
import {resultSelection} from './resultSelection';
import {forgetFavorites} from './favorites';
const FavoriteArchiveDialog=lazy(()=>import('./FavoriteArchiveDialog'));

export type FavoriteRow={number:string;id:number;source:'ieee'|'arxiv';paper_id:string;version:number;identifier:string;title:string;year:number|null;created:number;status:string;latest_version?:number};
type Source=''|'ieee'|'arxiv';
const ARCHIVE_LIMIT=100;
const statusLabels:Record<string,string>={paper_missing:'论文暂不可读取',version_missing:'该版本暂不可读取',unavailable:'目录暂时不可用'};
function sourceFromURL():Source{const value=new URLSearchParams(location.search).get('source');return value==='ieee'||value==='arxiv'?value:'';}
function href(row:FavoriteRow){return row.source==='ieee'?'/papers/'+row.paper_id:'/arxiv/papers/'+row.paper_id+'?'+new URLSearchParams({v:String(row.version)});}

/** Saved papers, newest first. Selection belongs to the loaded rows of the current filter only. */
export default function FavoritesPage(){
 useLanguage();
 const [source,setSource]=useState<Source>(sourceFromURL),[results,dispatch]=useReducer(resultSelection<FavoriteRow>,{rows:[],selected:[]});
 const [cursor,setCursor]=useState<number|null>(null),[counts,setCounts]=useState<{ieee:number;arxiv:number}|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [confirming,setConfirming]=useState(false),[archive,setArchive]=useState<FavoriteRow[]|null>(null),[notice,setNotice]=useState('');
 const generation=useRef(0),heading=useRef<HTMLHeadingElement>(null);
 const {rows,selected}=results,chosen=rows.filter(row=>selected.includes(row.number));
 async function load(filter:Source,next?:number){
  const id=++generation.current;setBusy(true);setError('');if(next===undefined){dispatch({type:'reset'});setCursor(null);}
  try{
   const params=new URLSearchParams({limit:'25',...(filter?{source:filter}:{}),...(next!==undefined?{cursor:String(next)}:{})});
   const value=await api('/api/me/favorites?'+params);if(id!==generation.current)return;
   dispatch({type:next===undefined?'replace':'append',rows:value.items.map((item:any)=>({...item,number:String(item.id)}))});
   setCursor(value.next_cursor);setCounts(value.counts);
  }catch(e){if(id===generation.current)setError((e as Error).message);}finally{if(id===generation.current)setBusy(false);}
 }
 useEffect(()=>{void load(source);const pop=()=>{const next=sourceFromURL();setSource(next);void load(next);};window.addEventListener('popstate',pop);return()=>{generation.current++;window.removeEventListener('popstate',pop);};},[]);
 function filter(next:Source){if(next===source)return;setSource(next);setConfirming(false);const u=new URL(location.href);if(next)u.searchParams.set('source',next);else u.searchParams.delete('source');history.pushState({},'',u);void load(next);}
 async function remove(){
  setBusy(true);setError('');
  try{const {removed}=await api('/api/me/favorites/remove','POST',{ids:chosen.map(row=>row.id)});forgetFavorites();setNotice(t('已取消收藏 {n} 篇。',{n:removed}));setConfirming(false);await load(source);heading.current?.focus();}
  catch(e){setError((e as Error).message);setBusy(false);}
 }
 const total=counts?counts.ieee+counts.arxiv:null,tooMany=chosen.length>ARCHIVE_LIMIT;
 const tabs:[Source,string,number|undefined][]=[['',t('全部'),total??undefined],['ieee','IEEE',counts?.ieee],['arxiv','arXiv',counts?.arxiv]];
 return <><main id="main" className="workspace personal-page favorites-page">
  <header className="personal-heading"><span className="eyebrow">{t('FAVORITES')}</span><h1 ref={heading} tabIndex={-1}>{t('我的收藏')}</h1></header>
  <nav className="favorite-filters" aria-label={t('按来源筛选收藏')}>{tabs.map(([value,label,count])=><button type="button" key={value||'all'} aria-pressed={source===value} onClick={()=>filter(value)}>{label}{count!==undefined&&<span className="count-badge">{fmt(count)}</span>}</button>)}</nav>
  {notice&&<p className="hint favorite-notice" role="status">{notice}</p>}
  <PaperSelectionToolbar total={rows.length} count={selected.length} disabled={busy} onAll={checked=>{setConfirming(false);dispatch({type:'all',checked});}} actions={<>
   {confirming?<><button type="button" className="danger" disabled={busy} onClick={()=>void remove()}><Icon name="trash"/>{t('确认取消收藏 {n} 篇',{n:chosen.length})}</button><button type="button" onClick={()=>setConfirming(false)}>{t('保留')}</button></>
    :<button type="button" disabled={busy||!chosen.length} onClick={()=>setConfirming(true)}><Icon name="trash"/>{t('取消收藏')}</button>}
   <button type="button" disabled={busy||!chosen.length||tooMany} aria-describedby={tooMany?'favorite-limit':undefined} onClick={()=>setArchive(chosen)}><Icon name="download"/>{t('下载 PDF')}</button>
   {selected.length>0&&<button type="button" className="text-button" onClick={()=>{setConfirming(false);dispatch({type:'all',checked:false});}}>{t('清空选择')}</button>}
  </>}/>
  {tooMany&&<p className="error favorite-limit" id="favorite-limit" role="alert">{t('单次最多打包 {limit} 篇（已选 {n} 篇）。',{limit:ARCHIVE_LIMIT,n:chosen.length})}</p>}
  {error&&<div className="error-box" role="alert">{t(error)}</div>}
  {busy&&!rows.length?<div className="paper-list is-loading" role="status"><span className="sr-only">{t('正在读取收藏…')}</span>{[0,1,2].map(i=><div className="paper-skeleton" key={i} aria-hidden="true"><i/><i/><i/></div>)}</div>
   :!rows.length&&!error?<div className="empty"><Icon name="star"/><h2>{source?t('这个来源还没有收藏'):t('还没有收藏的论文')}</h2><p>{t('在检索结果或论文详情中点击「收藏」即可保存。')}</p><a className="button" href={source?'/?sources='+source:'/'}>{t('去检索论文')}</a></div>
   :<div className="paper-list favorite-list">{rows.map(row=><article className={'paper-row favorite-row'+(selected.includes(row.number)?' paper-selected':'')} key={row.number}>
    <label className="paper-selection-control"><input type="checkbox" checked={selected.includes(row.number)} disabled={busy} aria-label={t('选择论文：')+(row.title||row.identifier)} onChange={e=>{setConfirming(false);dispatch({type:'select',numbers:[row.number],checked:e.target.checked});}}/></label>
    <div className="paper-body">
     <a className="paper-title" href={href(row)}><ScientificTitle value={row.title} fallback={row.identifier}/></a>
     <div className="favorite-meta"><span className={'favorite-source '+row.source}>{row.source==='ieee'?'IEEE':'arXiv'}</span><code className="paper-number">{row.source==='arxiv'?row.identifier+'v'+row.version:row.identifier}</code>{row.year&&<span className="paper-year">{row.year}</span>}
      {row.status!=='ok'&&<span className="badge failed">{t(statusLabels[row.status]||row.status)}</span>}
      {row.source==='arxiv'&&row.latest_version&&row.latest_version>row.version&&<a className="favorite-newer" href={'/arxiv/papers/'+row.paper_id+'?'+new URLSearchParams({v:String(row.latest_version)})}>{t('有更新版本 v{v}',{v:String(row.latest_version)})}</a>}
      <span className="favorite-saved">{t('收藏于 {date}',{date:new Date(row.created*1000).toLocaleDateString(locale())})}</span></div>
    </div>
   </article>)}</div>}
  {cursor!==null&&<button className="load-more" disabled={busy} onClick={()=>void load(source,cursor)}>{busy?t('加载中…'):t('加载更多')}</button>}
 </main>{archive&&<Suspense fallback={null}><FavoriteArchiveDialog rows={archive} onClose={()=>setArchive(null)}/></Suspense>}</>;
}
