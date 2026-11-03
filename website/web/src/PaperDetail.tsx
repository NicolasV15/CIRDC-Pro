import React,{useEffect,useRef,useState} from 'react';
import {t,localizedText,keywordGroupLabel,contentTypeLabel} from './i18n';
import {api} from './api';
import {time} from './format';
import Icon from './Icon';
import {PdfAcquisition} from './PdfAcquisition';
import MetadataMaintenance from './MetadataMaintenance';
import ReaderLayoutControls,{useReaderLayout} from './ReaderLayoutControls';
import ScientificTitle from './ScientificTitle';
import AbstractText from './AbstractText';
import PaperReferences from './PaperReferences';
import CitationPanel from './CitationPanel';
import PaperSearchBar from './PaperSearchBar';
import BackToTop from './BackToTop';
import {AuthorLinks} from './AuthorSearch';
import {VenueTags} from './VenueTags';
import type {AuthorReference} from './authorLinks';
import type {ReferenceJump} from './paperReferenceData';
import type {Passage,ReadingResource} from './types';
import type {FocusResult,PassageFocus} from './passageLocate';
const CitationDialog=React.lazy(()=>import('./CitationDialog'));
const DocumentReader=React.lazy(()=>import('./DocumentReader').then(module=>({default:module.DocumentReader})));

function text(value:unknown){return typeof value==='string'?value.replace(/<[^>]*>/g,''):'';}
function resourceHref(value:unknown){return typeof value==='string'&&value.startsWith('/api/resources/')?value:undefined;}
export function readingHref(item:ReadingResource){return resourceHref(item.reader_href)||resourceHref(item.href);}
function isPdfResource(item:ReadingResource){return item.media_type?.split(';')[0].trim().toLowerCase()==='application/pdf';}
function PaperPdfLink({items,notice,noticeLocales,auto=false}:{items?:ReadingResource[];notice?:string;noticeLocales?:Record<string,string>;auto?:boolean}){
 const noticeId=React.useId();
 const pdf=(items||[]).find(item=>item.kind!=='document'&&resourceHref(item.href)&&isPdfResource(item));
 const missingText=localizedText(noticeLocales,notice||t('暂无已关联 PDF'));
 const acquisition=(items||[]).find(item=>item.kind==='pdf-acquisition'&&item.href?.startsWith('/api/content/'));
 if(acquisition)return <PdfAcquisition key={acquisition.href} href={acquisition.href} api={api} auto={auto}/>;
 return pdf?<a className="button detail-pdf-trigger" href={readingHref(pdf)} target="_blank" rel="noopener noreferrer"><Icon name="file"/>{t('阅读 PDF')}<Icon name="external" className="icon-trailing"/></a>:<span className="pdf-unavailable"><button type="button" className="detail-pdf-trigger reading-pdf-unavailable" disabled aria-describedby={noticeId} title={missingText}><Icon name="file"/>{t('阅读 PDF')}</button><span id={noticeId} className="pdf-unavailable-reason">{missingText}</span></span>;
}
type Locate={q:string;terms:string;passage:number;version:string|null};
type Hits={state:string;items:Passage[];total:number;match:string;alternatives:string[][]};
const hitStates:Record<string,string>={disabled:'正文检索尚未启用。',no_body:'本文正文尚未获取，无法在正文中定位。',not_indexed:'本文正文已获取，但尚未建立检索索引。',unknown:'正文目录仍在同步，暂不能确认本文是否已有正文。'};
const matchLabels:Record<string,string>={exact:'原句精确命中',approximate:'近似匹配（非原句）',terms:'同段包含全部检索词',phrase:'短语命中'};
function locateFromUrl():Locate|null{
 const params=new URLSearchParams(window.location.search),q=(params.get('q')||'').trim();
 return q?{q,terms:params.get('terms')==='exact'?'exact':'expand',passage:Number(params.get('passage')??-1),version:params.get('v')}:null;
}
/** Moves between every full-text hit of the current query inside this paper. */
function PassageNavigator({number,locate,onFocus,result,onClose}:{number:string;locate:Locate;onFocus:(focus:PassageFocus|null)=>void;result:FocusResult|null;onClose:()=>void}){
 const [hits,setHits]=useState<Hits|null>(null),[index,setIndex]=useState(0),[error,setError]=useState(''),token=useRef(0);
 useEffect(()=>{
  let active=true;setHits(null);setError('');
  void api('/api/papers/'+encodeURIComponent(number)+'/passages?'+new URLSearchParams({q:locate.q,limit:'200',...(locate.terms==='exact'?{terms:'exact'}:{})})).then(value=>{
   if(!active)return;
   const alternatives=((value.query?.alternatives||[]) as string[][]).flat().map(option=>option.split(' '));
   const found=value.items.findIndex((item:Passage)=>item.ordinal===locate.passage);
   setHits({state:value.state,items:value.items,total:value.total,match:value.query?.match||'',alternatives});setIndex(Math.max(0,found));
  }).catch(e=>{if(active)setError((e as Error).message);});
  return()=>{active=false;};
 },[number,locate.q,locate.terms]);
 const hit=hits?.items[index];
 useEffect(()=>{
  if(!hits||!hit){onFocus(null);return;}
  onFocus({ordinal:hit.ordinal,version:hit.version,fingerprint:hit.fingerprint,alternatives:hits.alternatives,token:++token.current});
  history.replaceState(history.state,'','/papers/'+number+'?'+new URLSearchParams({passage:String(hit.ordinal),...(hit.version?{v:hit.version}:{}),q:locate.q,...(locate.terms==='exact'?{terms:'exact'}:{})}));
 },[hits,index]);
 return <div className="passage-navigator" role="region" aria-label={t('正文命中')}>
  <span className="passage-navigator-label"><Icon name="search"/>{t('正文命中')}</span>
  {error?<span className="error">{t(error)}</span>:!hits?<span>{t('正在读取命中…')}</span>:hits.state!=='indexed'?<span>{t(hitStates[hits.state]||hitStates.unknown)}</span>:!hits.total?<span>{t('当前正文中没有该查询的命中。')}</span>:<>
   <button type="button" className="compact" aria-label={t('上一处命中')} disabled={index<=0} onClick={()=>setIndex(index-1)}><Icon name="left"/></button>
   <span className="passage-count" aria-live="polite">{index+1} / {hits.total}{hits.total>hits.items.length?'+':''}</span>
   <button type="button" className="compact" aria-label={t('下一处命中')} disabled={index>=hits.items.length-1} onClick={()=>setIndex(index+1)}><Icon name="right"/></button>
   <span className={'passage-match'+(hits.match==='approximate'?' is-approximate':'')}>{t(matchLabels[hits.match]||hits.match)}</span>
   {hit?.section&&<span className="passage-section">{hit.section}</span>}
  </>}
  {result?.status==='relocated'&&<span className="passage-notice">{t('正文版本已更新，已按段落文字重新定位。')}</span>}
  {result?.status==='missing'&&<span className="passage-notice is-missing">{t('当前显示的正文中未找到该段落。')}</span>}
  <button type="button" className="ghost compact" onClick={onClose}><Icon name="close"/>{t('退出定位')}</button>
 </div>;
}
function ReadingResources({items}:{items?:ReadingResource[]}){
 const available=(items||[]).filter(item=>item.kind!=='document'&&!isPdfResource(item)&&resourceHref(item.href));
 if(!available.length)return null;
 return <section className="reading-resources"><h3>{t('本地资料')}</h3>{available.map(item=><div className="reading-resource" key={item.id}><a className="button wide" href={readingHref(item)} target="_blank" rel="noopener noreferrer"><Icon name="file"/><span>{localizedText(item.label_i18n,item.label)}</span><Icon name="external" className="icon-trailing"/></a>{item.note&&<p className="hint">{localizedText(item.note_i18n,item.note)}{item.size_bytes?' · '+(item.size_bytes/1024/1024).toFixed(1)+' MiB':''}</p>}</div>)}</section>;
}
export default function PaperDetail({number,back,initialQuery,onSearch}:{number:string;back:()=>void;initialQuery:string;onSearch:(query:string)=>void}){
 const pageTop=useRef<HTMLHeadingElement>(null);
 const [item,setItem]=useState<any>(),[error,setError]=useState(''),[citationOpen,setCitationOpen]=useState(false);
 const [documentReadyFor,setDocumentReadyFor]=useState<string|null>(null);
 const [keywordsExpanded,setKeywordsExpanded]=useState(false);
 const [abstractExpanded,setAbstractExpanded]=useState(true);
 const [referenceJump,setReferenceJump]=useState<(ReferenceJump&{paper:string})|null>(null),referenceSequence=useRef(0),loadedNumber=useRef<string|null>(null);
 const requestReference=React.useCallback((order:number,source:HTMLElement)=>setReferenceJump({order,source,token:++referenceSequence.current,paper:number}),[number]);
 const documentReady=React.useCallback(()=>setDocumentReadyFor(number),[number]);
 const {layout,update:changeLayout,reset:resetLayout}=useReaderLayout(),publicationToggle=useRef<HTMLButtonElement>(null);
 const [locate,setLocate]=useState<Locate|null>(locateFromUrl),[focus,setFocus]=useState<PassageFocus|null>(null),[focusResult,setFocusResult]=useState<FocusResult|null>(null);
 useEffect(()=>{setLocate(locateFromUrl());setFocus(null);setFocusResult(null);},[number]);
 const changeFocus=React.useCallback((value:PassageFocus|null)=>{setFocusResult(null);setFocus(value);},[]);
 function closeLocate(){setLocate(null);setFocus(null);setFocusResult(null);history.replaceState(history.state,'','/papers/'+number);}
 const publicationId='publication-information-'+number;
 const keywordsContentId='paper-keywords-'+number+'-content';
 const abstractContentId='paper-abstract-'+number+'-content';
 function togglePublication(){changeLayout({infoOpen:!layout.infoOpen});requestAnimationFrame(()=>publicationToggle.current?.focus({preventScroll:true}));}
 useEffect(()=>{let active=true;setKeywordsExpanded(false);setAbstractExpanded(true);setError('');void api('/api/papers/'+number).then(r=>{if(active){loadedNumber.current=number;setItem(r.paper);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[number]);
 if(error)return <main id="main" className="workspace detail-page detail-state"><div className="state-card" role="alert"><Icon name="info"/><p className="error">{t(error)}</p><button type="button" onClick={back}><Icon name="back"/>{t('返回检索')}</button></div></main>;
 if(!item||loadedNumber.current!==number)return <main id="main" className="workspace detail-page detail-state"><div className="state-card" role="status"><span className="spinner" aria-hidden="true"/>{t('正在读取论文记录…')}</div></main>;
 const p=item.record;
 const references:AuthorReference[]=item.author_refs||(p.authors||[]).map((a:any,i:number)=>({source:'ieee',author_id:a.id?String(a.id):null,name:a.preferredName||[a.firstName,a.lastName].filter(Boolean).join(' '),ordinal:i}));
 const keywordGroups=Object.entries(p.keywords||{});
 return <><main id="main" className="workspace detail-page" data-copy-scope style={{'--reader-page-width':layout.pageWidth+'px','--reader-toc-width':layout.tocWidth+'px','--reader-font-scale':layout.fontScale/100,'--publication-column-width':(layout.infoOpen?layout.infoWidth:44)+'px'} as React.CSSProperties}>
  <div className="detail-toolbar"><button type="button" className="back" onClick={back}><Icon name="back"/>{t('返回检索')}</button><PaperSearchBar number={number} initialQuery={initialQuery} onSearch={onSearch}/><ReaderLayoutControls layout={layout} onChange={changeLayout} onReset={resetLayout}/></div>
  <header className="detail-header">
   {p.articleContentType&&<p className="detail-kicker" data-copy-ignore>{contentTypeLabel(p.articleContentType)}</p>}
   <h1 ref={pageTop} tabIndex={-1} data-copy-content="title"><ScientificTitle value={p.articleTitle} fallback={t('未提供标题')}/></h1>
   <AuthorLinks references={references} detail/>
   <div className="publication-line detail-publication-line"><VenueTags paper={{kind:p.articleContentType,venue:String(p.publicationNumber||''),venue_series:item.venue_series,publication:p.publicationTitle}}/><p className="publication">{[p.publicationTitle,p.publicationYear,p.publicationDate].filter(Boolean).join(' · ')}</p></div>
   <div className="detail-record-toolbar"><div className="detail-record-actions"><button type="button" className="detail-citation-trigger" aria-label={t('获取引用格式：')+(text(p.articleTitle)||number)} onClick={()=>setCitationOpen(true)}><Icon name="quote"/>{t('引用')}</button><PaperPdfLink items={item.resources} notice={item.resource_notice} noticeLocales={item.resource_notice_i18n} auto={documentReadyFor===number}/><a className="button detail-source-link" href={'https://ieeexplore.ieee.org/document/'+number} target="_blank" rel="noreferrer">{t('IEEE Xplore 原文')}<Icon name="external" className="icon-trailing"/></a></div><span className="detail-record-id">{t('论文编号')} <code>{number}</code></span></div>
  </header>
  <div className="detail-grid"><section className="detail-main" aria-label={t('论文内容')}>
   <section className="panel abstract-panel"><div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={abstractExpanded?t('收起摘要'):t('展开摘要')} aria-controls={abstractContentId} aria-expanded={abstractExpanded} onClick={()=>setAbstractExpanded(value=>!value)}>{t('摘要')}</button></h2></div><div id={abstractContentId} hidden={!abstractExpanded}><p className="abstract" data-copy-content="abstract" data-copy-source-html={typeof p.abstract==='string'?p.abstract.trim():undefined} data-copy-source-mode="literal" data-copy-preserve-lines><AbstractText value={p.abstract} fallback="—"/></p><MetadataMaintenance key={number} number={number} fetcher={api} onReady={()=>{void api('/api/papers/'+number).then(r=>{if(loadedNumber.current===number)setItem(r.paper);});}}/></div></section>
   <React.Suspense fallback={null}><DocumentReader resource={(item.resources||[]).find((resource:ReadingResource)=>resource.kind==='document')} fetcher={api} onReady={documentReady} paperNumber={number} onReference={requestReference} focus={focus} onFocusResult={setFocusResult}/></React.Suspense>
   <PaperReferences key={number} number={number} fetcher={api} jump={referenceJump?.paper===number?referenceJump:null}/>
   <CitationPanel key={'citations:'+number} number={number} fetcher={api}/>
   <div className="panel keywords-panel"><div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={keywordsExpanded?t('收起关键词'):t('展开关键词')} aria-controls={keywordsContentId} aria-expanded={keywordsExpanded} onClick={()=>setKeywordsExpanded(value=>!value)}>{t('关键词')}</button></h2></div><div id={keywordsContentId} hidden={!keywordsExpanded}>{keywordGroups.map(([name,words])=><div className="keyword-group" key={name}><h3>{keywordGroupLabel(name)}</h3><div className="tags">{(words as string[]).map((word,i)=><a key={i} className="keyword-link" href={'/?'+new URLSearchParams({field:'keywords',q:word})} target="_blank" rel="noopener noreferrer" aria-label={t('在新标签页检索关键词：')+word}>{word}<Icon name="external"/></a>)}</div></div>)}{!keywordGroups.length&&<p className="muted">{'—'}</p>}</div></div>
   <details className="panel raw"><summary>{t('查看原始元数据 JSON')}</summary><pre>{JSON.stringify(item,null,2)}</pre></details>
  </section>{locate&&<PassageNavigator number={number} locate={locate} onFocus={changeFocus} result={focusResult} onClose={closeLocate}/>}<aside className={'publication-sidebar'+(!layout.infoOpen?' is-collapsed':'')}>{!layout.infoOpen&&<button type="button" ref={publicationToggle} className="publication-sidebar-rail" aria-label={t('展开出版信息')} title={t('展开出版信息')} aria-expanded={false} aria-controls={publicationId} onClick={togglePublication}><Icon name="right" className="rail-chevron"/><span className="publication-sidebar-rail-label">{t('出版信息')}</span></button>}<div id={publicationId} className="panel bibliographic" hidden={!layout.infoOpen}><div className="publication-sidebar-heading"><h2>{t('出版信息')}</h2><button type="button" ref={layout.infoOpen?publicationToggle:undefined} className="publication-sidebar-toggle" aria-label={t('收起出版信息')} title={t('收起出版信息')} aria-expanded={true} aria-controls={publicationId} onClick={togglePublication}><Icon name="right"/></button></div><dl>{[[t('论文编号'),number],[t('类型'),contentTypeLabel(p.articleContentType)],[t('出版物编号'),p.publicationNumber],[t('出版年份'),p.publicationYear],[t('卷 / 期'),[p.volume,p.issue].filter(Boolean).join(' / ')],[t('页码'),[p.startPage,p.endPage].filter(Boolean).join('–')],[t('出版商'),p.publisher],[t('DOI'),p.doi||t('未提供')],[t('记录更新'),time(item.updated_at)]].map(([k,v])=><div className="bibliographic-row" key={k}><dt>{k}</dt><dd>{v||'—'}</dd></div>)}</dl><ReadingResources items={item.resources}/></div></aside></div>
 </main><BackToTop target={pageTop}/>{citationOpen&&<React.Suspense fallback={<p className="hint" role="status">{t('正在生成引用…')}</p>}><CitationDialog numbers={[number]} fetcher={api} onClose={()=>setCitationOpen(false)}/></React.Suspense>}</>;
}
