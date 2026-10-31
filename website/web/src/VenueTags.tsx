import { t, useLanguage } from './i18n';
import {guideCopy,tierLabels,venueRanking,type VenueTier} from './venueRanking';
import {useState,lazy,Suspense} from 'react';
const VenueGuide=lazy(()=>import('./VenueGuide'));
import { matchingVenueFamilies, paperVenueTags, selectedVenueFamilies, venueFamilies, isHistoricalFamily, orderVenueFamilies, venuePeriodText, type VenueReference } from './venueFamilies';
export function VenueTags({ paper }: {
    paper: VenueReference;
}) {
    const tags = paperVenueTags(paper);
    if (!tags.length)
        return null;
    return <div className="venue-tags" aria-label={t("刊会来源标签")}>{tags.map(tag => <span className={'venue-tag ' + tag.family.kind.toLowerCase()} key={tag.family.key} title={tag.family.title + (tag.old ? t("（历史刊会名称）") : '')}>{tag.label}{tag.old && <span className="venue-old">{t("Old")}</span>}</span>)}</div>;
}
export function VenueFamilyFilter({ value, onChange }: {
    value: string;
    onChange: (value: string) => void;
}) {
    const [open, setOpen] = useState(window.innerWidth > 760 || !!value), [query, setQuery] = useState(''),[guideOpen,setGuideOpen]=useState(false);
    const language=useLanguage(),copy=guideCopy[language];
    const selected = orderVenueFamilies(selectedVenueFamilies(value)), keys = new Set(selected.map(f => f.key)), matches = orderVenueFamilies(matchingVenueFamilies(query));
    function toggle(key: string) { const next = new Set(keys); if (next.has(key))
        next.delete(key);
    else
        next.add(key); onChange(venueFamilies.filter(f => next.has(f.key)).map(f => f.key).join(',')); }
    return <><details className="venue-family-filter panel" open={open} onToggle={e => setOpen(e.currentTarget.open)}><summary><span className="venue-family-heading"><span>{t("电路精选刊会")}</span><button type="button" className="venue-guide-trigger" aria-label={copy.info} title={copy.info} aria-haspopup="dialog" aria-controls="venue-guide-dialog" aria-expanded={guideOpen} onClick={e=>{e.preventDefault();e.stopPropagation();setGuideOpen(true);}} onKeyDown={e=>{if(e.key==='Enter'||e.key===' ')e.stopPropagation();}}><span aria-hidden="true" className="venue-info-glyph">i</span></button></span><small>{selected.length ? t("已选 ") + selected.length + t(" / 22 个家族") : t("全部 IEEE · 可按 22 个家族筛选")}</small></summary><div className="venue-family-body"><div className="venue-family-actions"><button type="button" onClick={() => onChange(venueFamilies.map(f => f.key).join(','))} disabled={selected.length === venueFamilies.length}>{t("选择全部电路刊会")}</button><button type="button" onClick={() => onChange('')} disabled={!selected.length}>{t("清除刊会标签")}</button><input aria-label={t("查找刊会标签")} placeholder={t("简称或全名，如 JSSC、SSCL")} value={query} onChange={e => setQuery(e.target.value)}/></div>{(['Journals', 'Conferences'] as const).map(kind => <div className="venue-family-group" key={kind}><h3>{kind === 'Journals' ? t("期刊") : t("会议")}</h3><div className="venue-family-tier-list" role="group" aria-label={kind === 'Journals' ? t("电路期刊标签") : t("电路会议标签")}>{([1,2,3,4] as VenueTier[]).map(tier=>{const entries=matches.filter(f=>f.kind===kind&&venueRanking[f.key].tier===tier);return entries.length?<section className="venue-family-tier" key={tier}><h4>{tierLabels[tier][language]}</h4><div className="venue-family-choices">{entries.map(f=><button type="button" className="venue-family-choice" key={f.key} aria-pressed={keys.has(f.key)} title={f.title+' · '+tierLabels[tier][language]+' · '+venuePeriodText(f,t("至今"),t("目录"))} onClick={()=>toggle(f.key)}>{f.label}{isHistoricalFamily(f)&&<span className="venue-old">{t("Old")}</span>}</button>)}</div></section>:null;})}</div></div>)}{!matches.length && <p className="muted">{t("没有匹配的刊会标签。")}</p>}{selected.length > 0 && <div className="venue-selection" role="status"><span>{t("当前：")}</span><div className="venue-selection-items">{selected.map(f => <span className="venue-selection-item" key={f.key}><strong>{f.label}</strong><span className="venue-period">（{venuePeriodText(f,t("至今"),t("目录"))}）</span>{isHistoricalFamily(f)&&<span className="venue-old">{t("Old")}</span>}</span>)}</div></div>}</div></details>{guideOpen&&<Suspense fallback={<p className="hint" role="status">{copy.loading}</p>}><VenueGuide onClose={()=>setGuideOpen(false)}/></Suspense>}</>;
}
