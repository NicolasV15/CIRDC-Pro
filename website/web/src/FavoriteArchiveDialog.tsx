import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import {locale,t,useLanguage} from './i18n';
import Icon from './Icon';
import {defaultFilenameTemplate,downloadFilenames,filenameKey,filenameTemplateError} from './downloadNames';
import type {FavoriteRow} from './FavoritesPage';

const reasons:Record<string,string>={missing:'没有已缓存的 PDF',restricted:'访问受限',not_packaged:'离线包未包含此文件',unreadable:'文件无法读取',paper_missing:'论文暂不可读取'};
type Result={files:{id:number;filename:string}[];skipped:{id:number;reason:string}[];archive:{id:string;href:string;expires:number}|null};
function storedTemplate(){try{return localStorage.getItem(filenameKey)||defaultFilenameTemplate;}catch{return defaultFilenameTemplate;}}

/** One ZIP of cached PDFs across sources and arXiv versions; missing files are listed, never fetched. */
export default function FavoriteArchiveDialog({rows,onClose}:{rows:FavoriteRow[];onClose:()=>void}){
 useLanguage();
 const dialog=useRef<HTMLDialogElement>(null),close=useRef<HTMLButtonElement>(null);
 const [template,setTemplate]=useState(storedTemplate),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<Result|null>(null),[discarded,setDiscarded]=useState(false);
 const templateError=filenameTemplateError(template),titles=new Map(rows.map(row=>[row.id,row]));
 useEffect(()=>{const box=dialog.current;if(!box)return;const opener=document.activeElement instanceof HTMLElement?document.activeElement:null;box.showModal();close.current?.focus();return()=>{if(box.open)box.close();if(opener?.isConnected)opener.focus({preventScroll:true});};},[]);
 async function prepare(){
  setBusy(true);setError('');setDiscarded(false);
  try{
   try{localStorage.setItem(filenameKey,template);}catch{/* The template still applies to this package. */}
   const names=downloadFilenames(template,rows.map(row=>({number:String(row.id),display_number:row.identifier+(row.source==='arxiv'?'v'+row.version:''),title:row.title,year:row.year??''})));
   setResult(await api('/api/me/archives','POST',{ids:rows.map(row=>row.id),filenames:Object.fromEntries(names.map(name=>[name.number,name.filename]))}));
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 async function discard(){if(!result?.archive)return;try{await api(result.archive.href,'DELETE');setDiscarded(true);}catch(e){setError((e as Error).message);}}
 const skipped=result?.skipped||[];
 return <dialog ref={dialog} className="citation-dialog favorite-archive-dialog" aria-labelledby="favorite-archive-title" onCancel={e=>{e.preventDefault();onClose();}}>
  <header className="citation-header"><div><h2 id="favorite-archive-title">{t('下载收藏的 PDF')}</h2><p>{t('已选 {n} 篇（仅含已有 PDF）',{n:rows.length})}</p></div><button type="button" ref={close} className="citation-close" aria-label={t('关闭')} onClick={onClose}><Icon name="close"/></button></header>
  <div className="citation-body">
   {!result&&<form className="favorite-archive-form" onSubmit={e=>{e.preventDefault();void prepare();}}>
    <label>{t('文件名模板')}<input value={template} onChange={e=>setTemplate(e.target.value)} aria-invalid={!!templateError} aria-describedby="favorite-template-hint"/></label>
    <p className="hint" id="favorite-template-hint">{templateError?t(templateError):t('可用字段：{id}、{title}、{year}；arXiv 编号包含版本。')}</p>
    {error&&<p className="error" role="alert">{t(error)}</p>}
    <div className="actions"><button className="primary" disabled={busy||!!templateError} aria-busy={busy||undefined}>{busy?<><span className="spinner" aria-hidden="true"/>{t('正在打包…')}</>:<><Icon name="download"/>{t('准备 ZIP')}</>}</button><button type="button" onClick={onClose}>{t('取消')}</button></div>
   </form>}
   {result&&<div className="favorite-archive-result" role="status">
    {result.archive&&!discarded?<>
     <p><strong>{t('已打包 {n} 个 PDF',{n:result.files.length})}</strong>{skipped.length>0&&t('，{n} 篇未包含',{n:skipped.length})}</p>
     <a className="button primary" href={result.archive.href} download><Icon name="download"/>{t('下载 ZIP')}</a>
     <p className="hint">{t('链接将于 {time} 失效。',{time:new Date(result.archive.expires*1000).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'})})}</p>
     <button type="button" className="text-button" onClick={()=>void discard()}><Icon name="trash"/>{t('删除服务器上的压缩包')}</button>
    </>:discarded?<p>{t('压缩包已删除。')}</p>:<p><strong>{t('没有可打包的 PDF。')}</strong></p>}
    {skipped.length>0&&<details className="favorite-archive-skipped" open={!result.archive}><summary>{t('未包含 {n} 篇',{n:skipped.length})}</summary><ul>{skipped.map(item=><li key={item.id}><span>{titles.get(item.id)?.title||titles.get(item.id)?.identifier}</span><span className="badge">{t(reasons[item.reason]||item.reason)}</span></li>)}</ul></details>}
    {error&&<p className="error" role="alert">{t(error)}</p>}
    <div className="actions"><button type="button" onClick={onClose}>{t('关闭')}</button></div>
   </div>}
  </div>
 </dialog>;
}
