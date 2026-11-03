import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {t,useLanguage} from './i18n';
import {captureSelection} from './selectionContent';
import type {CopyFormat,CopyResult,CopyWarning} from './selectionFormats';
import type {CopySnapshot} from './selectionTypes';
import Icon from './Icon';
import './selectionCopy.css';

const formats:CopyFormat[]=['markdown','latex','text'];
const labels:Record<CopyFormat,string>={markdown:'复制 Markdown',latex:'复制 LaTeX',text:'复制纯文本'};
const warnings:Record<CopyWarning,string>={'table-simplified':'表格结构不完整、包含合并单元格或不适合当前格式，已按逐行内容复制。','image-link':'图片已按说明和链接复制。','source-unmapped':'部分原始格式无法与显示选区准确对应，已保留实际显示内容。','math-unavailable':'部分公式缺少可恢复的 TeX，未根据视觉字符猜测内容。','link-omitted':'不支持的链接地址已省略，保留选中文字。'};
function restore(snapshot:CopySnapshot){
 const range=snapshot.range;if(!range.startContainer.isConnected||!range.endContainer.isConnected)return;
 const selection=window.getSelection();if(!selection)return;
 selection.removeAllRanges();selection.addRange(range.cloneRange());
 if(snapshot.backwards&&selection.setBaseAndExtent)selection.setBaseAndExtent(range.endContainer,range.endOffset,range.startContainer,range.startOffset);
}
function Preview({result,format,onFormat,onClose,manual}:{result:CopyResult;format:CopyFormat;onFormat:(value:CopyFormat)=>void;onClose:()=>void;manual:boolean}){
 useLanguage();const dialog=useRef<HTMLDialogElement>(null),output=useRef<HTMLTextAreaElement>(null);
 useEffect(()=>{const el=dialog.current;if(!el)return;el.showModal();output.current?.focus();output.current?.select();return()=>{if(el.open)el.close();};},[]);
 useEffect(()=>{output.current?.focus();output.current?.select();},[format]);
 return <dialog ref={dialog} className="citation-dialog selection-copy-dialog" data-copy-ui aria-labelledby="selection-copy-preview-title" onCancel={event=>{event.preventDefault();onClose();}}>
  <header className="citation-header"><div><h2 id="selection-copy-preview-title">{t('选区格式文本')}</h2><p>{t(manual?'当前环境无法直接写入剪贴板，请复制下面的源码文本。':'下方为选区生成的格式源码。')}</p></div><button type="button" className="citation-close" aria-label={t('关闭复制预览')} onClick={onClose}><Icon name="close"/></button></header>
  <div className="citation-body"><div className="citation-formats" role="group" aria-label={t('选择复制格式')}>{formats.map(key=><button type="button" key={key} aria-pressed={key===format} onClick={()=>onFormat(key)}>{t(labels[key])}</button>)}</div>
   <label className="citation-output-label">{t('格式源码')}<textarea ref={output} readOnly spellCheck={false} value={result.values[format]} aria-label={t('格式源码')}/></label>
   <div className="citation-actions"><button type="button" onClick={()=>{output.current?.focus();output.current?.select();}}>{t('全选文本')}</button><button type="button" onClick={onClose}>{t('关闭')}</button></div>
   <p className="hint">{t('可使用 Ctrl/Cmd+C，或手机的原生复制操作。')}</p>
   {!!result.warnings[format].length&&<ul className="selection-copy-warnings">{result.warnings[format].map(key=><li key={key}>{t(warnings[key])}</li>)}</ul>}
   {format==='latex'&&<p className="hint">{t('LaTeX 为片段；链接使用的 href 命令需要目标文档支持 hyperref。')}</p>}
  </div>
 </dialog>;
}

export default function SelectionCopyToolbar({snapshot,onDismiss}:{snapshot:CopySnapshot;onDismiss:()=>void}){
 useLanguage();const toolbar=useRef<HTMLDivElement>(null),[position,setPosition]=useState<{left:number;top:number}|null>(null),[notice,setNotice]=useState(''),[result,setResult]=useState<CopyResult|null>(null),[preview,setPreview]=useState(false),[manual,setManual]=useState(false),[format,setFormat]=useState<CopyFormat>('markdown');
 const activeToken=useRef(snapshot.token),mounted=useRef(true);activeToken.current=snapshot.token;
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 useEffect(()=>{setResult(null);setNotice('');},[snapshot.token]);
 useLayoutEffect(()=>{
  let frame=0;
  function update(){
   frame=0;if(!snapshot.range.startContainer.isConnected||!snapshot.range.endContainer.isConnected){onDismiss();return;}
   const box=toolbar.current;if(!box)return;const rects=Array.from(snapshot.range.getClientRects()),rect=rects.find(r=>r.bottom>0&&r.top<innerHeight)||snapshot.range.getBoundingClientRect();
   if(!rect.width&&!rect.height){if(!preview)onDismiss();return;}
   const width=box.offsetWidth,height=box.offsetHeight,mobile=window.matchMedia('(max-width:760px)').matches;
   setPosition({left:mobile?Math.max(12,(innerWidth-width)/2):Math.max(12,Math.min(rect.left+(rect.width-width)/2,innerWidth-width-12)),top:mobile?Math.max(12,(window.visualViewport?.height||innerHeight)-height-16):Math.max(12,Math.min(rect.top>height+16?rect.top-height-8:rect.bottom+8,innerHeight-height-12))});
  }
  const schedule=()=>{if(!frame)frame=requestAnimationFrame(update);};update();window.addEventListener('scroll',schedule,true);window.addEventListener('resize',schedule);window.visualViewport?.addEventListener('resize',schedule);
  return()=>{cancelAnimationFrame(frame);window.removeEventListener('scroll',schedule,true);window.removeEventListener('resize',schedule);window.visualViewport?.removeEventListener('resize',schedule);};
 },[snapshot.token,notice,preview,onDismiss]);
 async function copy(key:CopyFormat){
  const token=snapshot.token;
  setFormat(key);setNotice('');
  try{
   const value=result||captureSelection(snapshot.range,snapshot.scope);setResult(value);
   if(!value.values[key]){setNotice('选区中没有可复制的正文内容。');return;}
   if(navigator.clipboard?.writeText){
    try{await navigator.clipboard.writeText(value.values[key]);if(activeToken.current!==token||!mounted.current)return;restore(snapshot);setNotice(value.warnings[key].length?'已复制，部分结构已简化。':'已复制');return;}catch{/* HTTP and permission failures use the explicit manual preview. */}
   }
   if(activeToken.current!==token||!mounted.current)return;
   setManual(true);setPreview(true);
  }catch{setNotice('选区已变化，请重新选择。');}
 }
 function closePreview(){setPreview(false);requestAnimationFrame(()=>restore(snapshot));}
 return createPortal(<>
  <div ref={toolbar} className="selection-copy-toolbar" data-copy-ui role="toolbar" aria-label={t('选区复制')} style={{left:position?.left,top:position?.top,visibility:position&&!preview?'visible':'hidden'}} onPointerDown={event=>event.preventDefault()} onKeyDown={event=>{if(event.key==='Escape')onDismiss();}}>
   {formats.map(key=><button type="button" key={key} onClick={()=>void copy(key)}>{t(labels[key])}</button>)}
   {notice&&<div className="selection-copy-notice" role="status">{t(notice)}{result&&<button type="button" className="text-button" onClick={()=>{setManual(false);setPreview(true);}}>{t('查看格式文本')}</button>}{result&&result.warnings[format].map(key=><p key={key}>{t(warnings[key])}</p>)}</div>}
  </div>
  {preview&&result&&<Preview result={result} format={format} onFormat={setFormat} onClose={closePreview} manual={manual}/>}
 </>,document.body);
}
