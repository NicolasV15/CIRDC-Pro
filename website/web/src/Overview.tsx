import type React from 'react';
import {t,locale,localizedText} from './i18n';
import {coverageDisplay} from './resourceCoverage';
import {fmt,time} from './format';
import type {Index,Overview} from './types';

export function OverviewCards({overview,compact=false}:{overview?:Overview;compact?:boolean}){
 if(!overview)return null;
 const n=(kind:string)=>overview.venues.find(v=>v.kind===kind)?.n||0;
 const metrics=overview.resource_coverage?.length?overview.resource_coverage:[undefined];
 const cells:{label:string;value:string;hint:string;tooltip?:string;coverage?:boolean}[]=[{label:t('论文记录'),value:fmt(overview.papers),hint:t('数据库中已有记录')},{label:t('期刊'),value:fmt(n('Journals')),hint:t('已收录的期刊系列')},{label:t('会议系列'),value:fmt(n('Conferences')),hint:t('已收录的会议系列')}];
 for(const metric of metrics){
  const coverage=coverageDisplay(metric,overview.papers,locale());
  const label=metric?localizedText(metric.label_i18n,metric.label||t('阅读资料覆盖率')):t('阅读资料覆盖率');
  const hint=coverage.count===null?t('统计暂不可用'):typeof coverage.denominator==='number'?fmt(coverage.count)+' / '+fmt(coverage.denominator):t('已关联 {n} 篇',{n:fmt(coverage.count)});
  const explanation=metric?localizedText(metric.note_i18n,metric.note||''):'';
  const tooltip=[explanation,coverage.count===null?'':hint,metric?.sampled_at?t('登记时间：')+time(metric.sampled_at):''].filter(Boolean).join(' · ');
  cells.push({label,value:coverage.rate,hint,tooltip,coverage:true});
 }
 return <div className={'stats'+(compact?' stats-compact':'')} role="group" aria-label={t('数据库概览')} tabIndex={compact?0:undefined} style={{'--overview-columns':cells.length} as React.CSSProperties}>{cells.map((cell,index)=><div className={'stat'+(cell.coverage?' stat-coverage':'')} key={index} title={cell.tooltip||cell.hint}><span>{cell.label}</span><strong>{cell.value}</strong>{(!compact||cell.coverage)&&<small>{cell.hint}</small>}</div>)}</div>;
}
export function IndexStatus({index}:{index?:Index}){
 if(!index)return null;
 const total=index.overview?.papers||0,finished=index.phase==='ready',stale=!index.checked_at||Date.now()-new Date(index.checked_at).getTime()>120000;
 const ready=finished&&!index.error&&!stale;
 const title=index.error?t('搜索同步异常'):stale?t('同步检查已过期'):finished?t('搜索索引已同步'):t('搜索索引正在构建');
 return <section className={'index-status'+(ready?' synced':'')} aria-label={t('搜索索引')}><div className="index-status-heading"><span className="status-dot" aria-hidden="true"/><strong>{title}</strong></div><span className="index-status-count">{fmt(index.indexed)} / {fmt(total)}{t(' 条 · 积压 ')}{fmt(index.backlog)}{t(' 条')}</span>{!finished&&<div className="progress"><i style={{width:Math.min(100,(index.indexed||0)/Math.max(total,1)*100)+'%'}}/></div>}{!ready&&<p>{!finished?t('当前搜索仅覆盖已索引记录；按论文编号可直接查询数据库。'):t('搜索可能尚未包含最近变更；详情仍直接读取数据库。')}</p>}<small>{t('同步检查：')}{time(index.checked_at)}</small></section>;
}
