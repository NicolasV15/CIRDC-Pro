import {useCallback,useState} from 'react';
import PaperCitations from './PaperCitations';
import PaperPatentCitations from './PaperPatentCitations';
import {locale,t,useLanguage} from './i18n';
import type {CitationSummary} from './citationSummary';

type Fetcher=(path:string,method?:string,data?:unknown)=>Promise<any>;
type Kind='papers'|'patents';
const kinds:Kind[]=['papers','patents'];
const label=(kind:Kind)=>t(kind==='papers'?'论文引用':'专利引用');
const initial=():Record<Kind,CitationSummary>=>({papers:{count:null,absent:false},patents:{count:null,absent:false}});

export default function CitationPanel({number,fetcher}:{number:string;fetcher:Fetcher}){
 useLanguage();
 const [expanded,setExpanded]=useState(false),[selected,setSelected]=useState<Kind>('papers'),[summaries,setSummaries]=useState(initial);
 const receivePapers=useCallback((value:CitationSummary)=>setSummaries(previous=>previous.papers.count===value.count&&previous.papers.absent===value.absent?previous:{...previous,papers:value}),[]);
 const receivePatents=useCallback((value:CitationSummary)=>setSummaries(previous=>previous.patents.count===value.count&&previous.patents.absent===value.absent?previous:{...previous,patents:value}),[]);
 const id='paper-citation-panel-'+number,contentId=id+'-content';
 const count=(kind:Kind)=>summaries[kind].count===null?'—':summaries[kind].count!.toLocaleString(locale());
 return <section id={id} className="panel paper-citation-panel" aria-label={t('被引')}>
  <div className="section-heading references-heading"><h2><button type="button" className="reference-toggle" aria-label={expanded?t('收起被引'):t('展开被引')} aria-expanded={expanded} aria-controls={contentId} onClick={()=>setExpanded(value=>!value)}>{t('被引')}</button></h2></div>
  <div id={contentId} hidden={!expanded}>
   <div className="citation-type-tabs citation-groups" role="tablist" aria-label={t('被引类型')}>{kinds.map(kind=><button key={kind} id={id+'-tab-'+kind} type="button" className="citation-type-tab" role="tab" aria-selected={selected===kind} aria-controls={id+'-type-'+kind} tabIndex={selected===kind?0:-1} onClick={()=>setSelected(kind)} onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'papers':event.key==='End'?'patents':kind==='papers'?'patents':'papers';setSelected(next);document.getElementById(id+'-tab-'+next)?.focus();}}}>{label(kind)}<span>{count(kind)}</span></button>)}</div>
   <div id={id+'-type-papers'} role="tabpanel" aria-labelledby={id+'-tab-papers'} hidden={selected!=='papers'}><PaperCitations number={number} fetcher={fetcher} embedded onSummary={receivePapers}/></div>
   <div id={id+'-type-patents'} role="tabpanel" aria-labelledby={id+'-tab-patents'} hidden={selected!=='patents'}><PaperPatentCitations number={number} fetcher={fetcher} embedded onSummary={receivePatents}/></div>
  </div>
 </section>;
}
