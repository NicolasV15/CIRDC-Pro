import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import type {CopySnapshot} from './selectionTypes';

const Toolbar=lazy(()=>import('./SelectionCopyToolbar'));
const element=(node:Node|null)=>node?.nodeType===Node.ELEMENT_NODE?node as Element:node?.parentElement;

/** The initial page carries only selection detection; conversion loads after a selection. */
export default function SelectionCopy(){
 const [snapshot,setSnapshot]=useState<CopySnapshot|null>(null),serial=useRef(0),latest=useRef<CopySnapshot|null>(null);
 useEffect(()=>{
  let timer:ReturnType<typeof setTimeout>|undefined;
  function read(){
   if(document.activeElement?.closest('[data-copy-ui]'))return;
   if(document.activeElement?.matches('input,textarea,select,[contenteditable="true"]')){latest.current=null;setSnapshot(null);return;}
   const selected=window.getSelection();
   if(!selected||selected.isCollapsed||selected.rangeCount!==1){latest.current=null;setSnapshot(null);return;}
   const range=selected.getRangeAt(0),start=element(range.startContainer),end=element(range.endContainer),scope=start?.closest<HTMLElement>('[data-copy-scope]');
   if(!scope||end?.closest('[data-copy-scope]')!==scope||start?.closest('[data-copy-ui],.abstract-measure,[hidden],button,input,textarea,select,option,nav,summary')||end?.closest('[data-copy-ui],.abstract-measure,[hidden],button,input,textarea,select,option,nav,summary')){latest.current=null;setSnapshot(null);return;}
   if(!start?.closest('[data-copy-content]')&&!end?.closest('[data-copy-content]')){latest.current=null;setSnapshot(null);return;}
   const previous=latest.current;
   if(previous&&previous.scope===scope&&previous.range.startContainer===range.startContainer&&previous.range.startOffset===range.startOffset&&previous.range.endContainer===range.endContainer&&previous.range.endOffset===range.endOffset)return;
   const value={range:range.cloneRange(),scope,token:++serial.current,backwards:selected.anchorNode===range.endContainer&&selected.anchorOffset===range.endOffset};latest.current=value;setSnapshot(value);
  }
  function schedule(event?:Event){
   if(event instanceof KeyboardEvent&&event.key==='Escape'){if(timer!==undefined)clearTimeout(timer);latest.current=null;setSnapshot(null);return;}
   if(event?.target instanceof Element&&event.target.closest('[data-copy-ui]'))return;
   if(document.activeElement?.closest('[data-copy-ui]'))return;
   const selected=window.getSelection(),previous=latest.current,current=selected?.rangeCount===1?selected.getRangeAt(0):undefined;
   if(previous&&(!current||selected?.isCollapsed||current.startContainer!==previous.range.startContainer||current.startOffset!==previous.range.startOffset||current.endContainer!==previous.range.endContainer||current.endOffset!==previous.range.endOffset)){latest.current=null;setSnapshot(null);}
   if(timer!==undefined)clearTimeout(timer);timer=setTimeout(read,180);
  }
  document.addEventListener('selectionchange',schedule);document.addEventListener('pointerup',schedule);document.addEventListener('keyup',schedule);
  return()=>{if(timer!==undefined)clearTimeout(timer);document.removeEventListener('selectionchange',schedule);document.removeEventListener('pointerup',schedule);document.removeEventListener('keyup',schedule);};
 },[]);
 return snapshot?<Suspense fallback={null}><Toolbar snapshot={snapshot} onDismiss={()=>{latest.current=null;setSnapshot(null);}}/></Suspense>:null;
}
