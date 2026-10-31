import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import ThemeControl from './ThemeControl';
import ReaderLayoutControls,{useReaderLayout} from './ReaderLayoutControls';
import ScientificTitle from './ScientificTitle';
import PageSizeControl,{normalizePageSize,storedPageSize,pageSizePreference} from './PageSizeControl';
import {coverageDisplay,type ResourceCoverage} from './resourceCoverage';
import PaperSelectionToolbar from './PaperSelectionToolbar';
import type {SelectedPaper} from './paperBatch';
import {resultSelection} from './resultSelection';
const BatchDownloadDialog=React.lazy(()=>import('./BatchDownloadDialog'));
const CitationDialog=React.lazy(()=>import('./CitationDialog'));
const DocumentReader=React.lazy(()=>import('./DocumentReader').then(module=>({default:module.DocumentReader})));
import {ResourceSettings} from './ResourceSettings';
import {AuthorProfile} from './AuthorProfile';
import {AuthorLinks,AuthorSearch} from './AuthorSearch';
import type {AuthorReference} from './authorLinks';
import { t, locale, useLanguage, setLanguage, errorMessage, localizedText, stageLabel, auditLabel, keywordGroupLabel, contentTypeLabel } from './i18n';
import { VenueFamilyFilter, VenueTags } from './VenueTags';
import { selectedVenueFamilies, venueNumbers } from './venueFamilies';
type User = {
    username: string;
    role: string;
    must_change: boolean;
    csrf: string;
};
type ReadingResource = {
    reader_href?: string;
    media_type?: string;
    kind?: string;
    id: string;
    href: string;
    label: string;
    label_i18n?: Record<string, string>;
    note?: string;
    note_i18n?: Record<string, string>;
    size_bytes?: number;
};
type Paper = {
    venue?: string;
    venue_series?: string[];
    number: string;
    title: string;
    authors: string;
    publication: string;
    year: number;
    kind: string;
    doi: string;
    snippet: string;
    abstract_state: string;
    keywords_state: string;
    resources?: ReadingResource[];
    author_refs?: AuthorReference[];
};
type Venue = {
    kind: string;
    number: string;
    title: string;
};
type Index = {
    year_range?: { min: number | null; max: number | null };
    phase?: string;
    indexed?: number;
    backlog?: number;
    checked_at?: string;
    error?: string;
    overview?: Overview;
};
type Overview = {
    resource_coverage?: ResourceCoverage[];
    papers: number;
    field_states: {
        abstract_state: string;
        keywords_state: string;
        n: number;
    }[];
    venues: {
        kind: string;
        n: number;
    }[];
    sampled_at: string;
};
type Filters = {
    limit: string;
    venue_tags: string;
    q: string;
    field: string;
    kind: string;
    venue: string;
    year_from: string;
    year_to: string;
    abstract_state: string;
    keywords_state: string;
    sort: string;
    author_source: string;
    author_id: string;
    author_unidentified: string;
};
function invalidYearRange(f: Pick<Filters, 'year_from' | 'year_to'>) {
    return !!f.year_from && !!f.year_to && Number(f.year_from) > Number(f.year_to);
}
const statusNames: Record<string, string> = { complete: '已完成', pending: '待补查', no_data: '来源无数据', failed: '失败', queued: '排队中', running: '运行中', blocked: '访问受限 / 已暂停', done: '已完成', completed: '已完成', partial: '部分完成', paused: '已暂停', deferred: '待后续发布', building: '首次构建中', catching_up: '追平变更中', ready: '已同步', interrupted: '进程中断' };
const contentStateNames: Record<string,string> = {complete:'已收录',pending:'待补查',no_data:'来源无数据',failed:'失败'};
const fmt = (n: number | undefined) => Number(n || 0).toLocaleString(locale());
const time = (s: string | undefined) => s ? new Date(s.replace(' ', 'T') + (/(?:Z|[+-]\d{2}:\d{2})$/.test(s) ? '' : '+08:00')).toLocaleString(locale()) : '—';
let csrf = '';
async function api(path: string, method = 'GET', data?: unknown) {
    const response = await fetch(path, { method, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(method !== 'GET' ? { 'X-CSRF-Token': csrf } : {}) }, ...(data !== undefined ? { body: JSON.stringify(data) } : {}) });
    const result = await response.json();
    if (response.status === 401 && !path.startsWith('/api/auth/'))
        window.dispatchEvent(new Event('cirdc-auth-expired'));
    if (!response.ok)
        throw new Error(errorMessage(result));
    return result;
}
function Badge({ state }: {
    state: string;
}) { return <span className={'badge ' + state}>{t(statusNames[state] || state)}</span>; }
function LanguageSwitch() { const lang = useLanguage(); return <div className="language-switch" role="group" aria-label={t('界面语言')}><button type="button" lang="zh-CN" aria-pressed={lang === 'zh'} onClick={() => setLanguage('zh')}>{t("中文")}</button><button type="button" lang="en" aria-pressed={lang === 'en'} onClick={() => setLanguage('en')}>{t("English")}</button></div>; }
function App() {
    useLanguage();
    const profileRoute = window.location.pathname.match(/^\/authors\/(ieee)\/([0-9]{1,64})$/);
    const [user, setUser] = useState<User | null>(null), [mode, setMode] = useState('reader'), [loading, setLoading] = useState(true), [error, setError] = useState(''), [change, setChange] = useState(false), [authRequired,setAuthRequired]=useState(true);
    async function session() { try {
        const r = await api('/api/auth/session');
        csrf = r.csrf;
        setUser(r.user);
        setMode(r.interface);
        setAuthRequired(r.interface==='admin'||r.authentication_required!==false);
    }
    catch {
        setError(t("暂时无法连接服务，请刷新页面。"));
    }
    finally {
        setLoading(false);
    } }
    useEffect(() => { void session(); const expired = () => { setUser(null); void session(); }; window.addEventListener('cirdc-auth-expired', expired); return () => window.removeEventListener('cirdc-auth-expired', expired); }, []);
    async function logout() { try {
        await api('/api/auth/logout', 'POST', {});
        setUser(null);
        setChange(false);
        await session();
    }
    catch (e) {
        setError(String((e as Error).message));
    } }
    const publicReader=mode==='reader'&&!authRequired;
    if (loading)
        return <div className="loading">{t("正在连接文献数据库…")}</div>;
    return <><header className={'top'+(publicReader?' public-reader-header':'')}><a className="brand" href={mode === 'admin' ? '/admin/' : '/'}><span className="brand-mark">{t("C")}</span><strong>{t("CIRDC ")}<em>{t("Pro")}</em></strong><span className="brand-sub">{mode === 'admin' ? t("管理员工作台") : t("文献数据库")}</span></a><div className="top-actions"><LanguageSwitch /><ThemeControl/>{user && !publicReader && <><span className="username">{user.username}</span><button className="text-button" onClick={() => setChange(true)}>{t("修改密码")}</button><button className="text-button" onClick={() => void logout()}>{t("退出")}</button></>}</div></header>
 {error && <div className="global-error" role="alert">{t(error)}<button onClick={() => setError('')}>{t("关闭")}</button></div>}
 {!publicReader && !user ? <Login mode={mode} onLogin={u => { setUser(u); csrf = u.csrf; }}/> : !publicReader && (user?.must_change || change) ? <PasswordForm forced={!!user?.must_change} done={() => { setChange(false); setUser(null); void session(); }} cancel={() => setChange(false)}/> : mode === 'admin' ? <Admin /> : profileRoute ? <AuthorProfile source={profileRoute[1]} authorId={profileRoute[2]} fetcher={api}/> : <Reader />}
 <footer>{t("CIRDC Pro ")}<span>·</span>{t(" IEEE 期刊与会议元数据 ")}</footer></>;
}
function Login({ mode, onLogin }: {
    mode: string;
    onLogin: (u: User) => void;
}) {
    const [name, setName] = useState(''), [password, setPassword] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
    async function submit(e: React.FormEvent) { e.preventDefault(); setBusy(true); setError(''); try {
        const r = await api('/api/auth/login', 'POST', { username: name, password });
        csrf = r.csrf;
        onLogin(r.user);
    }
    catch (e) {
        setError((e as Error).message);
    }
    finally {
        setBusy(false);
    } }
    return <main className="login-layout"><section className="login-intro"><span className="eyebrow">{t("CIRCUITS · RESEARCH · DISCOVERY")}</span><h1>{t("从一篇论文，")}<br />{t("开始下一步研究。")}</h1><p>{t("汇集期刊与会议元数据。检索标题、作者、关键词和摘要，查看完整记录与数据覆盖情况。")}</p><div className="paper-illustration"><div><span>{t("IEEE JOURNALS & CONFERENCES")}</span><i /><i /><i /><b>{t("Metadata, connected.")}</b></div><div className="paper-back"/></div></section><section className="login-card"><span className="eyebrow">{mode === 'admin' ? t("ADMINISTRATOR") : t("WELCOME BACK")}</span><h2>{mode === 'admin' ? t("登录管理员工作台") : t("登录文献数据库")}</h2><p className="muted">{t("使用独立的网站账户。首次登录需要修改初始密码。")}</p><form onSubmit={e => void submit(e)}><label>{t("用户名")}<input name="username" autoComplete="username" required value={name} onChange={e => setName(e.target.value)}/></label><label>{t("密码")}<input name="password" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)}/></label>{error && <p className="error" role="alert">{t(error)}</p>}<button className="primary wide" disabled={busy}>{busy ? t("正在登录…") : t("登录")}</button></form><p className="hint">{t("账户由管理员开通。忘记密码时请联系管理员。")}</p></section></main>;
}
function PasswordInput({ label, value, onChange, autoComplete, minLength }: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    autoComplete: 'current-password' | 'new-password';
    minLength?: number;
}) {
    const [visible, setVisible] = useState(false);
    const id = React.useId();
    return <div className="password-field"><label htmlFor={id}>{label}</label><div className="password-input"><input id={id} type={visible ? 'text' : 'password'} autoComplete={autoComplete} minLength={minLength} value={value} onChange={e => onChange(e.target.value)} required/><button className="password-visibility" type="button" aria-controls={id} aria-pressed={visible} aria-label={(visible ? t('隐藏') : t('显示')) + ' ' + label.split(' · ')[0]} onClick={() => setVisible(v => !v)}><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>{visible && <path d="m3 3 18 18"/>}</svg>{visible ? t("隐藏") : t("显示")}</button></div></div>;
}
function PasswordForm({ forced, done, cancel }: {
    forced: boolean;
    done: () => void;
    cancel: () => void;
}) {
    const [current, setCurrent] = useState(''), [next, setNext] = useState(''), [confirm, setConfirm] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
    async function submit(e: React.FormEvent) { e.preventDefault(); if (next !== confirm) {
        setError(t("两次输入的新密码不一致。"));
        return;
    } setBusy(true); try {
        await api('/api/auth/password', 'POST', { current_password: current, new_password: next });
        done();
    }
    catch (e) {
        setError((e as Error).message);
    }
    finally {
        setBusy(false);
    } }
    return <main className="password-page panel"><span className="eyebrow">{t("ACCOUNT SECURITY")}</span><h1>{forced ? t("设置你自己的密码") : t("修改密码")}</h1><p className="muted">{forced ? t("首次登录，请先修改初始密码后继续。") : t("修改后所有已有会话会退出，请使用新密码重新登录。")}</p><form onSubmit={e => void submit(e)}><PasswordInput label={t("当前密码")} value={current} onChange={setCurrent} autoComplete="current-password"/><PasswordInput label={t("新密码 · 至少 8 个字符")} value={next} onChange={setNext} autoComplete="new-password" minLength={8}/><PasswordInput label={t("再次输入新密码")} value={confirm} onChange={setConfirm} autoComplete="new-password" minLength={8}/>{error && <p className="error" role="alert">{t(error)}</p>}<div className="actions"><button className="primary" disabled={busy}>{busy ? t("保存中…") : t("保存并重新登录")}</button>{!forced && <button type="button" onClick={cancel}>{t("取消")}</button>}</div></form></main>;
}
function OverviewCards({ overview,compact=false }: {overview?: Overview;compact?:boolean}) {
    if (!overview) return null;
    const n=(kind:string)=>overview.venues.find(v=>v.kind===kind)?.n||0;
    const metric=overview.resource_coverage?.[0],coverage=coverageDisplay(metric,overview.papers,locale());
    const coverageLabel=metric?localizedText(metric.label_i18n,metric.label||t("阅读资料覆盖率")):t("阅读资料覆盖率");
    const coverageHint=coverage.count===null?t("统计暂不可用"):typeof coverage.denominator==='number'?fmt(coverage.count)+' / '+fmt(coverage.denominator):t("已关联 {n} 篇",{n:fmt(coverage.count)});
    const explanation=metric?localizedText(metric.note_i18n,metric.note||''):'';
    const tooltip=[explanation,coverage.count===null?'':fmt(coverage.count)+' / '+fmt(typeof coverage.denominator==='number'?coverage.denominator:undefined),metric?.sampled_at?t("登记时间：")+time(metric.sampled_at):''].filter(Boolean).join(' · ');
    const cells=[[t("论文记录"),fmt(overview.papers),t("数据库中已有记录")],[t("期刊"),fmt(n('Journals')),t("已收录的期刊系列")],[t("会议系列"),fmt(n('Conferences')),t("已收录的会议系列")],[coverageLabel,coverage.rate,coverageHint]];
    return <div className={'stats'+(compact?' stats-compact':'')} aria-label={t("数据库概览")}>{cells.map(([label,value,hint],index)=><div className="stat" key={label} title={index===3?tooltip:hint}><span>{label}</span><strong>{value}</strong><small>{compact&&index<3?'\u00a0':hint}</small></div>)}</div>;
}
function IndexStatus({ index }: {
    index?: Index;
}) {
    if (!index)
        return null;
    const total = index.overview?.papers || 0, finished = index.phase === 'ready', stale = !index.checked_at || Date.now() - new Date(index.checked_at).getTime() > 120000;
    const ready = finished && !index.error && !stale;
    const title = index.error ? t("搜索同步异常") : stale ? t("同步检查已过期") : finished ? t("搜索索引已同步") : t("搜索索引正在构建");
    return <div className={'index-status ' + (ready ? 'synced' : '')}><div><strong>{title}</strong><span>{fmt(index.indexed)} / {fmt(total)}{t(" 条 · 积压 ")}{fmt(index.backlog)}{t(" 条")}</span></div>{!finished && <div className="progress"><i style={{ width: Math.min(100, (index.indexed || 0) / Math.max(total, 1) * 100) + '%' }}/></div>}{!ready && <p>{!finished ? t("当前搜索仅覆盖已索引记录；按论文编号可直接查询数据库。") : t("搜索可能尚未包含最近变更；详情仍直接读取数据库。")}</p>}<small>{t("同步检查：")}{time(index.checked_at)}</small></div>;
}
function Reader() {
    const [citationNumbers,setCitationNumbers]=useState<string[]>([]),[downloadSelection,setDownloadSelection]=useState<SelectedPaper[]|null>(null);
    // Selection belongs to the rows on screen, never to a hidden cross-search basket.
    const [results,dispatchResults]=React.useReducer(resultSelection<Paper>,{rows:[],selected:[]});
    const {rows}=results,selectedKeys=new Set(results.selected);
    function snapshot(p:Paper):SelectedPaper{return {number:p.number,title:p.title,year:p.year,kind:p.kind,venue:p.venue,venue_series:p.venue_series,publication:p.publication};}
    const selected=rows.filter(p=>selectedKeys.has(p.number)).map(snapshot);
    function selectPapers(papers:Paper[],checked:boolean){dispatchResults({type:'select',numbers:papers.map(p=>p.number),checked});}
    useEffect(()=>{try{sessionStorage.removeItem('cirdc.selected-papers.v1');}catch{/* Legacy baskets are never restored. */}},[]);
    const [filtersOpen, setFiltersOpen] = useState(window.innerWidth > 760);
    const latestRequest = React.useRef(0);
    const defaults: Filters = { limit: storedPageSize(), venue_tags: '', q: '', field: 'all', kind: '', venue: '', year_from: '', year_to: '', abstract_state: '', keywords_state: '', sort: 'relevance', author_source: '', author_id: '', author_unidentified: '' };
    const initial = { ...defaults, ...Object.fromEntries(new URLSearchParams(window.location.search)) };
    initial.limit=normalizePageSize(initial.limit,defaults.limit);
    initial.venue_tags = selectedVenueFamilies(initial.venue_tags).map(f => f.key).join(',');
    const [filters, setFilters] = useState<Filters>(initial), [applied, setApplied] = useState<Filters>(initial), [venueText, setVenueText] = useState(initial.venue), [venues, setVenues] = useState<Venue[]>([]), [index, setIndex] = useState<Index>(), [cursor, setCursor] = useState<string | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState(''), [partial, setPartial] = useState(false), [detail, setDetail] = useState<string | null>(window.location.pathname.match(/^\/papers\/(\d+)/)?.[1] || null);
    useEffect(()=>{try{localStorage.setItem(pageSizePreference,applied.limit);}catch{/* The URL still preserves this setting. */}},[applied.limit]);
    function changePageSize(limit:string){
        const next={...applied,limit};setFilters(old=>({...old,limit}));setApplied(next);
        history.replaceState({},'', '/?'+new URLSearchParams(Object.entries(next).filter(([key,value])=>key!=='cursor'&&!!value)));
        void load(next);
    }
    function update(k: keyof Filters, v: string) { setFilters(f => ({ ...f, [k]: v })); if (k === 'year_from' || k === 'year_to') setError(''); }
    async function load(f: Filters, more?: string) { const request = ++latestRequest.current; setBusy(true); setError(''); if (!more) {
        setCursor(null);dispatchResults({type:'reset'});
    } if (invalidYearRange(f)) {
        setBusy(false); setError(t("起始年份不能晚于结束年份。")); return;
    } try {
        const { venue_tags, ...query } = f;
        const params = new URLSearchParams(Object.entries(query).filter(([key, v]) => key!=='cursor'&&!!v));
        const publicationIds = venueNumbers(venue_tags);
        if (publicationIds.length)
            params.set('venue_any', publicationIds.join(','));
        if (more)
            params.set('cursor', more);
        const r = await api('/api/papers?' + params);
        if (request !== latestRequest.current)
            return;
        dispatchResults({type:more?'append':'replace',rows:r.items});
        setCursor(r.next_cursor);
        setPartial(!!r.partial);
    }
    catch (e) {
        if (request === latestRequest.current)
            setError((e as Error).message);
    }
    finally {
        if (request === latestRequest.current)
            setBusy(false);
    } }
    async function overview() { try {
        const r = await api('/api/overview');
        setIndex(r.index);
    }
    catch (e) {
        setError((e as Error).message);
    } }
    useEffect(() => { void overview(); void api('/api/venues').then(r => setVenues(r.items)).catch(() => { }); if (!detail) {const params=new URLSearchParams(window.location.search);params.set('limit',initial.limit);params.delete('cursor');history.replaceState({},'', '/?'+params);void load(initial);} const timer = setInterval(() => void overview(), 60000); const pop = () => setDetail(window.location.pathname.match(/^\/papers\/(\d+)/)?.[1] || null); window.addEventListener('popstate', pop); return () => { clearInterval(timer); window.removeEventListener('popstate', pop); }; }, []);
    function applySearch(next: Filters) { if (invalidYearRange(next)) { setError(t("起始年份不能晚于结束年份。")); return; } const value = venueText.split(' · ')[0].trim(); if (value && !/^\d+$/.test(value)) {
        setError(t("请从候选列表选择刊会，或输入刊会编号。"));
        return;
    } const resetAuthor = next.field === 'authors' && next.q !== applied.q; const f = { ...next, venue: value, ...(resetAuthor ? { author_source: '', author_id: '', author_unidentified: '' } : {}) }; setFilters(f); setApplied(f); history.replaceState({}, '', '/?' + new URLSearchParams(Object.entries(f).filter(([, v]) => v))); void load(f); }
    function submit(e: React.FormEvent) { e.preventDefault(); applySearch(filters); }
    function updateSearchOption(key: 'field' | 'sort', value: string) { if (filters[key] === value)
        return; const next = { ...filters, [key]: value }; setFilters(next); applySearch(next); }
    function open(number: string) { setDetail(number); history.pushState({}, '', '/papers/' + number); window.scrollTo(0, 0); }
    function back() { setDetail(null); history.pushState({}, '', '/?' + new URLSearchParams(Object.entries(applied).filter(([, v]) => v))); if (!rows.length)
        void load(applied); }
    if (detail)
        return <PaperDetail number={detail} back={back}/>;
    const choices = venues.filter(v => (!filters.kind || v.kind === filters.kind) && (!venueText || (v.number + ' ' + v.title).toLowerCase().includes(venueText.toLowerCase()))).slice(0, 80);
    const latestYear = Math.min(2200, Math.max(new Date().getFullYear(), index?.year_range?.max || 0, Number(filters.year_from) || 0, Number(filters.year_to) || 0));
    const years = Array.from({ length: latestYear - 1800 + 1 }, (_, i) => latestYear - i);
    return <><main className="workspace reader-workspace"><div className="page-heading reader-heading"><div><span className="eyebrow">{t("LITERATURE EXPLORER")}</span><h1>{t("探索论文与研究线索")}</h1><p className="muted">{t("从标题到摘要，查找你关心的电路、方法与作者。")}</p></div><OverviewCards overview={index?.overview} compact/></div><div className="content-grid"><aside><details className="filter-disclosure" open={filtersOpen} onToggle={e => setFiltersOpen(e.currentTarget.open)}><summary>{t("筛选刊会、年份与补全状态")}</summary><section className="panel filter-panel"><h2>{t("缩小检索范围")}</h2><label>{t("出版物类型")}<select value={filters.kind} onChange={e => { update('kind', e.target.value); setVenueText(''); update('venue', ''); }}><option value="">{t("全部类型")}</option><option value="Journals">{t("期刊")}</option><option value="Conferences">{t("会议")}</option></select></label><label>{t("期刊 / 会议系列")}<input list="venues" value={venueText} onChange={e => setVenueText(e.target.value)} placeholder={t("输入名称或编号")}/><datalist id="venues">{choices.map(v => <option key={v.kind + v.number} value={v.number + ' · ' + v.title}/>)}</datalist></label><div className="year-range"><label>{t("起始年份")}<select value={filters.year_from} onChange={e => update('year_from', e.target.value)}><option value="">{t("不限")}</option>{years.map(year => <option key={year} value={year} disabled={!!filters.year_to && year > Number(filters.year_to)}>{year}</option>)}</select></label><label>{t("结束年份")}<select value={filters.year_to} onChange={e => update('year_to', e.target.value)}><option value="">{t("不限")}</option>{years.map(year => <option key={year} value={year} disabled={!!filters.year_from && year < Number(filters.year_from)}>{year}</option>)}</select></label></div>{(['abstract_state', 'keywords_state'] as const).map(k => <label key={k}>{k === 'abstract_state' ? t("摘要状态") : t("关键词状态")}<select value={filters[k]} onChange={e => update(k, e.target.value)}><option value="">{t("全部状态")}</option>{['complete', 'pending', 'no_data', 'failed'].map(s => <option key={s} value={s}>{t(contentStateNames[s])}</option>)}</select></label>)}<button className="wide" onClick={() => { const cleared={...defaults,limit:applied.limit};setFilters(cleared);setVenueText('');setApplied(cleared);history.replaceState({},'', '/?limit='+cleared.limit);void load(cleared); }}>{t("清除全部条件")}</button><p className="hint">{t("修改条件后，点击右侧「检索」应用。")}</p></section></details></aside><section className="results"><form className="search-box" onSubmit={submit}><div className="search-main"><span aria-hidden="true">⌕</span><input aria-label={t("搜索论文")} placeholder={filters.field === 'authors' ? t("输入作者姓名或 IEEE 作者 ID") : t("搜索论文、作者、关键词，或输入编号 / DOI")} value={filters.q} onChange={e => update('q', e.target.value)}/><button className="primary" disabled={busy || invalidYearRange(filters)}>{t("检索")}</button></div><div className="search-options"><div className="search-option-section"><span className="search-option-label">{t("检索字段")}</span><div className="search-choice-group field-choices" role="group" aria-label={t("检索字段")}>{[['all', t("全部")], ['title', t("标题")], ['authors', t("作者")], ['keywords', t("关键词")], ['abstract', t("摘要")]].map(([v, l]) => <button key={v} type="button" className="search-choice" aria-pressed={filters.field === v} onClick={() => updateSearchOption('field', v)}>{l}</button>)}</div></div><div className="search-option-section"><span className="search-option-label">{t("排序")}</span><div className="search-choice-group" role="group" aria-label={t("排序")}>{[['relevance', t("相关度")], ['year', t("年份从新到旧")]].map(([v, l]) => <button key={v} type="button" className="search-choice" aria-pressed={filters.sort === v} onClick={() => updateSearchOption('sort', v)}>{l}</button>)}</div></div></div></form><VenueFamilyFilter value={filters.venue_tags} onChange={value => applySearch({ ...filters, venue_tags: value })}/>{applied.field === 'authors' && (applied.q.trim() || applied.author_id) && <AuthorSearch query={applied.q} authorId={applied.author_id} source={applied.author_source||'ieee'} fetcher={api} onSelect={author=>applySearch({...filters,field:'authors',q:applied.q,author_source:author.source,author_id:author.author_id,author_unidentified:''})} onUnknown={()=>applySearch({...filters,field:'authors',q:applied.q,author_source:'',author_id:'',author_unidentified:'1'})}/>}{(applied.author_id || applied.author_unidentified) && <div className="selected-author" role="status"><span>{applied.author_id ? t("当前限定作者：IEEE ID ") + applied.author_id : t("当前查看：未提供作者 ID 的署名记录")}</span><button type="button" onClick={() => applySearch({ ...filters, author_id: '', author_source: '', author_unidentified: '' })}>{t("清除作者限定")}</button></div>}<div className="result-toolbar"><h2>{applied.q ? t("检索结果") : t("浏览论文")}</h2><PageSizeControl value={applied.limit} onChange={changePageSize}/><span className="muted">{t("已载入 ")}{fmt(rows.length)}{t(" 条")}{partial ? t(" · 索引覆盖或同步尚未完成") : ''}</span></div><PaperSelectionToolbar total={rows.length} count={selected.length} disabled={busy} onAll={checked=>dispatchResults({type:'all',checked})} onCite={()=>setCitationNumbers(selected.map(p=>p.number))} onDownload={()=>setDownloadSelection(selected)}/>{error && <div className="error-box" role="alert">{t(error)}</div>}{busy && !rows.length ? <div className="empty">{t("正在检索…")}</div> : !rows.length ? <div className="empty"><h3>{t("当前范围未找到记录")}</h3><p>{partial ? t("搜索索引仍在构建或同步，可直接输入论文编号查看。") : t("试试其他搜索词，或放宽刊会和年份条件。")}</p></div> : <div className="paper-list">{rows.map(p => <article className={'paper-row'+(selectedKeys.has(p.number)?' paper-selected':'')} key={p.number}><label className="paper-selection-control"><input type="checkbox" checked={selectedKeys.has(p.number)} disabled={busy} aria-label={t('选择论文：')+(p.title||p.number)} onChange={e=>selectPapers([p],e.target.checked)}/></label><div className="paper-year">{p.year || '—'}<small>{contentTypeLabel(p.kind) || '—'}</small></div><div className="paper-body"><a className="paper-title" href={'/papers/' + p.number} onClick={e => { e.preventDefault(); open(p.number); }}><ScientificTitle value={p.title} fallback={t("未提供标题")}/></a><AuthorLinks references={p.author_refs} fallback={p.authors}/><div className="publication-line"><VenueTags paper={p}/><p className="publication">{p.publication}</p></div>{p.snippet && <AbstractPreview number={p.number} preview={p.snippet}/>}<div className="paper-meta"><code>{p.number}</code><button type="button" className="citation-trigger" aria-label={t("获取引用格式：")+(p.title||p.number)} onClick={()=>setCitationNumbers([p.number])}>{t("引用")}</button>{p.resources?.[0] && readingHref(p.resources[0]) && <a className="button resource-shortcut" href={readingHref(p.resources[0])} target="_blank" rel="noopener noreferrer">{localizedText(p.resources[0].label_i18n, p.resources[0].label)} ↗</a>}</div></div></article>)}</div>}{cursor && <button className="load-more" disabled={busy} onClick={() => void load(applied, cursor)}>{busy ? t("加载中…") : t("加载更多论文")}</button>}<p className="hint result-note">{t("统计采样于 ")}{time(index?.overview?.sampled_at)}{t("。统计仅反映已有元数据，不代表本轮新抓取或已人工验证。")}</p></section></div></main>{citationNumbers.length>0&&<React.Suspense fallback={<p className="hint" role="status">{t("正在生成引用…")}</p>}><CitationDialog numbers={citationNumbers} fetcher={api} onClose={()=>setCitationNumbers([])}/></React.Suspense>}{downloadSelection&&<React.Suspense fallback={<p className="hint" role="status">{t('正在读取下载信息…')}</p>}><BatchDownloadDialog selected={downloadSelection} fetcher={api} onClose={()=>setDownloadSelection(null)}/></React.Suspense>}</>;
}
function AbstractPreview({ number, preview }: {number: string;preview: string}) {
    const [expanded, setExpanded] = useState(false), [full, setFull] = useState<string | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
    const clean = text(preview), expandLabel = t("展开摘要");
    const [collapsed, setCollapsed] = useState(clean), [truncated, setTruncated] = useState(false);
    const loading = React.useRef(false), container = React.useRef<HTMLDivElement>(null), id = React.useId();
    React.useLayoutEffect(() => {
        const host = container.current;
        if (!host) return;
        let previousWidth = -1;
        function fit() {
            if (!host) return;
            const width = host.getBoundingClientRect().width;
            if (!width || Math.abs(width - previousWidth) < .5) return;
            previousWidth = width;
            const measure = document.createElement('p');
            measure.className = 'snippet abstract-measure';
            measure.setAttribute('aria-hidden', 'true');
            measure.style.width = width + 'px';
            const content = document.createElement('span');
            content.textContent = clean;
            measure.append(content);
            host.append(measure);
            try {
                const maxHeight = parseFloat(getComputedStyle(measure).lineHeight) * 2 + .5;
                const needsTail = measure.getBoundingClientRect().height > maxHeight || preview.length >= 400;
                setTruncated(needsTail);
                if (!needsTail) { setCollapsed(clean); return; }
                const tail = document.createElement('span');
                tail.className = 'abstract-tail';
                tail.append(document.createTextNode('… '));
                const label = document.createElement('span');
                label.className = 'abstract-toggle';
                label.textContent = expandLabel;
                tail.append(label); measure.append(tail);
                const characters = Array.from(clean);
                let lower = 0, upper = characters.length;
                while (lower < upper) {
                    const middle = Math.ceil((lower + upper) / 2);
                    content.textContent = characters.slice(0, middle).join('').trimEnd();
                    if (measure.getBoundingClientRect().height <= maxHeight) lower = middle;
                    else upper = middle - 1;
                }
                let fitted = characters.slice(0, lower).join('').trimEnd().replace(/[.…]+$/, '');
                const space = fitted.lastIndexOf(' ');
                if (space > fitted.length - 24 && space > 0 && lower < characters.length && /[A-Za-z]/.test(characters[lower] || '')) fitted = fitted.slice(0, space);
                setCollapsed(fitted);
            } finally { measure.remove(); }
        }
        fit();
        const observer = new ResizeObserver(fit); observer.observe(host);
        return () => observer.disconnect();
    }, [clean, preview.length, expandLabel]);
    async function readFull() {
        if (loading.current) return;
        loading.current = true; setBusy(true); setError('');
        try { const value = await api('/api/papers/' + encodeURIComponent(number)); setFull(text(value.paper.record.abstract)); }
        catch (e) { setError((e as Error).message); }
        finally { loading.current = false; setBusy(false); }
    }
    function toggle() { const opening = !expanded; setExpanded(opening); if (opening && full === null && !loading.current) void readFull(); }
    return <div className="abstract-preview" ref={container}><p id={id} className={'snippet' + (expanded ? ' expanded' : '')}><span className="abstract-copy">{(expanded ? full ?? clean : collapsed) || '—'}</span>{(expanded || truncated) && <span className="abstract-tail">{expanded ? ' ' : <span aria-hidden="true">… </span>}<button type="button" className="abstract-toggle" aria-expanded={expanded} aria-controls={id} onClick={toggle}>{expanded ? t("收起摘要") : expandLabel}</button></span>}</p>{expanded && busy && <p className="hint abstract-loading" role="status">{t("正在读取完整摘要…")}</p>}{expanded && error && <div className="abstract-error" role="alert"><p className="error">{t(error)}</p><button type="button" onClick={() => void readFull()}>{t("重试加载摘要")}</button></div>}</div>;
}
function text(value: unknown) { return typeof value === 'string' ? value.replace(/<[^>]*>/g, '') : ''; }
function resourceHref(value: unknown) { return typeof value === 'string' && value.startsWith('/api/resources/') ? value : undefined; }
function readingHref(item:ReadingResource) { return resourceHref(item.reader_href)||resourceHref(item.href); }
function isPdfResource(item:ReadingResource) { return item.media_type?.split(';')[0].trim().toLowerCase()==='application/pdf'; }
function PaperPdfLink({ items, notice, noticeLocales }: {
    items?: ReadingResource[];
    notice?: string;
    noticeLocales?: Record<string, string>;
}) {
    const noticeId=React.useId();
    const pdf=(items||[]).find(item=>item.kind!=='document'&&resourceHref(item.href)&&isPdfResource(item));
    const missingText=localizedText(noticeLocales,notice||t("暂无已关联 PDF"));
    return pdf?<a className="button detail-pdf-trigger" href={readingHref(pdf)} target="_blank" rel="noopener noreferrer">{t("阅读 PDF")} ↗</a>:<><button type="button" className="detail-pdf-trigger reading-pdf-unavailable" disabled aria-describedby={noticeId} title={missingText}>{t("阅读 PDF")} ↗</button><span id={noticeId} hidden>{missingText}</span></>;
}
function ReadingResources({ items }: { items?: ReadingResource[] }) {
    const available=(items||[]).filter(item=>item.kind!=='document'&&!isPdfResource(item)&&resourceHref(item.href));
    if(!available.length)return null;
    return <section className="reading-resources"><h3>{t("本地资料")}</h3>{available.map(item=><div className="reading-resource" key={item.id}><a className="button wide" href={readingHref(item)} target="_blank" rel="noopener noreferrer">{localizedText(item.label_i18n,item.label)} ↗</a>{item.note&&<p className="hint">{localizedText(item.note_i18n,item.note)}{item.size_bytes?' · '+(item.size_bytes/1024/1024).toFixed(1)+' MiB':''}</p>}</div>)}</section>;
}
function PaperDetail({ number, back }: {
    number: string;
    back: () => void;
}) {
    const [item, setItem] = useState<any>(), [error, setError] = useState(''), [citationOpen,setCitationOpen]=useState(false);
    const {layout,update:changeLayout,reset:resetLayout}=useReaderLayout(),publicationToggle=useRef<HTMLButtonElement>(null);
    const publicationId='publication-information-'+number;
    function togglePublication(){changeLayout({infoOpen:!layout.infoOpen});requestAnimationFrame(()=>publicationToggle.current?.focus({preventScroll:true}));}
    useEffect(() => { void api('/api/papers/' + number).then(r => setItem(r.paper)).catch(e => setError(e.message)); }, [number]);
    if (error)
        return <main className="workspace"><button onClick={back}>{t("← 返回检索")}</button><p className="error">{t(error)}</p></main>;
    if (!item)
        return <main className="workspace">{t("正在读取论文记录…")}</main>;
    const p = item.record;
    const references: AuthorReference[] = item.author_refs || (p.authors || []).map((a: any, i: number) => ({ source: 'ieee', author_id: a.id ? String(a.id) : null, name: a.preferredName || [a.firstName, a.lastName].filter(Boolean).join(' '), ordinal: i }));
    return <><main className="workspace detail-page" style={{'--reader-page-width':layout.pageWidth+'px','--reader-toc-width':layout.tocWidth+'px','--reader-font-scale':layout.fontScale/100,'--publication-column-width':(layout.infoOpen?layout.infoWidth:44)+'px'} as React.CSSProperties}><div className="detail-toolbar"><button className="back" onClick={back}>{t("← 返回检索")}</button><ReaderLayoutControls layout={layout} onChange={changeLayout} onReset={resetLayout}/></div><div className="detail-record-toolbar"><div className="detail-record-actions"><button type="button" className="detail-citation-trigger" aria-label={t("获取引用格式：")+(text(p.articleTitle)||number)} onClick={()=>setCitationOpen(true)}>{t("引用")}</button><PaperPdfLink items={item.resources} notice={item.resource_notice} noticeLocales={item.resource_notice_i18n}/></div><span className="eyebrow">{t("ARTICLE RECORD · ")}{number}</span></div><h1><ScientificTitle value={p.articleTitle} fallback={t("未提供标题")}/></h1><AuthorLinks references={references} detail/><div className="publication-line detail-publication-line"><VenueTags paper={{ kind: p.articleContentType, venue: String(p.publicationNumber || ''), venue_series: item.venue_series, publication: p.publicationTitle }}/><p className="publication">{[p.publicationTitle,p.publicationYear,p.publicationDate].filter(Boolean).join(' · ')}</p></div><div className="detail-grid"><section><div className="panel"><div className="section-heading"><h2>{t("摘要")}</h2></div><p className="abstract">{text(p.abstract) || '—'}</p></div><React.Suspense fallback={null}><DocumentReader resource={(item.resources||[]).find((resource:ReadingResource)=>resource.kind==='document')} fetcher={api}/></React.Suspense><div className="panel keywords-panel"><div className="section-heading"><h2>{t("关键词")}</h2></div>{Object.entries(p.keywords || {}).map(([name, words]) => <div className="keyword-group" key={name}><h3>{keywordGroupLabel(name)}</h3><div className="tags">{(words as string[]).map((word, i) => <a key={i} className="keyword-link" href={'/?' + new URLSearchParams({ field: 'keywords', q: word })} target="_blank" rel="noopener noreferrer" aria-label={t("在新标签页检索关键词：") + word}>{word}<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14 4h6v6M20 4 10 14M10 5H5v14h14v-5"/></svg></a>)}</div></div>)}{!Object.keys(p.keywords || {}).length && <p className="muted">{'—'}</p>}</div><details className="panel raw"><summary>{t("查看原始元数据 JSON")}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details></section><aside className={'publication-sidebar'+(!layout.infoOpen?' is-collapsed':'')}>{!layout.infoOpen&&<button type="button" ref={publicationToggle} className="publication-sidebar-rail" aria-label={t("展开出版信息")} title={t("展开出版信息")} aria-expanded={false} aria-controls={publicationId} onClick={togglePublication}><span aria-hidden="true">‹</span><span className="publication-sidebar-rail-label">{t("出版信息")}</span></button>}<div id={publicationId} className="panel bibliographic" hidden={!layout.infoOpen}><div className="publication-sidebar-heading"><h2>{t("出版信息")}</h2><button type="button" ref={layout.infoOpen?publicationToggle:undefined} className="publication-sidebar-toggle" aria-label={t("收起出版信息")} title={t("收起出版信息")} aria-expanded={true} aria-controls={publicationId} onClick={togglePublication}><span aria-hidden="true">›</span></button></div><dl>{[[t("论文编号"), number], [t("类型"), contentTypeLabel(p.articleContentType)], [t("出版物编号"), p.publicationNumber], [t("出版年份"), p.publicationYear], [t("卷 / 期"), [p.volume, p.issue].filter(Boolean).join(' / ')], [t("页码"), [p.startPage, p.endPage].filter(Boolean).join('–')], [t("出版商"), p.publisher], [t("DOI"), p.doi || t("未提供")], [t("记录更新"), time(item.updated_at)]].map(([k, v]) => <React.Fragment key={k}><dt>{k}</dt><dd>{v || '—'}</dd></React.Fragment>)}</dl><ReadingResources items={item.resources}/><a className="button wide" href={'https://ieeexplore.ieee.org/document/' + number} target="_blank" rel="noreferrer">{t("查看 IEEE Xplore 原始链接 ↗")}</a></div></aside></div></main>{citationOpen&&<React.Suspense fallback={<p className="hint" role="status">{t("正在生成引用…")}</p>}><CitationDialog numbers={[number]} fetcher={api} onClose={()=>setCitationOpen(false)}/></React.Suspense>}</>;
}
function Admin() {
    const [tab, setTab] = useState('jobs'), [jobs, setJobs] = useState<any[]>([]), [selected, setSelected] = useState(''), [job, setJob] = useState<any>(), [index, setIndex] = useState<Index>(), [error, setError] = useState(''), [notice, setNotice] = useState<{
        key: string;
        values?: Record<string, string>;
    } | null>(null), [busy, setBusy] = useState(false), [log, setLog] = useState(''), [diagnostics, setDiagnostics] = useState<any>(), [preview, setPreview] = useState<any>(), [params, setParams] = useState({ stage: 'all', publication: '', year: '' }), [users, setUsers] = useState<any[]>([]), [events, setEvents] = useState<any[]>([]), [username, setUsername] = useState(''), [newPassword, setNewPassword] = useState('');
    async function refresh() { try {
        const [j, o] = await Promise.all([api('/api/admin/runs'), api('/api/admin/overview')]);
        setJobs(j.items);
        setIndex(o.index);
        const id = selected || j.items[0]?.id;
        if (id) {
            setSelected(id);
            setJob(await api('/api/admin/runs/' + id));
        }
    }
    catch (e) {
        setError((e as Error).message);
    } }
    useEffect(() => { void refresh(); const timer = setInterval(() => { if (!document.hidden)
        void refresh(); }, 5000); return () => clearInterval(timer); }, [selected]);
    async function accounts() { try {
        const [u, a] = await Promise.all([api('/api/admin/users'), api('/api/admin/audit')]);
        setUsers(u.items);
        setEvents(a.items);
    }
    catch (e) {
        setError((e as Error).message);
    } }
    useEffect(() => { if (tab === 'accounts')
        void accounts(); }, [tab]);
    async function operation(action: string) { setBusy(true); setError(''); setNotice(null); try {
        const r = await api('/api/admin/actions/' + action, 'POST', action === 'resume' || action === 'retry' ? { run_id: selected } : params);
        if (action === 'plan')
            setPreview(r);
        else if (action === 'doctor')
            setDiagnostics(r);
        else {
            setNotice({ key: t("作业请求已提交：{id}。请以实际进度为准。"), values: { id: r.run_id || selected } });
            setPreview(undefined);
            await refresh();
        }
    }
    catch (e) {
        setError((e as Error).message);
    }
    finally {
        setBusy(false);
    } }
    async function userAction(action: string, name = username, active?: boolean) { setError(''); try {
        await api('/api/admin/users/' + action, 'POST', { username: name, password: newPassword, ...(active !== undefined ? { active } : {}) });
        setNewPassword('');
        setNotice({ key: t("账户操作已完成。") });
        await accounts();
    }
    catch (e) {
        setError((e as Error).message);
    } }
    return <main className="workspace"><div className="page-heading"><div><span className="eyebrow">{t("ADMINISTRATOR WORKSPACE")}</span><h1>{t("数据维护工作台")}</h1><p className="muted">{t("管理更新作业、搜索索引与网站账户。")}</p></div><span className="source-pill">{t("仅本机管理入口")}</span></div><nav className="tabs">{[['jobs', t("更新作业")], ['index', t("索引与预检")], ['accounts', t("账户与审计")]].map(([v, l]) => <button className={tab === v ? 'active' : ''} key={v} onClick={() => { setTab(v); setNotice(null); setError(''); }}>{l}</button>)}</nav>{error && <div className="error-box" role="alert">{t(error)}</div>}{notice && <div className="notice" role="status">{t(notice.key, notice.values)}</div>}
 {tab === 'jobs' && <div className="admin-grid"><aside><section className="panel"><h2>{t("启动更新")}</h2><p className="muted">{t("默认覆盖全部刊会，可按需限定范围。")}</p><label>{t("更新阶段")}<select value={params.stage} onChange={e => { setParams({ ...params, stage: e.target.value }); setPreview(undefined); }}>{[['all', t("全部阶段")], ['catalog', t("刊会目录")], ['metadata', t("论文元数据")], ['enrich', t("摘要与关键词")]].map(([v, l]) => <option value={v} key={v}>{l}</option>)}</select></label><label>{t("刊会编号")}<input inputMode="numeric" value={params.publication} placeholder={t("留空表示全部")} onChange={e => { setParams({ ...params, publication: e.target.value }); setPreview(undefined); }}/></label><label>{t("年份")}<input type="number" value={params.year} placeholder={t("留空表示全部")} onChange={e => { setParams({ ...params, year: e.target.value }); setPreview(undefined); }}/></label><button className="wide" disabled={busy} onClick={() => void operation('plan')}>{t("预览更新范围")}</button>{preview && <><div className="preview"><p>{t("范围：")}{params.publication || t("全部刊会")} / {params.year || t("全部年份")} / {stageLabel(params.stage)}</p><p>{t("期刊 ")}{fmt(preview.journals)}{t(" · 会议系列 ")}{fmt(preview.conference_series)}</p><p>{t("历史元数据文件 ")}{fmt(preview.existing_article_files)}</p></div><button className="primary wide" disabled={busy} onClick={() => void operation('update')}>{t("按此范围启动后台作业")}</button></>}</section><section className="panel jobs-list"><h2>{t("最近作业")}</h2>{jobs.map(j => <button key={j.id} className={'job-option ' + (j.id === selected ? 'selected' : '')} onClick={() => setSelected(j.id)}><Badge state={j.status}/><code>{j.id}</code><small>{time(j.created_at)}</small></button>)}</section></aside><section className="panel job-detail"><div className="section-heading"><h2>{t("作业详情")}</h2>{job && <Badge state={job.observed_status || job.status}/>}</div>{job ? <><code className="job-id">{job.id}</code><p className="muted">{t("心跳 ")}{time(job.heartbeat)}{t(" · 阶段 ")}{stageLabel(job.params?.stage || 'all')}</p><div className="job-counts">{['done', 'pending', 'failed', 'blocked', 'deferred'].map(k => <div key={k}><span>{t(statusNames[k] || k)}</span><strong>{fmt(job.counts?.[k])}</strong></div>)}</div><p className="hint">{t("以上为任务数，不是论文数。待办未清零或仍有失败时，不代表全库已完成。")}</p>{job.error && <div className="error-box">{t(job.error)}{t("。受限任务会保留，不会自动循环重试。")}</div>}<div className="actions"><button disabled={busy || ['running', 'queued'].includes(job.status)} onClick={() => void operation('resume')}>{t("恢复待办任务")}</button><button disabled={busy || ['running', 'queued'].includes(job.status)} onClick={() => void operation('retry')}>{t("重试失败 / 受限任务")}</button><button onClick={() => void api('/api/admin/runs/' + selected + '/logs').then(r => setLog(r.log)).catch(e => setError(e.message))}>{t("读取运行日志")}</button></div><details><summary>{t("已导入 / 已抓取记录统计")}</summary><pre>{JSON.stringify(job.stats, null, 2)}</pre></details><h3>{t("失败与受限记录")}</h3>{!job.errors?.length ? <p className="muted">{t("当前没有失败记录。")}</p> : <div className="table-scroll"><table><thead><tr><th>{t("阶段 / 任务")}</th><th>{t("状态")}</th><th>{t("原因")}</th></tr></thead><tbody>{job.errors.map((e: any, i: number) => <tr key={i}><td>{stageLabel(e.kind)}<br /><code>{e.task_key}</code></td><td><Badge state={e.status}/></td><td>{t(e.error)}</td></tr>)}</tbody></table></div>}{!!job.deferred?.length && <details><summary>{t("待后续发布的目录任务")}</summary><pre>{JSON.stringify(job.deferred, null, 2)}</pre></details>}{log && <details open><summary>{t("日志末尾（最多 64 KiB）")}</summary><pre>{log}</pre></details>}</> : <p className="muted">{t("暂无更新作业。")}</p>}</section></div>}
 {tab === 'index' && <><OverviewCards overview={index?.overview}/><div className="admin-grid"><section><IndexStatus index={index}/><section className="panel"><h2>{t("服务预检")}</h2><p className="muted">{t("检查数据库、元数据目录与迁移状态，不触发采集。")}</p><button disabled={busy} onClick={() => void operation('doctor')}>{t("执行预检")}</button>{diagnostics && <pre>{JSON.stringify(diagnostics, null, 2)}</pre>}</section><ResourceSettings api={api}/></section><section className="panel"><h2>{t("字段覆盖")}</h2><table><thead><tr><th>{t("摘要")}</th><th>{t("关键词")}</th><th>{t("论文数")}</th></tr></thead><tbody>{index?.overview?.field_states.map((s, i) => <tr key={i}><td><Badge state={s.abstract_state}/></td><td><Badge state={s.keywords_state}/></td><td>{fmt(s.n)}</td></tr>)}</tbody></table><p className="hint">{t("采样时间：")}{time(index?.overview?.sampled_at)}{t("。索引初次构建与论文元数据补全是两个独立过程。")}</p></section></div></>}
 {tab === 'accounts' && <div className="admin-grid"><section className="panel"><h2>{t("账户操作")}</h2><label>{t("用户名")}<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="off"/></label><label>{t("初始 / 重置密码")}<input value={newPassword} onChange={e => setNewPassword(e.target.value)} type="password" minLength={8} autoComplete="new-password"/></label><p className="hint">{t("仅保存在网站账户系统。新建或重置后须在首次登录时改密。")}</p><div className="actions"><button className="primary" onClick={() => void userAction('create')}>{t("新增读者")}</button><button onClick={() => void userAction('reset')}>{t("重置密码")}</button></div></section><section><div className="panel table-scroll"><h2>{t("网站账户")}</h2><table><thead><tr><th>{t("用户名")}</th><th>{t("权限")}</th><th>{t("状态")}</th><th>{t("操作")}</th></tr></thead><tbody>{users.map(u => <tr key={u.username}><td><button className="text-button" onClick={() => setUsername(u.username)}>{u.username}</button></td><td>{u.role === 'admin' ? t("管理员") : t("读者")}</td><td>{u.active ? t("已启用") : t("已禁用")}{u.must_change ? t(" · 待改密") : ''}</td><td><button onClick={() => void userAction('active', u.username, !u.active)}>{u.active ? t("禁用") : t("启用")}</button></td></tr>)}</tbody></table></div><div className="panel table-scroll"><h2>{t("最近管理操作")}</h2><table><thead><tr><th>{t("时间")}</th><th>{t("操作者")}</th><th>{t("动作")}</th><th>{t("对象")}</th></tr></thead><tbody>{events.map(e => <tr key={e.id}><td>{new Date(e.at * 1000).toLocaleString(locale())}</td><td>{e.actor}</td><td>{auditLabel(e.action)}</td><td>{e.target}</td></tr>)}</tbody></table></div></section></div>}
 </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
