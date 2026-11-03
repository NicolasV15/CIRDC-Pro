import {Fragment,useState} from 'react';
import {t,useLanguage} from './i18n';
import {api} from './api';
import {fmt} from './format';
import Icon from './Icon';
import type {FulltextStatus,Highlighted as HighlightedValue,MatchReason,Paper,Passage,QueryInfo} from './types';

const fieldNames:Record<string,string>={title:'标题',authors:'作者',keywords:'关键词',abstract:'摘要',body:'正文'};
const matchNames:Record<string,string>={exact:'原句',approximate:'近似',terms:'词项',phrase:'短语'};

export function Highlighted({value}:{value:HighlightedValue}){
 const parts=[];let cursor=0;
 for(const [start,end] of value.highlights){
  if(start<cursor)continue;
  if(start>cursor)parts.push(<Fragment key={'t'+cursor}>{value.text.slice(cursor,start)}</Fragment>);
  parts.push(<mark className="hit" key={'m'+start}>{value.text.slice(start,end)}</mark>);cursor=end;
 }
 if(cursor<value.text.length)parts.push(<Fragment key="tail">{value.text.slice(cursor)}</Fragment>);
 return <>{parts}</>;
}

export function passageHref(number:string,passage:Pick<Passage,'ordinal'|'version'>,query:string,terms:string){
 return '/papers/'+number+'?'+new URLSearchParams({passage:String(passage.ordinal),...(passage.version?{v:passage.version}:{}),q:query,...(terms==='exact'?{terms}:{})});
}

/** How the query was read, which equivalents were searched and what the full-text scope is. */
export default function SearchInsights({query,fulltext,field,onTerm}:{query?:QueryInfo;fulltext?:FulltextStatus|null;field:string;onTerm:(text:string)=>void}){
 useLanguage();
 const concepts=(query?.groups||[]).filter(group=>group.kind==='concept');
 const related=[...new Set(concepts.flatMap(group=>group.related||[]))];
 const lines=[];
 if(query?.doi)lines.push(<p key="doi"><Icon name="search"/>{t('按 DOI 精确查找：')}<code>{query.doi}</code></p>);
 if(query?.number)lines.push(<p key="number"><Icon name="search"/>{t('按论文编号精确查找：')}<code>{query.number}</code></p>);
 for(const group of concepts){
  const others=group.equivalents||[];
  lines.push(<p key={'c'+group.text}><Icon name="link"/><strong>{group.label||group.text}</strong>{query?.terms==='exact'||!others.length?<span>{t('仅匹配原写法（已关闭别名扩展）')}</span>:<span>{t('同时匹配 {n} 种等价写法：',{n:others.length})}<em>{others.slice(0,4).join(' · ')}{others.length>4?' …':''}</em></span>}</p>);
 }
 if(field==='body'){
  if(!fulltext?.enabled)lines.push(<p key="scope" className="insight-warning"><Icon name="info"/>{t('正文检索尚未启用：站点未建立正文段落索引，因此不会返回正文结果。')}</p>);
  else{
   lines.push(<p key="scope"><Icon name="book"/>{t('正文检索范围：已索引 {n} 篇论文正文',{n:fmt(fulltext.documents)})}{fulltext.pending?t('，{n} 篇正文仍待索引或更新',{n:fmt(fulltext.pending)}):''}{t('。未获取或未索引正文的论文不会出现在正文结果中。')}{fulltext.phase!=='ready'?' '+t('正文目录仍在同步。'):''}</p>);
   if(fulltext.failed)lines.push(<p key="failed" className="insight-warning"><Icon name="info"/>{t('其中 {n} 篇索引失败，{m} 篇已暂停重试。',{n:fmt(fulltext.failed),m:fmt(fulltext.blocked||0)})}</p>);
   if(query?.match)lines.push(<p key="match" className={query.match==='approximate'?'insight-warning':undefined}><Icon name={query.match==='approximate'?'info':'check'}/>{t(query.match==='exact'?'原句精确命中：忽略大小写、标点、空白与换行差异，词序一致。':query.match==='approximate'?'未找到逐字一致的原句。以下为近似匹配：同一段落包含查询中多数主要词，不能视为原句出处。':query.match==='phrase'?'同一段落包含引号内的完整短语。':'同一段落同时包含全部检索词（含已启用的等价写法）。')}</p>);
  }
 }
 if(!lines.length&&!related.length)return null;
 return <section className="search-insights" aria-label={t('检索说明')}>{lines}{related.length>0&&<div className="related-terms"><span>{t('相关概念（不参与匹配）：')}</span>{related.map(term=><button type="button" key={term} className="filter-chip" onClick={()=>onTerm(term)}>{term}</button>)}</div>}</section>;
}

const flagNames:Record<string,string>={exact_title:'标题完全一致',title_phrase:'标题包含完整查询',author_name:'作者姓名一致'};
export function MatchReasons({paper}:{paper:Paper}){
 useLanguage();
 const flags=Object.entries(paper.flags||{}).filter(([key,value])=>value&&(flagNames[key]||key==='exact_identifier'));
 if(!paper.reasons?.length&&!flags.length)return null;
 return <ul className="match-reasons" aria-label={t('匹配原因')}>
  {flags.map(([key,value])=><li key={key} className="match-flag">{key==='exact_identifier'?t(value==='doi'?'DOI 精确匹配':'论文编号精确匹配'):t(flagNames[key])}</li>)}
  {(paper.reasons||[]).map((reason:MatchReason)=>reason.terms.map(term=><li key={reason.field+term.query}><span>{t(fieldNames[reason.field]||reason.field)}</span>{term.matched.length?term.matched.join(' / '):term.query}{term.alias&&<em>{t('（等价写法）')}</em>}</li>))}
 </ul>;
}

export function PassageHits({paper,query,terms,onOpen}:{paper:Paper;query:string;terms:string;onOpen:(number:string,href:string)=>void}){
 useLanguage();
 const [all,setAll]=useState<Passage[]|null>(null),[next,setNext]=useState<number|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const items=all||paper.passages||[],total=paper.passage_total||items.length;
 async function load(offset=0){
  setBusy(true);setError('');
  try{const value=await api('/api/papers/'+encodeURIComponent(paper.number)+'/passages?'+new URLSearchParams({q:query,offset:String(offset),limit:'50',...(terms==='exact'?{terms}:{})}));setAll(old=>offset&&old?[...old,...value.items]:value.items);setNext(value.next_offset);}
  catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 if(!items.length)return null;
 return <div className="passage-hits">
  <ol>{items.map(passage=>{const href=passageHref(paper.number,passage,query,terms);return <li key={passage.ordinal} className={'passage-hit match-'+passage.match}>
   <div className="passage-hit-meta"><span className="passage-section">{passage.section||t('正文')}</span><span className="passage-match">{t(matchNames[passage.match]||passage.match)}</span></div>
   <p className="passage-text"><Highlighted value={passage.excerpt}/></p>
   <a className="passage-open" href={href} onClick={event=>{if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();onOpen(paper.number,href);}}><Icon name="book"/>{t('在正文中定位')}</a>
  </li>;})}</ol>
  {error&&<p className="error" role="alert">{t(error)}</p>}
  {(all?next!==null:total>items.length)&&<button type="button" className="text-button" disabled={busy} onClick={()=>void load(all?next||0:0)}>{busy?t('加载中…'):all?t('加载更多命中'):t('查看本文全部 {n} 处命中',{n:fmt(total)})}</button>}
 </div>;
}
