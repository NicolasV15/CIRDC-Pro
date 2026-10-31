import React,{useEffect,useState} from 'react';
import {t,locale} from './i18n';
import {authorSearchHref,authorProfileHref,ieeeAuthorHref} from './authorLinks';

type Fetcher=(path:string)=>Promise<any>;
const states:Record<string,string>={complete:'已完成',no_data:'来源未提供',not_returned:'本次未返回',blocked:'访问受限',failed:'提取失败',hidden:'来源已隐藏'};
const fmt=(value:unknown)=>value===null||value===undefined?'—':Number(value).toLocaleString(locale());
const time=(value:string|null)=>value?new Date(value).toLocaleString(locale()):'—';

export function AuthorProfile({source,authorId,fetcher}:{source:string;authorId:string;fetcher:Fetcher}){
 const [author,setAuthor]=useState<any>(null),[local,setLocal]=useState<any>(null),[busy,setBusy]=useState(true),[error,setError]=useState('');
 useEffect(()=>{let active=true;setBusy(true);setError('');setAuthor(null);setLocal(null);
  const path=encodeURIComponent(source)+'/'+encodeURIComponent(authorId);
  void fetcher('/api/author-profiles/'+path).then(value=>{if(active)setAuthor(value.author)}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setBusy(false)});
  void fetcher('/api/authors/'+path).then(value=>{if(active)setLocal(value.author)}).catch(()=>{});
  return()=>{active=false};
 },[source,authorId,fetcher]);
 const p=author?.profile||{},hidden=p.is_hidden===true;
 const name=(!hidden&&p.preferred_name)||local?.display_name||authorId;
 const papers=authorSearchHref({source,author_id:authorId,name,ordinal:0})||'/';
 const ieee=ieeeAuthorHref({source,author_id:authorId});
 function empty(field:string){return t(states[author?.field_states?.[field]]||'作者资料尚未提取')}
 return <main className="workspace author-profile"><a className="back author-profile-link" href={papers}>← {t('返回作者论文检索')}</a>
  <section className="panel"><span className="eyebrow">{t('作者资料')}</span><h1>{name}</h1><p className="muted">IEEE ID: {authorId}</p>
   <div className="actions"><a className="author-profile-link" href={papers}>{t('查看本库论文')}</a>{ieee&&<a className="author-profile-link" href={ieee} target="_blank" rel="noopener noreferrer">{t('查看 IEEE Xplore 作者原始链接')} ↗</a>}</div>
   {busy&&<p role="status">{t('正在读取作者资料…')}</p>}{error&&<p className="error" role="alert">{t(error)}</p>}
   {!busy&&!error&&!author&&<p className="hint">{t('作者资料尚未提取。本站仅展示已导入资料，不会自动抓取。')}</p>}
   {author&&<><p className="hint">{t('最近状态：')}{t(states[author.fetch_state]||author.fetch_state)}{t(' · 最近尝试：')}{time(author.last_attempt_at)}</p>
    {['blocked','failed'].includes(author.fetch_state)&&<p className="error">{(author.fetched_at?t('最近一次提取未完成，以下为上次成功资料。'):t('尚无成功提取的资料。'))}{author.last_error_code&&<code> {author.last_error_code}</code>}</p>}
    <p className="muted">{t('资料采集时间：')}{time(author.fetched_at)}</p>
    {hidden?<p className="hint">{t('IEEE 当前已隐藏此作者资料，本站不展示旧的详细资料。')}</p>:<>
     <div className="author-profile-metrics"><div><span>{t('本库论文数')}</span><strong>{fmt(local?.papers)}</strong></div><div><span>{t('IEEE 论文数')}</span><strong>{fmt(p.ieee_article_count)}</strong></div><div><span>{t('IEEE 引用次数')}</span><strong>{fmt(p.ieee_citation_count)}</strong></div></div>
     <p className="hint">{t('IEEE 指标来自采集时的作者页面，与本库收录数量可能不同。')}</p>
     <dl className="author-profile-fields"><div><dt>ORCID</dt><dd>{/^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9X]{4}$/.test(p.orcid||'')?<a href={'https://orcid.org/'+p.orcid} target="_blank" rel="noopener noreferrer">{p.orcid}</a>:p.orcid||empty('orcid')}</dd></div>
      <div><dt>{t('当前机构（IEEE 来源）')}</dt><dd>{p.current_affiliations?.length?<ul>{p.current_affiliations.map((value:string,i:number)=><li key={i}>{value}</li>)}</ul>:empty('current_affiliations')}</dd></div>
      <div><dt>{t('首次 / 最近发表年份')}</dt><dd>{p.first_published_year||'—'} / {p.last_published_year||'—'}</dd></div>
     </dl><h2>{t('作者简介')}</h2>{p.bio_paragraphs?.length?p.bio_paragraphs.map((value:string,i:number)=><p className="author-biography" key={i}>{value}</p>):<p className="muted">{empty('bio_paragraphs')}</p>}
     <details><summary>{t('研究主题')} · {p.topics?.length||0}</summary>{p.topics?.length?<ul>{p.topics.map((item:any,i:number)=><li key={i}>{item.name} <span className="muted">({fmt(item.num_records)})</span></li>)}</ul>:<p>{empty('topics')}</p>}</details>
     <details><summary>{t('合作者（本次返回）')} · {p.coauthors?.length||0}</summary><p className="hint">{t('此列表仅保留来源返回的关联信息，不代表已建立这些作者的资料档案。')}</p>{p.coauthors?.length?<ul className="author-coauthors">{p.coauthors.map((item:any,i:number)=>{const href=item.author_id?authorProfileHref({source:'ieee',author_id:item.author_id}):undefined;return <li key={i}>{href?<a className="author-profile-link" href={href}>{item.preferred_name||item.author_id}</a>:item.preferred_name||'—'}{item.author_id&&<small> IEEE ID: {item.author_id}</small>}</li>})}</ul>:<p>{empty('coauthors')}</p>}</details>
     <details><summary>{t('发表年份分布')}</summary>{p.publication_years?.length?<div className="table-scroll"><table><thead><tr><th>{t('年份')}</th><th>{t('IEEE 论文数')}</th></tr></thead><tbody>{p.publication_years.map((item:any,i:number)=><tr key={i}><td>{item.name}</td><td>{fmt(item.num_records)}</td></tr>)}</tbody></table></div>:<p>{empty('publication_years')}</p>}</details>
    </>}
   </>}
  </section>
 </main>;
}
