import {lazy,Suspense,useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {api,ApiError} from './api';
import {arxivCitationRecord} from './arxivCitations';
import {t,useLanguage} from './i18n';
import ScientificTitle from './ScientificTitle';
import AbstractText from './AbstractText';
const CitationDialog=lazy(()=>import('./CitationDialog'));
const DocumentReader=lazy(()=>import('./DocumentReader').then(m=>({default:m.DocumentReader})));
import ReaderLayoutControls,{useReaderLayout} from './ReaderLayoutControls';
import SelectionCopy from './SelectionCopy';
import Icon from './Icon';
import PaperSearchBar from './PaperSearchBar';
import BackToTop from './BackToTop';
import {PaperPdfLink,PaperSourceLink} from './PaperResourceLinks';
import {ArxivResources} from './ArxivResources';
import {acquisitionAction,acquisitionPending,type ArxivState} from './arxivResourceState';
import {arxivCategoryName} from './arxivTaxonomy';
import {arxivCategoryLabel} from './ArxivCategoryFilter';
import {licenseLabel} from './arxivLicense';
import {decodeTexAccents} from './texAccents';
import './arxiv.css';
import {arxivDate} from './arxivDate';
import ArxivSearchPage from './ArxivSearchPage';

type Version={version:number;version_date:string};
type Paper={paper_id:string;arxiv_id:string;title:string;abstract:string;authors_raw:string;metadata?:Record<string,any>;versions?:Version[]};

function requestedVersion(){return Number(new URLSearchParams(location.search).get('v'))||0;}
const searchHref=(values:Record<string,string>)=>'/?'+new URLSearchParams({source:'arxiv',...values});
/** Optional source fields, displayed only when the metadata record carries them. */
const optionalFields:[string,string[]][]=[['提交者',['submitter']],['备注',['comments']],['期刊引用',['journal_ref','journal-ref']],['报告编号',['report_no','report-no']],['MSC 分类',['msc_class','msc-class']],['ACM 分类',['acm_class','acm-class']]];
const AUTHOR_PREVIEW=8;
/** Line breaks after `/` so DOIs wrap at their parts in the narrow sidebar. */
function breakable(value:string){return value.split('/').flatMap((part,i)=>i?[<wbr key={i}/>,'/'+part]:[part]);}
/** Web addresses in free-text comments (for example a project page) become links. */
function linked(value:string){return value.split(/(https?:\/\/[^\s<>"]+[^\s<>".,;:!?)])/).map((part,i)=>i%2?<a key={i} href={part} target="_blank" rel="noopener noreferrer">{part}</a>:part);}

export default function ArxivPage(){
 return location.pathname.match(/^\/arxiv\/papers\/(\d+)$/)?<ArxivDetail/>:<ArxivSearchPage/>;
}
function ArxivAuthors({names,raw}:{names:string[];raw:string}){
 const [expanded,setExpanded]=useState(false);
 if(!names.length)return raw?<p className="authors arxiv-detail-authors" data-copy-content="authors">{decodeTexAccents(raw)}</p>:null;
 const visible=expanded?names:names.slice(0,AUTHOR_PREVIEW);
 return <div className="arxiv-detail-authors-block"><p className="authors arxiv-detail-authors" data-copy-content="authors">{visible.map((name,i)=><span key={i}>{i>0&&', '}<a className="arxiv-author-link" href={searchHref({field:'authors',q:'"'+name+'"'})} title={t('检索该作者的 arXiv 论文')}>{name}</a></span>)}{!expanded&&names.length>AUTHOR_PREVIEW&&<span aria-hidden="true">, …</span>}</p>
  {names.length>AUTHOR_PREVIEW&&<button type="button" className="detail-authors-toggle" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}>{expanded?t('收起作者列表'):t('展开全部作者（共 {n} 位）',{n:names.length})}</button>}
 </div>;
}
function VersionSwitch({versions,value,onChange}:{versions:Version[];value:number;onChange:(version:number)=>void}){
 const latest=Math.max(...versions.map(v=>v.version));
 if(versions.length>6)return <label className="arxiv-version-select">{t('版本')}<select value={value} onChange={e=>onChange(Number(e.target.value))}>{versions.map(v=><option key={v.version} value={v.version}>v{v.version} · {arxivDate(v.version_date)}{v.version===latest?' · '+t('最新'):''}</option>)}</select></label>;
 return <div className="arxiv-version-switch" role="group" aria-label={t('版本')}>{versions.map(v=><button type="button" key={v.version} aria-pressed={v.version===value} onClick={()=>onChange(v.version)}><strong>v{v.version}</strong><span title="UTC+8">{arxivDate(v.version_date)}</span>{v.version===latest&&<small>{t('最新')}</small>}</button>)}</div>;
}
function ArxivDetail(){
 useLanguage();
 const initialQuery=new URLSearchParams(location.search).get('q')||'';
 const paperId=location.pathname.match(/^\/arxiv\/papers\/(\d+)$/)?.[1];
 const [paper,setPaper]=useState<Paper|null>(null),[citationOpen,setCitationOpen]=useState(false);
 const [error,setError]=useState(''),[missing,setMissing]=useState(false),[notice,setNotice]=useState('');
 const [version,setVersion]=useState(requestedVersion);
 const [state,setState]=useState<ArxivState|null>(null),[statusError,setStatusError]=useState(''),[busy,setBusy]=useState(false),[poll,setPoll]=useState(0);
 const pageTop=useRef<HTMLHeadingElement>(null),currentVersion=useRef(version);
 currentVersion.current=version;
 const [abstractExpanded,setAbstractExpanded]=useState(true);
 const {layout,update,reset}=useReaderLayout();
 useEffect(()=>{let active=true;void api('/api/arxiv/papers/'+paperId).then(v=>{
  if(!active)return;const p:Paper=v.paper,observed=(p.versions||[]).map(x=>x.version),latest=Math.max(...observed),wanted=requestedVersion();
  setPaper(p);
  if(wanted&&!observed.includes(wanted))setNotice(t('链接中的 v{v} 不在已记录的版本中，已显示最新版本 v{latest}。',{v:String(wanted),latest:String(latest)}));
  if(!wanted||!observed.includes(wanted)){setVersion(latest);const u=new URL(location.href);u.searchParams.set('v',String(latest));history.replaceState(history.state,'',u);}
 }).catch(e=>{if(!active)return;if(e instanceof ApiError&&e.status===404)setMissing(true);else setError((e as Error).message);});return()=>{active=false;};},[paperId]);
 /** Switching versions clears the previous version's status in the same render, so no stale state is shown. */
 function selectVersion(value:number){setVersion(value);setState(null);setStatusError('');setBusy(false);}
 useEffect(()=>{const pop=()=>{const v=requestedVersion();if(v)selectVersion(v);};window.addEventListener('popstate',pop);return()=>window.removeEventListener('popstate',pop);},[]);
 useEffect(()=>{
  if(!paperId||!version||!paper)return;let active=true;let timer:ReturnType<typeof setTimeout>|undefined;
  const base='/api/arxiv/papers/'+paperId+'/versions/'+version;
  async function read(){try{const value=await api(base+'/resources');if(!active)return;setState(value);setStatusError('');if(acquisitionPending(value))timer=setTimeout(read,3000);}catch(e){if(active)setStatusError((e as Error).message);}}
  void read();return()=>{active=false;if(timer)clearTimeout(timer);};
 },[paperId,version,poll,paper]);
 async function acquire(){
  const requested=version,action=acquisitionAction(state);if(!paperId||!requested||!action)return;
  setBusy(true);setStatusError('');
  try{await api('/api/arxiv/papers/'+paperId+'/versions/'+requested+'/ensure','POST',{retry:action==='retry'});}
  catch(e){if(currentVersion.current===requested)setStatusError((e as Error).message);}
  finally{if(currentVersion.current===requested){setBusy(false);setPoll(v=>v+1);}}
 }
 function choose(value:number){if(value===version)return;selectVersion(value);setNotice('');const u=new URL(location.href);u.searchParams.set('v',String(value));history.pushState(history.state,'',u);}
 const base=paperId&&version?'/api/arxiv/papers/'+paperId+'/versions/'+version:'';
 const documentResource=useMemo(()=>({href:base+'/document'}),[base]);
 const metadata=paper?.metadata||{};
 const authors:string[]=(metadata.authors_structured||[]).map((a:any)=>Array.isArray(a)?[a[1],a[0],a[2]].filter(Boolean).join(' '):[a.forenames,a.keyname].filter(Boolean).join(' ')||a.name||'').filter(Boolean);
 const versions=paper?.versions||[],latest=versions.length?Math.max(...versions.map(v=>v.version)):0,selected=versions.find(v=>v.version===version);
 const informationId='arxiv-information-'+paperId;
 const license=licenseLabel(metadata.license),licenseText=license?.values?t(license.label,license.values):license?.label;
 const citationFetcher=useCallback(async(path:string)=>{
  if(!paper||path!=='/api/papers/'+paper.paper_id)throw Error('invalid_arxiv_paper_request');
  return {paper:{number:String(paper.paper_id),record:arxivCitationRecord(paper,version)}};
 },[paper,version]);
 function back(){const values=new URLSearchParams(location.search);values.delete('v');values.set('source','arxiv');values.set('restore','1');location.href='/?'+values;}
 if(missing)return <main id="main" className="workspace detail-page arxiv-page"><div className="detail-toolbar"><button type="button" className="back" onClick={back}><Icon name="back"/>{t('返回检索')}</button></div><div className="empty"><Icon name="search"/><h1>{t('未找到该 arXiv 论文')}</h1><p>{t('该记录不在当前 arXiv 元数据目录中。')}</p></div></main>;
 return <><main id="main" className="workspace detail-page arxiv-page" data-copy-scope style={{'--reader-page-width':layout.pageWidth+'px','--reader-toc-width':layout.tocWidth+'px','--reader-font-scale':layout.fontScale/100,'--publication-column-width':(layout.infoOpen?layout.infoWidth:44)+'px'} as React.CSSProperties}>
  <div className="detail-toolbar"><button type="button" className="back" onClick={back}><Icon name="back"/>{t('返回检索')}</button><PaperSearchBar number={paper?.arxiv_id||''} initialQuery={initialQuery} placeholder={t('搜索 arXiv：标题、作者、摘要或编号')} onSearch={q=>{location.href=searchHref({q});}}/><ReaderLayoutControls layout={layout} onChange={update} onReset={reset}/></div>
  {error&&<div className="error-box" role="alert">{t(error)}</div>}
  {!paper?!error&&<p className="hint" role="status">{t('正在读取论文…')}</p>:<>
  <header className="detail-header">
   <p className="detail-kicker arxiv-kicker" data-copy-ignore>{(metadata.categories||[]).map((code:string)=><a key={code} href={searchHref({category:code})} title={arxivCategoryName(code)} aria-label={t('浏览分类：{name}',{name:arxivCategoryLabel(code)})}>{code}</a>)}<span className="arxiv-identifier">arXiv:{paper.arxiv_id}v{version}</span></p>
   <h1 ref={pageTop} tabIndex={-1} data-copy-content="title"><ScientificTitle value={paper.title}/></h1>
   <ArxivAuthors key={paper.paper_id} names={authors} raw={paper.authors_raw}/>
   {versions.length>0&&<div className="arxiv-version-row"><VersionSwitch versions={versions} value={version} onChange={choose}/>{version!==latest&&<p className="hint arxiv-version-note">{t('标题、作者与摘要为当前元数据，不一定与 v{v} 相同。',{v:String(version)})}</p>}</div>}
   {notice&&<p className="hint" role="status">{notice}</p>}
   <div className="detail-record-toolbar"><div className="detail-record-actions">
    <button type="button" className="detail-citation-trigger" aria-label={t('获取引用格式：')+paper.title} disabled={!selected} onClick={()=>setCitationOpen(true)}><Icon name="quote"/>{t('引用')}</button>
    {state?.resources?.pdf?.state==='ready'&&<PaperPdfLink href={base+'/pdf/reader'}/>}
    <PaperSourceLink href={'https://arxiv.org/abs/'+paper.arxiv_id+'v'+version} label={t('arXiv 原文')}/>
   </div></div>
   <ArxivResources key={version} base={base} state={state} error={statusError} busy={busy} onAcquire={()=>void acquire()} onReload={()=>setPoll(v=>v+1)}/>
  </header>
  <div className="detail-grid"><section className="detail-main" aria-label={t('论文内容')}>
   <section className="panel abstract-panel"><div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={abstractExpanded?t('收起摘要'):t('展开摘要')} aria-controls="arxiv-abstract" aria-expanded={abstractExpanded} onClick={()=>setAbstractExpanded(v=>!v)}>{t('摘要')}</button></h2></div><div id="arxiv-abstract" hidden={!abstractExpanded}>{paper.abstract?<p className="abstract" data-copy-content="abstract" data-copy-source-html={paper.abstract} data-copy-source-mode="literal" data-copy-preserve-lines><AbstractText value={paper.abstract}/></p>:<p className="muted">{t('元数据未提供摘要。')}</p>}</div></section>
   {!!state?.document&&<Suspense fallback={<p className="hint">{t('正在加载正文…')}</p>}><DocumentReader key={version} resource={documentResource} fetcher={api} automatic={false}/></Suspense>}
  </section><aside className={'publication-sidebar'+(!layout.infoOpen?' is-collapsed':'')}>
   {!layout.infoOpen&&<button type="button" className="publication-sidebar-rail" aria-label={t('展开出版信息')} aria-expanded={false} aria-controls={informationId} onClick={()=>update({infoOpen:true})}><Icon name="right"/><span className="publication-sidebar-rail-label">{t('出版信息')}</span></button>}
   <div id={informationId} className="panel bibliographic" hidden={!layout.infoOpen}><div className="publication-sidebar-heading"><h2>{t('出版信息')}</h2><button type="button" className="publication-sidebar-toggle" aria-label={t('收起出版信息')} aria-expanded={true} aria-controls={informationId} onClick={()=>update({infoOpen:false})}><Icon name="right"/></button></div><dl>
    <div className="bibliographic-row"><dt>{t('论文编号')}</dt><dd>{paper.arxiv_id}</dd></div>
    <div className="bibliographic-row"><dt>{t('当前版本')}</dt><dd title="UTC+8">{selected?'v'+selected.version+' · '+arxivDate(selected.version_date):'—'}{versions.length>1&&<small className="arxiv-version-count">{t('共 {n} 个版本',{n:String(versions.length)})}</small>}</dd></div>
    <div className="bibliographic-row"><dt>{t('投稿时间')}</dt><dd title="UTC+8">{arxivDate(metadata.submitted_at)}</dd></div>
    <div className="bibliographic-row"><dt>DOI</dt><dd>{metadata.doi?<a href={'https://doi.org/'+metadata.doi} target="_blank" rel="noopener noreferrer">{breakable(metadata.doi)}</a>:'—'}</dd></div>
    <div className="bibliographic-row"><dt>{t('许可证')}</dt><dd>{license?(license.href?<a href={license.href} target="_blank" rel="noopener noreferrer">{licenseText}</a>:licenseText):'—'}</dd></div>
    {optionalFields.map(([label,keys])=>{const value=keys.map(key=>metadata[key]).find(v=>typeof v==='string'&&v.trim());return value?<div className="bibliographic-row" key={label}><dt>{t(label)}</dt><dd>{linked(value)}</dd></div>:null;})}
   </dl></div>
  </aside></div><BackToTop target={pageTop}/>
  </>}
 </main><SelectionCopy/>{citationOpen&&paper&&<Suspense fallback={<p className="hint" role="status">{t('正在生成引用…')}</p>}><CitationDialog numbers={[String(paper.paper_id)]} fetcher={citationFetcher} filenamePrefix="arxiv" onClose={()=>setCitationOpen(false)}/></Suspense>}</>;
}
