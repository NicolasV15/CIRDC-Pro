import {useEffect,useRef,useState} from 'react';
import {t,useLanguage} from './i18n';
import {loadPapers,type LoadedPaper,type BatchFailure,type SelectedPaper} from './paperBatch';
import {defaultFilenameTemplate,filenameKey,filenameFields,templateHas,toggleFilenameField,filenameTemplateError,downloadFilenames,type FilenameField} from './downloadNames';
import {readPdfHead,checkDownloads,downloadGroups,safeResourceHref as safeHref,fileStatusLabels,type FileCheck,type FileStatus,type DownloadGroup} from './downloadAvailability';
type Prepared={ready:number;total_bytes:number;download_href:string|null;skipped:{number:string;code:string}[]};
export default function BatchDownloadDialog({selected,fetcher,onClose}:{selected:SelectedPaper[];fetcher:(path:string,method?:string,data?:unknown)=>Promise<any>;onClose:()=>void}){
 useLanguage();const dialog=useRef<HTMLDialogElement>(null),close=useRef<HTMLButtonElement>(null);
 const [template,setTemplate]=useState(()=>{try{return localStorage.getItem(filenameKey)??defaultFilenameTemplate;}catch{return defaultFilenameTemplate;}}),[items,setItems]=useState<LoadedPaper[]>([]),[failures,setFailures]=useState<BatchFailure[]>([]),[loading,setLoading]=useState(true),[progress,setProgress]=useState(0),[attempt,setAttempt]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(''),[prepared,setPrepared]=useState<Prepared>(),[checks,setChecks]=useState<FileCheck[]>([]),[checking,setChecking]=useState(false),[checked,setChecked]=useState(0);
 useEffect(()=>{const box=dialog.current;if(!box)return;const opener=document.activeElement instanceof HTMLElement?document.activeElement:null,overflow=document.body.style.overflow;box.showModal();document.body.style.overflow='hidden';close.current?.focus();return()=>{if(box.open)box.close();document.body.style.overflow=overflow;if(opener?.isConnected)opener.focus();};},[]);
 const key=selected.map(p=>p.number).join(',');
 useEffect(()=>{
  let active=true;const controller=new AbortController();setLoading(true);setPrepared(undefined);setItems([]);setFailures([]);setChecks([]);setError('');setProgress(0);setChecked(0);setChecking(false);
  void loadPapers(selected.map(p=>p.number),fetcher,done=>{if(active)setProgress(done);},()=>!active).then(async value=>{
   if(!active)return;setItems(value.items);setFailures(value.failures);setLoading(false);setChecking(true);
   const verified=await checkDownloads(value.items,path=>readPdfHead(path,controller.signal),done=>{if(active)setChecked(done);},()=>!active);
   if(active){setChecks(verified);setChecking(false);}
  });
  return()=>{active=false;controller.abort();};
 },[key,attempt,fetcher]);
 useEffect(()=>{try{localStorage.setItem(filenameKey,template);}catch{/* Naming remains usable with browser storage disabled. */}setPrepared(undefined);},[template]);
 const templateError=filenameTemplateError(template);
 const papers=items.map(item=>({number:item.number,title:item.paper.record.articleTitle||'',year:item.paper.record.publicationYear,kind:item.paper.record.articleContentType,venue:String(item.paper.record.publicationNumber||''),venue_series:item.paper.venue_series,publication:item.paper.record.publicationTitle}));
 const names=templateError?[]:downloadFilenames(template,papers);
 const groups=downloadGroups(names,checks),available=checks.filter(check=>check.status==='ready');
 const labels:Record<FilenameField,string>={id:'论文 ID',title:'标题',year:'年份',abbr:'刊会缩写'};
 const reasons:Record<string,string>={not_available:'暂无已关联 PDF',file_missing:'关联文件已不存在',file_unavailable:'关联文件暂不可读取'};
 async function prepare(group:DownloadGroup){
  if(!safeHref(group.endpoint)||!group.ready||busy)return;
  setBusy(true);setError('');setPrepared(undefined);
  try{
   const value:Prepared=await fetcher(group.endpoint,'POST',{items:group.items});
   setPrepared(value);
   // The archive endpoint checks again, so a deleted or changed file also changes the preview.
   const skipped=new Map(value.skipped.map(item=>[item.number,item.code]));
   setChecks(old=>old.map(check=>{const code=skipped.get(check.number);return code?{...check,status:code==='not_available'?'not_available':code==='file_missing'?'file_missing':'file_unavailable' as FileStatus}:check;}));
   const href=safeHref(value.download_href);
   if(value.ready>0&&href){const link=document.createElement('a');link.href=href;link.download='';document.body.append(link);link.click();link.remove();}
   else if(value.ready>0)setError('下载文件核对失败，请重新读取下载信息。');
  }
  catch(reason){setError(reason instanceof Error?reason.message:'操作暂时无法完成，请稍后重试。');}
  finally{setBusy(false);}
 }
 return <dialog ref={dialog} className="citation-dialog batch-download-dialog" aria-labelledby="batch-download-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}} onClick={e=>{if(e.target!==e.currentTarget||busy)return;const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}>
  <header className="citation-header"><div><h2 id="batch-download-title">{t('批量下载 PDF')}</h2><p>{t('下载已有 PDF 的 ZIP 副本，服务器上的原文件保持不变。')}</p></div><button ref={close} type="button" className="citation-close" aria-label={t('关闭下载设置')} disabled={busy} onClick={onClose}>×</button></header>
  <div className="citation-body"><fieldset className="filename-fields" disabled={busy}><legend>{t('选择文件名信息')}</legend>{filenameFields.map(field=><label key={field}><input type="checkbox" checked={templateHas(template,field)} onChange={e=>setTemplate(toggleFilenameField(template,field,e.target.checked))}/>{t(labels[field])}<code>{'{'+field+'}'}</code></label>)}</fieldset>
   <label className="filename-template-label">{t('文件名模板')}<input value={template} onChange={e=>setTemplate(e.target.value)} maxLength={300} disabled={busy} spellCheck={false} aria-label={t('文件名模板')}/></label><p className="hint">{t('可直接修改字段顺序和分隔符，系统会自动补上 .pdf。')}</p><div className="filename-presets"><button type="button" disabled={busy} onClick={()=>setTemplate(defaultFilenameTemplate)}>{t('年份_缩写_ID_标题')}</button><button type="button" disabled={busy} onClick={()=>setTemplate('{id}_{title}')}>{t('ID_标题')}</button><button type="button" disabled={busy} onClick={()=>setTemplate('{title}')}>{t('仅标题')}</button></div>
   <p className="hint">{t('非精选刊会不加入缩写；空字段及多余分隔符自动省略，重名时追加论文 ID，过长名称会截短。')}</p>
   {templateError&&<p className="error" role="alert">{t(templateError)}</p>}
   {loading?<p role="status">{t('正在读取下载信息：{done} / {total}',{done:progress,total:selected.length})}</p>:checking?<p role="status">{t('正在核对 PDF 文件：{done} / {total}',{done:checked,total:items.length})}</p>:<><div className="download-preview-heading"><h3>{t('下载预览')}</h3><span>{t('可下载 {ready} / 已选 {total} 篇',{ready:available.length,total:selected.length})}</span></div><ul className="download-preview-list">{items.map(item=>{const file=names.find(name=>name.number===item.number),check=checks.find(check=>check.number===item.number),status=check?.status||'unverified';return <li key={item.number} data-status={status}><code>{item.number}</code><span className="download-preview-name">{file?.filename||'—'}</span><span className="download-preview-status"><span className={status==='ready'?'download-ready':'download-missing'}>{t(fileStatusLabels[status])}</span>{status==='ready'&&check?.resource&&<a href={(safeHref(check.resource.reader_href)||safeHref(check.resource.href))!} target="_blank" rel="noopener noreferrer">{t('打开 PDF')} ↗</a>}</span></li>;})}</ul>{failures.length>0&&<div className="citation-warning"><p>{t('以下论文元数据读取失败：')}</p>{failures.map(item=><p key={item.number}>{item.number} · {t(item.message)}</p>)}</div>}
   <div className="citation-actions">{groups.map((group,index)=><button key={group.key} type="button" className="primary" disabled={busy||!!templateError} onClick={()=>void prepare(group)}>{busy?t('正在准备下载…'):groups.length===1?t('打包下载 ZIP'):t('下载第 {n} 包（{count} 篇）',{n:index+1,count:group.ready})}</button>)}<button type="button" disabled={busy} onClick={()=>setAttempt(attempt+1)}>{t('重新读取下载信息')}</button></div>{groups.length>1&&<p className="hint">{t('每包最多 100 篇，请分别点击下载。')}</p>}{!available.length&&<p className="hint">{t('所选论文暂无可下载的 PDF，不会自动采集缺失文件。')}</p>}
   </>}
   {error&&<p className="error" role="alert">{t(error)}</p>}{prepared&&<div className="download-prepared" role="status"><p>{t(prepared.ready>0&&safeHref(prepared.download_href)?'下载已启动，完成状态以浏览器为准。':'所选文件当前不可下载，请重新读取下载信息。')}</p><p>{t('已准备 {n} 个文件',{n:prepared.ready})}{prepared.total_bytes>0?' · '+(prepared.total_bytes/1024/1024).toFixed(1)+' MiB':''}</p>{prepared.skipped.map(item=><p key={item.number}>{item.number} · {t(reasons[item.code]||'关联文件暂不可读取')}</p>)}</div>}
  </div>
 </dialog>;
}
