import React,{useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import {t} from './i18n';
import {AbstractPartContent} from './AbstractText';
import type {TitlePart} from './titleMath';
import {abstractParts,abstractPrefix,abstractUnits} from './abstractMath';

function Copy({parts,limit,wide,source}:{parts:TitlePart[];limit?:number;wide:Set<number>;source?:string}){
 const visible=limit===undefined?parts:abstractPrefix(parts,limit);
 return <span className="abstract-copy" data-copy-source-html={source?.trim()} data-copy-source-mode={source===undefined?undefined:'prefix'}>{visible.map((part,index)=><span key={index} data-abstract-part={index} className={part.type==='math'?'abstract-math'+(wide.has(index)?' math-overflow':''):undefined}><AbstractPartContent part={part}/></span>)}</span>;
}

export default function AbstractPreview({number,preview,fetcher}:{number:string;preview:string;fetcher:(path:string)=>Promise<any>}){
 const [expanded,setExpanded]=useState(false),[full,setFull]=useState<string|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const parts=useMemo(()=>abstractParts(preview),[preview]),fullParts=useMemo(()=>abstractParts(full??preview),[full,preview]);
 const size=abstractUnits(parts),[limit,setLimit]=useState(size),[truncated,setTruncated]=useState(false),[wideKey,setWideKey]=useState('');
 const wide=useMemo(()=>new Set(wideKey?wideKey.split(',').map(Number):[]),[wideKey]);
 const host=useRef<HTMLDivElement>(null),source=useRef<HTMLParagraphElement>(null),loading=useRef(false),id=React.useId(),expandLabel=t('展开摘要');
 useLayoutEffect(()=>{
  let frame=0,disposed=false;
  function fit(){
   frame=0;const container=host.current,original=source.current;
   if(!container||!original)return;
   const width=container.getBoundingClientRect().width;if(!width)return;
   const fragments=Array.from(original.querySelector('.abstract-copy')!.children) as HTMLElement[],oversized:number[]=[];
   fragments.forEach((node,index)=>{
    const math=node.querySelector<HTMLElement>('.katex'),overflow=!!math&&math.getBoundingClientRect().width>width+.5;
    node.classList.toggle('math-overflow',overflow);if(overflow)oversized.push(index);
   });
   setWideKey(oversized.join(','));
   const measure=document.createElement('p');measure.className='snippet abstract-measure';measure.style.width=width+'px';measure.setAttribute('aria-hidden','true');
   const content=document.createElement('span');content.className='abstract-copy';measure.append(content);container.append(measure);
   function show(units:number){
    content.replaceChildren();const prefix=abstractPrefix(parts,units);
    prefix.forEach((part,index)=>{const node=fragments[index].cloneNode(true) as HTMLElement;if(part.type==='text')(part.script?node.querySelector(part.script)!:node).textContent=part.value;content.append(node);});
   }
   try{
    show(size);const maxHeight=parseFloat(getComputedStyle(measure).lineHeight)*2+.5;
    const needsTail=measure.getBoundingClientRect().height>maxHeight||preview.length>=400;setTruncated(needsTail);
    if(!needsTail){setLimit(size);return;}
    const tail=document.createElement('span');tail.className='abstract-tail';tail.append(document.createTextNode('… '));
    const label=document.createElement('span');label.className='abstract-toggle';label.textContent=expandLabel;tail.append(label);measure.append(tail);
    let lower=0,upper=size;
    while(lower<upper){const middle=Math.ceil((lower+upper)/2);show(middle);if(measure.getBoundingClientRect().height<=maxHeight)lower=middle;else upper=middle-1;}
    setLimit(lower);
   }finally{measure.remove();}
  }
  const schedule=()=>{if(!disposed&&!frame)frame=requestAnimationFrame(fit);};
  fit();const resize=new ResizeObserver(schedule);if(host.current)resize.observe(host.current);
  const mutation=new MutationObserver(schedule);if(source.current)mutation.observe(source.current,{childList:true,subtree:true});
  void document.fonts.ready.then(schedule);document.fonts.addEventListener('loadingdone',schedule);
  return()=>{disposed=true;cancelAnimationFrame(frame);resize.disconnect();mutation.disconnect();document.fonts.removeEventListener('loadingdone',schedule);};
 },[parts,size,preview.length,expandLabel]);
 // Full summaries may contain formulas beyond the preview's first 400 characters.
 const expandedCopy=useRef<HTMLParagraphElement>(null);
 useEffect(()=>{
  const node=expandedCopy.current;if(!expanded||!node)return;
  let frame=0,disposed=false;
  const update=()=>{frame=0;const width=node.clientWidth;for(const part of node.querySelectorAll<HTMLElement>('.abstract-math')){const math=part.querySelector<HTMLElement>('.katex');part.classList.toggle('math-overflow',!!math&&math.getBoundingClientRect().width>width+.5);}};
  const schedule=()=>{if(!disposed&&!frame)frame=requestAnimationFrame(update);};
  const resize=new ResizeObserver(schedule);resize.observe(node);
  const mutation=new MutationObserver(schedule);mutation.observe(node,{childList:true,subtree:true});
  void document.fonts.ready.then(schedule);document.fonts.addEventListener('loadingdone',schedule);schedule();
  return()=>{disposed=true;cancelAnimationFrame(frame);resize.disconnect();mutation.disconnect();document.fonts.removeEventListener('loadingdone',schedule);};
 },[expanded,fullParts]);
 async function readFull(){
  if(loading.current)return;loading.current=true;setBusy(true);setError('');
  try{const value=await fetcher('/api/papers/'+encodeURIComponent(number));setFull(typeof value.paper.record.abstract==='string'?value.paper.record.abstract:'');}
  catch(e){setError((e as Error).message);}finally{loading.current=false;setBusy(false);}
 }
 function toggle(){const opening=!expanded;setExpanded(opening);if(opening&&full===null&&!loading.current)void readFull();}
 return <div className="abstract-preview" ref={host}>
  <p className="snippet abstract-source abstract-measure" ref={source} aria-hidden="true"><Copy parts={parts} wide={wide}/></p>
  <p id={id} ref={expandedCopy} data-copy-content="abstract" className={'snippet'+(expanded?' expanded':'')}><Copy parts={expanded?fullParts:parts} limit={expanded?undefined:limit} wide={expanded?new Set():wide} source={expanded?full??preview:preview}/>{(expanded||truncated)&&<span className="abstract-tail">{expanded?' ':<span aria-hidden="true">… </span>}<button type="button" className="abstract-toggle" aria-expanded={expanded} aria-controls={id} onClick={toggle}>{expanded?t('收起摘要'):expandLabel}</button></span>}</p>
  {expanded&&busy&&<p className="hint abstract-loading" role="status">{t('正在读取完整摘要…')}</p>}
  {expanded&&error&&<div className="abstract-error" role="alert"><p className="error">{t(error)}</p><button type="button" onClick={()=>void readFull()}>{t('重试加载摘要')}</button></div>}
 </div>;
}
