import React,{useEffect,useRef,useState} from 'react';
import {locale,t} from './i18n';
import {authorSearchHref,authorProfileHref,ieeeAuthorHref,otherAuthorIdentities,type AuthorReference,type AuthorIdentity} from './authorLinks';

type Fetcher=(path:string)=>Promise<any>;
const format=(value:number)=>Number(value).toLocaleString(locale());
function IeeeSourceLink({author,name=false}:{author:{source:string;author_id:string|null;name?:string;display_name?:string};name?:boolean}){
 const href=ieeeAuthorHref(author);
 if(!href)return null;
 return <a className="ieee-author-source" href={href} target="_blank" rel="noopener noreferrer" title={t('在新标签页查看 IEEE Xplore 作者页面')} data-ieee-author-id={author.author_id}>{name?(author.name||author.display_name||author.author_id):t('查看 IEEE Xplore 作者原始链接')} <span aria-hidden="true">↗</span></a>;
}
function AuthorEntry({author,detail=false,preview=false}:{author:AuthorReference;detail?:boolean;preview?:boolean}){
 const href=authorSearchHref(author),name=author.name||t('未提供署名');
 const content=<><span>{name}</span>{detail&&<small>{author.author_id?t('IEEE ID: ')+author.author_id:t('未提供作者 ID')}</small>}</>;
 const className=detail?'author-reference':preview?'detail-author-preview-link':'paper-author-link';
 return href?<a className={className} data-author-id={author.author_id} href={href} title={t('查看该作者 ID 的论文：')+author.author_id}>{content}</a>:<span className={detail?'author-reference unidentified':preview?'detail-author-preview-unidentified':'paper-author-unidentified'} title={t('未提供作者 ID')}>{content}</span>;
}
function DetailAuthorLinks({references}:{references:AuthorReference[]}){
 const [expanded,setExpanded]=useState(false),listId=React.useId();
 const visible=expanded?references:references.slice(0,3),seen=new Set<string>();
 const sources=expanded?references.filter(author=>{const key=JSON.stringify([author.source,author.author_id]);if(!ieeeAuthorHref(author)||seen.has(key))return false;seen.add(key);return true;}):[];
 return <section className={'detail-author-disclosure'+(expanded?' is-expanded':'')} aria-label={t('论文作者（按原顺序）')}>
  <div id={listId} className={expanded?'detail-author-identities detail-authors-expanded':'detail-author-preview'}>{visible.map(author=><AuthorEntry key={author.ordinal} author={author} detail={expanded} preview={!expanded}/>)}</div>
  <button type="button" className="detail-authors-toggle" aria-expanded={expanded} aria-controls={listId} onClick={()=>setExpanded(value=>!value)}>{expanded?t('收起作者列表'):references.length>3?t('展开全部作者（共 {n} 位）',{n:references.length}):t('展开作者详情（共 {n} 位）',{n:references.length})}</button>
  {expanded&&sources.length>0&&<details className="ieee-author-source-list"><summary>{t('IEEE Xplore 作者原始链接')}</summary><div className="ieee-author-source-options">{sources.map(author=><IeeeSourceLink key={author.ordinal} author={author} name/>)}</div></details>}
 </section>;
}
export function AuthorLinks({references,fallback='',detail=false}:{references?:AuthorReference[];fallback?:string;detail?:boolean}){
 if(!references?.length)return fallback?.trim()?<p className={detail?'muted':'authors'}>{fallback}</p>:null;
 if(detail)return <DetailAuthorLinks key={JSON.stringify(references.map(author=>[author.source,author.author_id,author.name,author.ordinal]))} references={references}/>;
 return <div className="paper-author-links" aria-label={t('论文作者（按原顺序）')}>{references.map(author=><AuthorEntry key={author.ordinal} author={author}/>)}</div>;
}
function IdentityContent({author}:{author:AuthorIdentity}){
 return <><strong>{author.display_name||t('未提供署名')}</strong><span>{t('IEEE ID: ')}{author.author_id}</span><small>{t('库内 ')}{format(author.papers)}{t(' 篇 · ')}{author.first_year||'—'}–{author.last_year||'—'}</small>{author.name_variants.length>1&&<small>{t('署名变体：')}{author.name_variants.slice(0,3).join(' / ')}</small>}</>;
}
export function AuthorSearch({query,authorId,source='ieee',fetcher,onSelect,onUnknown}:{query:string;authorId:string;source?:string;fetcher:Fetcher;onSelect:(author:AuthorIdentity)=>void;onUnknown:()=>void}){
 const [expanded,setExpanded]=useState(!authorId),[selected,setSelected]=useState<AuthorIdentity|null>(null),[selectedBusy,setSelectedBusy]=useState(false),[selectedError,setSelectedError]=useState('');
 const [matches,setMatches]=useState<AuthorIdentity[]>([]),[more,setMore]=useState<string|null>(null),[unknown,setUnknown]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(''),[index,setIndex]=useState<any>();
 const request=useRef(0),candidatesId=React.useId();
 const searchQuery=/^\d+$/.test(query.trim())?(selected?.display_name||query):query;
 useEffect(()=>{setExpanded(!authorId);setSelected(null);setSelectedError('');if(!authorId){setSelectedBusy(false);return}let active=true;setSelectedBusy(true);
  void fetcher('/api/authors/'+encodeURIComponent(source||'ieee')+'/'+encodeURIComponent(authorId)).then(value=>{if(active)setSelected(value.author)}).catch(e=>{if(active)setSelectedError(e.message)}).finally(()=>{if(active)setSelectedBusy(false)});
  return()=>{active=false};
 },[authorId,source,fetcher]);
 async function load(cursor?:string){const current=++request.current;setBusy(true);setError('');try{
  const params=new URLSearchParams({q:searchQuery,limit:'20'});if(cursor)params.set('cursor',cursor);
  const value=await fetcher('/api/authors?'+params);if(current!==request.current)return;
  setMatches(old=>cursor?[...old,...value.items]:value.items);setMore(value.next_cursor);setUnknown(value.unidentified_papers);setIndex(value.index);
 }catch(e){if(current===request.current)setError((e as Error).message)}finally{if(current===request.current)setBusy(false)}}
 useEffect(()=>{++request.current;setMatches([]);setMore(null);setUnknown(0);setIndex(undefined);setError('');setBusy(false);if(expanded&&searchQuery.trim())void load();return()=>{++request.current}},[expanded,searchQuery]);
 const pinned=selected?.author_id===authorId&&selected.source===(source||'ieee')?selected:null;
 const candidates=otherAuthorIdentities(matches,source||'ieee',authorId);
 function select(author:AuthorIdentity){setExpanded(false);onSelect(author)}
 return <section className="author-matches panel" aria-label={t('作者身份分类')}><div className="section-heading"><h2>{t('作者身份 · 按 IEEE ID 区分')}</h2>{(selectedBusy||busy)&&<span className="muted">{t('查找中…')}</span>}</div>
  {authorId&&<div className="pinned-author" aria-label={t('已选作者')}><div className="author-match selected" data-author-id={authorId}>{pinned?<IdentityContent author={pinned}/>:<><strong>{t('已选作者')}</strong><span>{t('IEEE ID: ')}{authorId}</span></>}</div><a className="author-profile-link" href={authorProfileHref({source:source||'ieee',author_id:authorId})} target="_blank" rel="noopener noreferrer">{t('作者资料')} ↗</a><IeeeSourceLink author={{source:source||'ieee',author_id:authorId}}/><p className="hint">{t('当前按此作者 ID 检索论文，其他同名作者默认收起。')}</p>{selectedError&&<p className="error" role="alert">{t(selectedError)}</p>}<button type="button" className="author-candidates-toggle" aria-expanded={expanded} aria-controls={candidatesId} onClick={()=>setExpanded(value=>!value)}>{expanded?t('收起作者候选列表'):t('展开其他同名作者')}</button></div>}
  {expanded&&<div id={candidatesId} className="author-candidates"><p className="muted">{t('同名但 ID 不同的作者分别列出。选择一个身份，查看该 ID 的论文；同一 ID 的署名变体会一并关联。')}</p>{index&&index.authors_phase!=='ready'&&<p className="author-index-note">{t('作者索引补建中：已检查 ')}{format(index.authors_papers_seen||0)}{t(' 篇，当前结果可能不完整。')}</p>}{error&&<p className="error" role="alert">{t(error)}</p>}
   <div className="author-match-grid">{candidates.map(author=><div className="author-candidate-card" key={author.identity_key}><button type="button" className="author-match" data-author-id={author.author_id} onClick={()=>select(author)}><IdentityContent author={author}/></button><IeeeSourceLink author={author}/></div>)}</div>
   {!busy&&!candidates.length&&!error&&<p className="muted">{authorId?t('当前索引中没有其他匹配的作者身份。'):t('当前索引中没有匹配的已识别作者。')}</p>}{more&&<button type="button" disabled={busy} onClick={()=>void load(more)}>{t('更多作者身份')}</button>}{unknown>0&&<div className="unidentified-authors"><p>{t('另有 ')}{format(unknown)}{t(' 篇论文的匹配署名缺少作者 ID，暂不归并为同一个人。')}</p><button type="button" onClick={onUnknown}>{t('查看缺少 ID 的署名记录')}</button></div>}
  </div>}
 </section>;
}
