import {useEffect,useRef,useState} from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import {t,locale,localizedText} from './i18n';
import {restoreDocumentReferences} from './documentReferences';
import {restoreDocumentHeadings} from './documentHeadings';

type Fetcher=(path:string,method?:string,data?:unknown)=>Promise<any>;
type Resource={href:string;kind?:string};
type TocEntry={id:string;title:string;level:number};
const sidebarQuery='(min-width:1200px)';
const labels:Record<string,string>={missing:'正文尚未缓存',queued:'等待采集节点',fetching:'正在获取正文',body_ready:'正文已就绪，正在补齐图片',ready:'共享正文已缓存',source_no_body:'检查完成，官网无正文',partial:'部分资源未完成',failed:'当前节点未能取得正文'};
function localURL(value:string){const u=new URL(value,location.origin);if(u.origin!==location.origin||!u.pathname.startsWith('/api/'))throw Error('Invalid resource URL');return u.pathname+u.search;}

export function DocumentReader({resource,fetcher}:{resource?:Resource;fetcher:Fetcher}){
 const [value,setValue]=useState<any>(),[body,setBody]=useState(''),[error,setError]=useState(''),[image,setImage]=useState<{src:string;alt:string}|null>(null);
 const element=useRef<HTMLDivElement>(null),tocElement=useRef<HTMLDetailsElement>(null);const current=useRef(0);
 const [activeSection,setActiveSection]=useState(''),[tocOpen,setTocOpen]=useState(()=>window.matchMedia(sidebarQuery).matches);
 const [headingTitles,setHeadingTitles]=useState<Record<string,string>>({});
 const toc:TocEntry[]=(Array.isArray(value?.document?.toc)?value.document.toc:[]).map((entry:TocEntry)=>({...entry,title:Object.hasOwn(headingTitles,entry.id)?headingTitles[entry.id]:entry.title}));
 const tocIds=JSON.stringify(toc.map(entry=>entry.id));
 useEffect(()=>{
  const media=window.matchMedia(sidebarQuery),change=()=>setTocOpen(media.matches);
  media.addEventListener('change',change);return()=>media.removeEventListener('change',change);
 },[]);
 useEffect(()=>{
  if(!resource)return;let active=true;let timer:ReturnType<typeof setTimeout>|undefined;let version='';const request=++current.current;
  setValue(undefined);setBody('');setError('');setHeadingTitles({});
  async function update(v:any){if(!active||request!==current.current)return;setValue(v);
   if(v.document&&v.document.version!==version){const url=localURL(v.document.body_url);const r=await fetch(url,{credentials:'same-origin'});if(!r.ok)throw Error(t('正文暂不可读取'));const html=await r.text();if(!active||request!==current.current)return;version=v.document.version;setBody(html)}
   if(['queued','fetching','body_ready'].includes(v.job?.state||v.state))timer=setTimeout(()=>void poll(),2000);
  }
  async function poll(){try{await update(await fetcher(localURL(resource!.href)))}catch(e){if(active)setError((e as Error).message)}}
  void(async()=>{try{
   let v=await fetcher(localURL(resource.href));
   if(!active)return;
   if(!v.document&&(!v.job||['failed','missing'].includes(v.state)))v=await fetcher(localURL(resource.href)+'/ensure','POST',{});
   await update(v);
  }catch(e){if(active)setError((e as Error).message)}})();
  return()=>{active=false;if(timer)clearTimeout(timer)};
 },[resource?.href,fetcher]);
 useEffect(()=>{
  if(!element.current||!body)return;
  setHeadingTitles(restoreDocumentHeadings(element.current));
  restoreDocumentReferences(element.current);
  for(const node of element.current.querySelectorAll<HTMLElement>('.doc-math')){
   let tex=node.textContent||'';const display=tex.startsWith('\\[');tex=tex.replace(/^\\[([]/,'').replace(/\\[)\]]$/,'');
   try{katex.render(tex,node,{displayMode:display,throwOnError:false,trust:false,strict:'ignore',output:'htmlAndMathml',maxExpand:1000})}catch{node.textContent=tex}
  }
 },[body]);
 // Large reading fonts may make an inline formula wider than the whole article.
 useEffect(()=>{
  const container=element.current;if(!container||!body)return;
  const formulas=Array.from(container.querySelectorAll<HTMLElement>('.doc-math')).filter(node=>!node.querySelector('.katex-display'));
  let frame=0,disposed=false;
  const update=()=>{frame=0;const width=container.clientWidth;for(const node of formulas){const math=node.querySelector<HTMLElement>('.katex');node.classList.toggle('math-overflow',!!math&&math.getBoundingClientRect().width>width);}};
  const schedule=()=>{if(!frame)frame=requestAnimationFrame(update);};
  const resize=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(schedule);
  resize?.observe(container);
  for(const node of formulas)for(const base of node.querySelectorAll<HTMLElement>(':scope>.katex>.katex-html>.base'))resize?.observe(base);
  window.addEventListener('resize',schedule);void document.fonts?.ready.then(()=>{if(!disposed)schedule();});schedule();
  return()=>{disposed=true;cancelAnimationFrame(frame);resize?.disconnect();window.removeEventListener('resize',schedule);};
 },[body]);
 // Track the section at the reading line, including fast jumps and image reflow.
 useEffect(()=>{
  const container=element.current,ids=new Set<string>(JSON.parse(tocIds));
  if(!resource||!body||!container||!ids.size){setActiveSection('');return;}
  const headings=Array.from(container.querySelectorAll<HTMLElement>('[id]')).filter(node=>ids.has(node.id));
  if(!headings.length){setActiveSection('');return;}
  let frame=0;
  const update=()=>{
   frame=0;let active='';
   for(const heading of headings){if(heading.getBoundingClientRect().top>100)break;active=heading.id;}
   const last=headings[headings.length-1],lastBounds=last.getBoundingClientRect();
   if(window.scrollY>0&&Math.ceil(window.scrollY+window.innerHeight)>=document.documentElement.scrollHeight-2&&lastBounds.top<window.innerHeight&&lastBounds.bottom>0)active=last.id;
   setActiveSection(previous=>previous===active?previous:active);
  };
  const schedule=()=>{if(!frame)frame=requestAnimationFrame(update);};
  const resize=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(schedule);
  resize?.observe(container);
  window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);window.addEventListener('hashchange',schedule);
  container.addEventListener('load',schedule,true);schedule();
  return()=>{cancelAnimationFrame(frame);resize?.disconnect();window.removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);window.removeEventListener('hashchange',schedule);container.removeEventListener('load',schedule,true);};
 },[body,tocIds,resource?.href]);
 useEffect(()=>{
  const nav=tocElement.current?.querySelector('nav'),link=nav?.querySelector<HTMLElement>('[aria-current="location"]');
  if(!nav||!link)return;
  const keepVisible=()=>{
   if(!nav.clientHeight)return;
   const bounds=nav.getBoundingClientRect(),current=link.getBoundingClientRect();
   if(current.top<bounds.top)nav.scrollTop+=current.top-bounds.top-8;
   else if(current.bottom>bounds.bottom)nav.scrollTop+=current.bottom-bounds.bottom+8;
  };
  const resize=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(keepVisible);
  resize?.observe(nav);keepVisible();
  return()=>resize?.disconnect();
 },[activeSection,tocOpen]);
 // A failed image is retried only after the catalog reports more completed assets.
 useEffect(()=>{if(!element.current)return;for(const img of element.current.querySelectorAll<HTMLImageElement>('img[data-content-asset]')){if(img.dataset.failed==='1'&&value?.document?.assets?.some((asset:any)=>asset.id===img.dataset.contentAsset&&asset.status==='ready')){delete img.dataset.failed;img.src=img.src.split('?')[0]+'?ready='+String(value?.document?.assets_ready||0)}}},[value?.document?.assets_ready]);
 if(!resource)return null;
 return <div className={'document-reader-layout'+(body&&toc.length?' has-toc':'')}>
{!!body&&!!toc.length&&<details ref={tocElement} className="document-toc" open={tocOpen} onToggle={event=>setTocOpen(event.currentTarget.open)}><summary><span>{t('章节目录')}</span><span className="document-toc-current">{toc.find(entry=>entry.id===activeSection)?.title||''}</span></summary><nav aria-label={t('章节目录')}>{toc.map(entry=><a className={'level-'+entry.level} key={entry.id} href={'#'+entry.id} aria-current={activeSection===entry.id?'location':undefined} onClick={event=>{if(event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&!event.shiftKey){if(!window.matchMedia(sidebarQuery).matches)setTocOpen(false);}}}>{entry.title}</a>)}</nav></details>}
  <section className="panel document-reader" aria-label={t('文章正文')}>
  <div className="section-heading"><h2>{t('文章正文')}</h2><span className={'badge '+(value?.state||'queued')}>{t(labels[value?.state]||'正在检查共享正文')}</span></div>
  <p className="muted document-progress" role="status">{value?.document?<>{t('图片资源：')}{value.document.assets_ready} / {value.document.assets_total}{t(' · 获取时间：')}{value.document.fetched_at?new Date(value.document.fetched_at).toLocaleString(locale()):'—'}</>:value?.state==='source_no_body'?localizedText(value.result?.message_i18n,t('官网未提供在线正文，等待后续文档解析。')):t('已缓存时直接读取；缺失时由固定节点自动获取本篇文章。')}</p>
  {value?.state==='partial'&&<p className="hint">{t('正文可以阅读，部分图片暂不可用；此版本尚未完整缓存。')}</p>}
  {(error||value?.job?.error)&&<p className="error" role="alert">{error?t(error):t('获取未完成，仍可使用论文原始链接或本地资料。')}{value?.job?.error&&<code> {value.job.error}</code>}</p>}
   <div className="document-layout">
    {body&&<div className="document-body" ref={element} dangerouslySetInnerHTML={{__html:body}} onErrorCapture={event=>{const node=event.target;if(node instanceof HTMLImageElement){node.dataset.failed='1';node.alt=t('图片暂不可用')}}} onClick={event=>{const node=event.target;if(node instanceof Element&&node.closest('a.document-reference-link')&&event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&!event.shiftKey&&!window.matchMedia(sidebarQuery).matches)setTocOpen(false);if(node instanceof HTMLImageElement&&node.dataset.failed!=='1'&&node.complete&&node.naturalWidth>0){event.preventDefault();setImage({src:node.src,alt:node.alt});}}}/>}
   </div>
  {image&&<div className="document-lightbox" role="dialog" aria-modal="true" aria-label={t('查看大图')} onClick={()=>setImage(null)}><button type="button" onClick={()=>setImage(null)}>{t('关闭')}</button><img src={image.src} alt={image.alt}/></div>}
  </section>
 </div>;
}
