import {useEffect,useRef,useState} from 'react';
import {buildCitations,type CitationStyle} from './citations';
import {loadPapers,type LoadedPaper,type BatchFailure} from './paperBatch';
import {t,useLanguage} from './i18n';
import ScientificTitle from './ScientificTitle';

export default function CitationDialog({numbers,fetcher,onClose}:{numbers:string[];fetcher:(path:string)=>Promise<any>;onClose:()=>void}) {
 const language=useLanguage();
 const dialog=useRef<HTMLDialogElement>(null),close=useRef<HTMLButtonElement>(null),output=useRef<HTMLTextAreaElement>(null);
 const [records,setRecords]=useState<LoadedPaper[]>([]),[failures,setFailures]=useState<BatchFailure[]>([]),[progress,setProgress]=useState(0),[loading,setLoading]=useState(true),[attempt,setAttempt]=useState(0),[format,setFormat]=useState<CitationStyle>('bibtex'),[notice,setNotice]=useState('');
 useEffect(()=>{
  const box=dialog.current;if(!box)return;const opener=document.activeElement instanceof HTMLElement?document.activeElement:null,overflow=document.body.style.overflow;
  box.showModal();document.body.style.overflow='hidden';close.current?.focus();
  return()=>{if(box.open)box.close();document.body.style.overflow=overflow;if(opener?.isConnected)opener.focus();};
 },[]);
 const key=numbers.join(',');
 useEffect(()=>{
  let active=true;setRecords([]);setFailures([]);setProgress(0);setLoading(true);
  void loadPapers(numbers,fetcher,done=>{if(active)setProgress(done);},()=>!active).then(value=>{if(active){setRecords(value.items);setFailures(value.failures);setLoading(false);}});
  return()=>{active=false;};
 },[key,attempt,fetcher]);
 const citations=records.map(item=>({number:item.number,citation:buildCitations(item.paper.record,item.number)}));
 const value=citations.map((item,index)=>(numbers.length>1&&format!=='bibtex'?'['+(index+1)+'] ':'')+item.citation.values[format]).join('\n\n');
 const record=records[0]?.paper.record,number=numbers[0]||'';
 async function copy(){
  setNotice('');
  if(window.isSecureContext&&navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(value);setNotice('引用已复制');return;}catch{/* Direct HTTP and browser permissions use the selected text below. */}}
  output.current?.focus();output.current?.select();
  try{if(document.execCommand('copy')){setNotice('引用已复制');return;}}catch{/* Keep the text selected for manual copying. */}
  setNotice('无法自动复制，已选中文本，请手动复制。');
 }
 function download(){
  const url=URL.createObjectURL(new Blob([value+'\n'],{type:format==='bibtex'?'application/x-bibtex;charset=utf-8':'text/plain;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download=(numbers.length>1?'cirdc-references':'ieee'+number)+(format==='bibtex'?'.bib':'.txt');document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 const missingNames:Record<string,string>={title:'标题',authors:'作者',publication:'刊会名称',year:'出版年份',online_date:'在线发表日期'};
 return <dialog ref={dialog} className="citation-dialog" aria-labelledby="citation-dialog-title" onCancel={event=>{event.preventDefault();onClose();}} onClick={event=>{if(event.target!==event.currentTarget)return;const rect=event.currentTarget.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)onClose();}}>
  <header className="citation-header"><div><h2 id="citation-dialog-title">{t('引用格式')}</h2><p>{numbers.length>1?t('已选择 {n} 篇，按选择顺序导出。',{n:numbers.length}):<ScientificTitle value={record?.articleTitle} fallback={t('论文编号')+' '+number}/>}</p></div><button ref={close} type="button" className="citation-close" aria-label={t('关闭引用格式')} onClick={onClose}>×</button></header>
  <div className="citation-body">{loading&&<p role="status">{t('正在读取引用元数据：{done} / {total}',{done:progress,total:numbers.length})}</p>}
  {!loading&&failures.length>0&&<div className="citation-warning" role="alert"><p>{t('有 {n} 篇读取失败；本次导出包含 {done} 篇。',{n:failures.length,done:records.length})}</p><ul>{failures.map(item=><li key={item.number}>{item.number} · {t(item.message)}</li>)}</ul><button type="button" onClick={()=>setAttempt(attempt+1)}>{t('重新获取引用')}</button></div>}
  {!loading&&citations.length>0&&<><div className="citation-formats" role="group" aria-label={t('选择引用格式')}>{([['bibtex','BibTeX'],['ieee','IEEE'],['gbt2025','GB/T 7714-2025']] as const).map(([key,label])=><button type="button" key={key} aria-pressed={format===key} onClick={()=>{setFormat(key);setNotice('');}}>{label}</button>)}</div>
   <label className="citation-output-label">{t('引用文本')}<textarea ref={output} readOnly spellCheck={false} value={value} aria-label={t('引用文本')}/></label>
   <div className="citation-actions"><button type="button" className="primary" onClick={()=>void copy()}>{t('复制引用')}</button><button type="button" onClick={download}>{format==='bibtex'?t('下载 .bib'):t('下载 .txt')}</button></div><p className="citation-notice" role="status" aria-live="polite">{t(notice)}</p>
   {citations.some(item=>item.citation.missing.length>0)&&<div className="citation-warning">{citations.filter(item=>item.citation.missing.length).map(item=><p key={item.number}>{numbers.length>1?item.number+' · ':''}{t('现有元数据缺少：')}{item.citation.missing.map(key=>t(missingNames[key])).join(language==='zh'?'、':', ')}{t('；引用已省略缺失字段。')}</p>)}</div>}
   {citations.some(item=>item.citation.earlyAccess)&&<p className="hint">{t('Early Access 保留出版状态，省略临时卷期和页码。')}</p>}
   {citations.some(item=>item.citation.unstructuredAuthors)&&<p className="hint">{t('部分作者只有完整姓名，已按原文保留。')}</p>}
   <p className="hint">{t('依据现有元数据生成，投稿前请按目标刊物要求核对。')}{format!=='bibtex'&&' '+(numbers.length>1?t('已按选中顺序编号。'):t('未附文献序号，请按正文引用顺序编号。'))}</p>
  </>}
  </div>
 </dialog>;
}
