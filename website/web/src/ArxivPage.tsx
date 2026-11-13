import {lazy,Suspense,useCallback,useEffect,useRef,useState} from 'react';
import {api} from './api';
import {arxivCitationRecord} from './arxivCitations';
import {locale,t,useLanguage} from './i18n';
import ScientificTitle from './ScientificTitle';
import AbstractText from './AbstractText';
const CitationDialog=lazy(()=>import('./CitationDialog'));
const DocumentReader=lazy(()=>import('./DocumentReader').then(m=>({default:m.DocumentReader})));
import ReaderLayoutControls,{useReaderLayout} from './ReaderLayoutControls';
import SelectionCopy from './SelectionCopy';
import Icon from './Icon';
import PaperSearchBar from './PaperSearchBar';
import BackToTop from './BackToTop';
import {PaperPdfLink,PaperSourceLink,PaperSourceDownload} from './PaperResourceLinks';
import './arxiv.css';
import ArxivSearchPage from './ArxivSearchPage';

type Paper={paper_id:string;arxiv_id:string;title:string;abstract:string;authors_raw:string;metadata?:Record<string,any>;versions?:{version:number;version_date:string}[]};
type State={state:string;reading_ready?:boolean;acquisition_complete?:boolean;resources?:Record<string,{state:string;download_url?:string;error?:string}>;document?:any;reading_state?:string;conversion_errors?:Record<string,string>};

function dateLabel(value?:string){
 if(!value)return '—';const parsed=new Date(value);
 return Number.isNaN(parsed.getTime())?value:new Intl.DateTimeFormat(locale(),{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'UTC'}).format(parsed);
}

export default function ArxivPage(){
 return location.pathname.match(/^\/arxiv\/papers\/(\d+)$/)?<ArxivDetail/>:<ArxivSearchPage/>;
}
function ArxivDetail(){
 useLanguage();
 const params=new URLSearchParams(location.search),initialQuery=params.get('q')||'';
 const paperId=location.pathname.match(/^\/arxiv\/papers\/(\d+)$/)?.[1];
 const [paper,setPaper]=useState<Paper|null>(null),[citationOpen,setCitationOpen]=useState(false);
 const [error,setError]=useState(''),[version,setVersion]=useState<number>(Number(params.get('v'))||0);
 const [state,setState]=useState<State|null>(null),[busy,setBusy]=useState(false),[poll,setPoll]=useState(0);
 const pageTop=useRef<HTMLHeadingElement>(null);
 const [abstractExpanded,setAbstractExpanded]=useState(true);
 const {layout,update,reset}=useReaderLayout();
 useEffect(()=>{let active=true;void api('/api/arxiv/papers/'+paperId).then(v=>{if(!active)return;setPaper(v.paper);if(!version)setVersion(Math.max(...v.paper.versions.map((x:any)=>x.version)));}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[paperId]);
 useEffect(()=>{
  if(!paperId||!version)return;let active=true;let timer:ReturnType<typeof setTimeout>|undefined;setState(null);
  const base='/api/arxiv/papers/'+paperId+'/versions/'+version;
  async function read(){try{const value=await api(base+'/resources');if(!active)return;setState(value);if(value.state==='queued')timer=setTimeout(read,3000);}catch(e){if(active)setError((e as Error).message);}}
  void read();return()=>{active=false;if(timer)clearTimeout(timer);};
 },[paperId,version,poll]);
 async function acquire(){if(!paperId||!version)return;setBusy(true);setError('');try{await api('/api/arxiv/papers/'+paperId+'/versions/'+version+'/ensure','POST',{retry:state?.state==='partial'});setPoll(v=>v+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 function choose(value:number){setVersion(value);const u=new URL(location.href);u.searchParams.set('v',String(value));history.replaceState({},'',u);}
 useEffect(()=>{if(paperId&&version&&!new URLSearchParams(location.search).has('v'))choose(version);},[version,paperId]);
 const base=paperId&&version?'/api/arxiv/papers/'+paperId+'/versions/'+version:'';
 const metadata=paper?.metadata||{};
 const authors:string[]=(metadata.authors_structured||[]).map((a:any)=>Array.isArray(a)?[a[1],a[0],a[2]].filter(Boolean).join(' '):[a.forenames,a.keyname].filter(Boolean).join(' ')||a.name||'').filter(Boolean);
 if(!authors.length&&paper?.authors_raw)authors.push(paper.authors_raw);
 const cached=(kind:string)=>state?.resources?.[kind]?.state==='ready'?base+'/files/'+kind:undefined;
 const informationId='arxiv-information-'+paperId;
 const citationFetcher=useCallback(async(path:string)=>{
  if(!paper||path!=='/api/papers/'+paper.paper_id)throw Error('invalid_arxiv_paper_request');
  return {paper:{number:String(paper.paper_id),record:arxivCitationRecord(paper,version)}};
 },[paper,version]);

 return <><main id="main" className="workspace detail-page arxiv-page" data-copy-scope style={{'--reader-page-width':layout.pageWidth+'px','--reader-toc-width':layout.tocWidth+'px','--reader-font-scale':layout.fontScale/100,'--publication-column-width':(layout.infoOpen?layout.infoWidth:44)+'px'} as React.CSSProperties}>
  {error&&<p role="alert" className="error">{error}</p>}
  {!paper?<p role="status">{t('正在读取论文…')}</p>:<>
  <div className="detail-toolbar"><button type="button" className="back" onClick={()=>{const back=new URLSearchParams(params);back.delete('v');back.set('source','arxiv');back.set('restore','1');location.href='/?'+back;}}><Icon name="back"/>{t('返回检索')}</button><PaperSearchBar number={paper.arxiv_id} initialQuery={initialQuery} onSearch={q=>{location.href='/?'+new URLSearchParams({source:'arxiv',q});}}/><ReaderLayoutControls layout={layout} onChange={update} onReset={reset}/></div>
  <header className="detail-header">
   <p className="detail-kicker" data-copy-ignore>{[...(metadata.categories||[]),paper.arxiv_id+'v'+version].join(' · ')}</p>
   <h1 ref={pageTop} tabIndex={-1} data-copy-content="title"><ScientificTitle value={paper.title}/></h1>
   <p className="authors arxiv-detail-authors" data-copy-content="authors">{authors.join(', ')}</p>
   <div className="detail-record-toolbar"><div className="detail-record-actions">
    <button type="button" className="detail-citation-trigger" aria-label={t('获取引用格式：')+paper.title} disabled={!paper.versions?.some(v=>v.version===version)} onClick={()=>setCitationOpen(true)}><Icon name="quote"/>{t('引用')}</button>
    {cached('pdf')?<PaperPdfLink href={base+'/pdf/reader'}/>:<button type="button" className="detail-pdf-trigger" disabled={busy||state?.state==='queued'||state?.resources?.pdf?.state==='unavailable'} onClick={()=>void acquire()}><Icon name="download"/>{busy?t('正在提交…'):state?.state==='queued'?t('正在获取资料…'):state?.resources?.pdf?.state==='unavailable'?t('阅读 PDF'):state?.state==='partial'?t('重试未完成项'):t('获取论文资料')}</button>}
    <PaperSourceLink href={'https://arxiv.org/abs/'+paper.arxiv_id+'v'+version} label={t('arXiv 原文')}/>
    <PaperSourceDownload href={cached('html')} label={t('下载 HTML 源码')} onAcquire={()=>void acquire()} pending={busy||state?.state==='queued'} unavailable={state?.resources?.html?.state==='unavailable'}/>
    <PaperSourceDownload href={cached('source')} label={t('下载 TeX 源码')} onAcquire={()=>void acquire()} pending={busy||state?.state==='queued'} unavailable={state?.resources?.source?.state==='unavailable'}/>
   </div></div>
  </header>
  <div className="detail-grid"><section className="detail-main" aria-label={t('论文内容')}>
   <section className="panel abstract-panel"><div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={abstractExpanded?t('收起摘要'):t('展开摘要')} aria-controls="arxiv-abstract" aria-expanded={abstractExpanded} onClick={()=>setAbstractExpanded(v=>!v)}>{t('摘要')}</button></h2></div><div id="arxiv-abstract" hidden={!abstractExpanded}><p className="abstract" data-copy-content="abstract" data-copy-source-html={paper.abstract} data-copy-source-mode="literal" data-copy-preserve-lines><AbstractText value={paper.abstract}/></p></div></section>
   {state?.document&&<Suspense fallback={<p>{t('正在加载正文…')}</p>}><DocumentReader resource={{href:base+'/document'}} fetcher={api} automatic={false}/></Suspense>}
   {state?.reading_state==='failed'&&<p className="hint">{t('正文生成失败，仍可阅读已获取的 PDF。')}</p>}
  </section><aside className={'publication-sidebar'+(!layout.infoOpen?' is-collapsed':'')}>
   {!layout.infoOpen&&<button type="button" className="publication-sidebar-rail" aria-label={t('展开出版信息')} aria-expanded={false} aria-controls={informationId} onClick={()=>update({infoOpen:true})}><Icon name="right"/><span className="publication-sidebar-rail-label">{t('出版信息')}</span></button>}
   <div id={informationId} className="panel bibliographic" hidden={!layout.infoOpen}><div className="publication-sidebar-heading"><h2>{t('出版信息')}</h2><button type="button" className="publication-sidebar-toggle" aria-label={t('收起出版信息')} aria-expanded={true} aria-controls={informationId} onClick={()=>update({infoOpen:false})}><Icon name="right"/></button></div><dl><div className="bibliographic-row"><dt>{t('论文编号')}</dt><dd>{paper.arxiv_id}</dd></div><div className="bibliographic-row"><dt>{t('版本')}</dt><dd><select aria-label={t('版本')} value={version} onChange={e=>choose(Number(e.target.value))}>{paper.versions?.map(v=><option key={v.version} value={v.version} title={v.version_date}>v{v.version} · {dateLabel(v.version_date)}</option>)}</select></dd></div>{[[t('投稿时间'),dateLabel(metadata.submitted_at)],['DOI',metadata.doi],[t('许可证'),metadata.license]].map(([label,value])=><div className="bibliographic-row" key={label}><dt>{label}</dt><dd>{value||'—'}</dd></div>)}</dl></div>
  </aside></div><BackToTop target={pageTop}/>

  </>}
 </main><SelectionCopy/>{citationOpen&&paper&&<Suspense fallback={<p className="hint" role="status">{t('正在生成引用…')}</p>}><CitationDialog numbers={[String(paper.paper_id)]} fetcher={citationFetcher} filenamePrefix="arxiv" onClose={()=>setCitationOpen(false)}/></Suspense>}</>;
}
