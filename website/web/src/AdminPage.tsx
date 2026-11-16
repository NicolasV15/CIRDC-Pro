import {useEffect,useState,type ReactNode} from 'react';
import {t,locale,stageLabel,auditLabel} from './i18n';
import {api} from './api';
import {fmt,time,statusNames} from './format';
import Icon,{type IconName} from './Icon';
import {ResourceSettings} from './ResourceSettings';
import MaintenanceStatus from './MaintenanceStatus';
import {IndexStatus,OverviewCards} from './Overview';
import type {Index} from './types';
import './admin.css';

export function Badge({state}:{state:string}){return <span className={'badge '+state}>{t(statusNames[state]||state)}</span>;}
type Section='overview'|'jobs'|'index'|'resources'|'accounts'|'audit';
const sections:[Section,string,IconName][]=[['overview','概览','database'],['jobs','更新作业','server'],['index','索引与预检','search'],['resources','资料与采集','file'],['accounts','账户','user'],['audit','审计记录','book']];
function sectionFromHash():Section{const value=location.hash.slice(1) as Section;return sections.some(([key])=>key===value)?value:'overview';}
type Confirm={key:string;label:string;run:()=>Promise<void>};

/** One button that asks again before an action that changes jobs or accounts. */
function ConfirmButton({id,confirm,setConfirm,label,confirmLabel,disabled,primary,onConfirm}:{id:string;confirm:Confirm|null;setConfirm:(value:Confirm|null)=>void;label:string;confirmLabel:string;disabled?:boolean;primary?:boolean;onConfirm:()=>Promise<void>}){
 if(confirm?.key===id)return <span className="admin-confirm" role="group" aria-label={confirmLabel}><button type="button" className="danger" disabled={disabled} onClick={()=>{setConfirm(null);void onConfirm();}}>{confirmLabel}</button><button type="button" onClick={()=>setConfirm(null)}>{t('取消')}</button></span>;
 return <button type="button" className={primary?'primary':undefined} disabled={disabled} onClick={()=>setConfirm({key:id,label:confirmLabel,run:onConfirm})}>{label}</button>;
}
function Summary({label,value,state,detail,onOpen}:{label:string;value:ReactNode;state?:string;detail?:ReactNode;onOpen?:()=>void}){
 return <section className="panel admin-summary"><h3>{label}</h3><div className="admin-summary-value">{value}{state&&<Badge state={state}/>}</div>{detail&&<p className="muted">{detail}</p>}{onOpen&&<button type="button" className="text-button" onClick={onOpen}>{t('查看')}<Icon name="right"/></button>}</section>;
}

export default function AdminPage({current}:{current?:string}){
 const [section,setSection]=useState<Section>(sectionFromHash),[jobs,setJobs]=useState<any[]|null>(null),[selected,setSelected]=useState(''),[job,setJob]=useState<any>(),[index,setIndex]=useState<Index>();
 const [error,setError]=useState(''),[notice,setNotice]=useState<{key:string;values?:Record<string,string>}|null>(null),[busy,setBusy]=useState(false),[log,setLog]=useState(''),[diagnostics,setDiagnostics]=useState<any>(),[preview,setPreview]=useState<any>();
 const [params,setParams]=useState({stage:'all',publication:'',year:''}),[users,setUsers]=useState<any[]|null>(null),[events,setEvents]=useState<any[]|null>(null),[maintenance,setMaintenance]=useState<any>();
 const [username,setUsername]=useState(''),[newPassword,setNewPassword]=useState(''),[filter,setFilter]=useState(''),[confirm,setConfirm]=useState<Confirm|null>(null);
 async function refresh(){try{
  const [j,o]=await Promise.all([api('/api/admin/runs'),api('/api/admin/overview')]);
  setJobs(j.items);setIndex(o.index);
  const id=selected||j.items[0]?.id;
  if(id){setSelected(id);setJob(await api('/api/admin/runs/'+id));}else setJob(undefined);
 }catch(e){setError((e as Error).message);}}
 useEffect(()=>{void refresh();const timer=setInterval(()=>{if(!document.hidden)void refresh();},5000);return()=>clearInterval(timer);},[selected]);
 async function accounts(){try{const [u,a]=await Promise.all([api('/api/admin/users'),api('/api/admin/audit')]);setUsers(u.items);setEvents(a.items);}catch(e){setError((e as Error).message);}}
 useEffect(()=>{void accounts();void api('/api/admin/maintenance').then(setMaintenance).catch(()=>setMaintenance(null));},[]);
 useEffect(()=>{const pop=()=>setSection(sectionFromHash());window.addEventListener('hashchange',pop);return()=>window.removeEventListener('hashchange',pop);},[]);
 function open(next:Section){setSection(next);setNotice(null);setError('');setConfirm(null);if(location.hash!=='#'+next)history.pushState({},'','#'+next);document.getElementById('admin-section-title')?.focus();}
 async function operation(action:string){setBusy(true);setError('');setNotice(null);try{
  const r=await api('/api/admin/actions/'+action,'POST',action==='resume'||action==='retry'?{run_id:selected}:params);
  if(action==='plan')setPreview(r);
  else if(action==='doctor')setDiagnostics(r);
  else{setNotice({key:t('作业已提交：{id}'),values:{id:r.run_id||selected}});setPreview(undefined);await refresh();}
 }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function userAction(action:string,name=username,active?:boolean){setError('');setNotice(null);try{
  await api('/api/admin/users/'+action,'POST',{username:name,password:newPassword,...(active!==undefined?{active}:{})});
  setNewPassword('');setNotice({key:t('账户操作已完成。')});await accounts();
 }catch(e){setError((e as Error).message);}}
 const running=!!job&&['running','queued'].includes(job.status),latest=jobs?.[0];
 const failing=(jobs||[]).filter(j=>['failed','blocked','interrupted'].includes(j.status)).length;
 const visibleUsers=(users||[]).filter(u=>!filter||u.username.includes(filter.trim().toLowerCase()));
 const title=sections.find(([key])=>key===section)![1];
 return <main id="main" className="workspace admin-workspace admin-shell">
  <nav className="admin-nav" aria-label={t('工作台分区')}><span className="admin-nav-scope"><Icon name="lock"/>{t('仅本机管理入口')}</span>
   {sections.map(([key,label,icon])=><a key={key} href={'#'+key} aria-current={section===key?'page':undefined} onClick={e=>{e.preventDefault();open(key);}}><Icon name={icon}/>{t(label)}{key==='jobs'&&failing>0&&<span className="count-badge admin-alert">{failing}</span>}</a>)}
  </nav>
  <div className="admin-content">
   <header className="admin-heading"><h1 id="admin-section-title" tabIndex={-1}>{t(title)}</h1></header>
   {error&&<div className="error-box" role="alert">{t(error)}</div>}{notice&&<div className="notice" role="status">{t(notice.key,notice.values)}</div>}
   {section==='overview'&&<div className="admin-summaries">
    <Summary label={t('最新作业')} value={latest?<code>{latest.id.slice(0,8)}</code>:t('暂无作业')} state={latest?.status} detail={latest?time(latest.created_at):undefined} onOpen={()=>open('jobs')}/>
    <Summary label={t('失败或受限作业')} value={fmt(failing)} onOpen={()=>open('jobs')}/>
    <Summary label={t('搜索索引')} value={index?.overview?fmt(index.overview.papers):'—'} state={index?.phase} detail={t('索引中的论文记录')} onOpen={()=>open('index')}/>
    <Summary label={t('采集与补全')} value={maintenance?.service||t('未配置')} detail={maintenance?t('待提交结果 {n}',{n:String(maintenance.pending_results??'—')}):maintenance===null?t('暂时无法读取采集状态'):undefined} onOpen={()=>open('resources')}/>
    <Summary label={t('网站账户')} value={users?fmt(users.length):'—'} detail={users?t('自主注册 {self} · 已停用 {disabled}',{self:String(users.filter(u=>u.origin==='self').length),disabled:String(users.filter(u=>!u.active).length)}):undefined} onOpen={()=>open('accounts')}/>
   </div>}
   {section==='jobs'&&<div className="admin-grid"><aside className="admin-aside">
    <section className="panel"><h2>{t('启动更新')}</h2>
     <label>{t('更新阶段')}<select value={params.stage} onChange={e=>{setParams({...params,stage:e.target.value});setPreview(undefined);}}>{[['all',t('全部阶段')],['catalog',t('刊会目录')],['metadata',t('论文元数据')],['enrich',t('摘要与关键词')]].map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label>
     <label>{t('刊会编号')}<input inputMode="numeric" value={params.publication} placeholder={t('留空表示全部')} onChange={e=>{setParams({...params,publication:e.target.value});setPreview(undefined);}}/></label>
     <label>{t('年份')}<input type="number" value={params.year} placeholder={t('留空表示全部')} onChange={e=>{setParams({...params,year:e.target.value});setPreview(undefined);}}/></label>
     <button className="wide" disabled={busy} onClick={()=>void operation('plan')}>{t('预览更新范围')}</button>
     {preview&&<><div className="preview"><p><span>{t('范围：')}</span>{params.publication||t('全部刊会')} / {params.year||t('全部年份')} / {stageLabel(params.stage)}</p><p>{t('期刊 ')}{fmt(preview.journals)}{t(' · 会议系列 ')}{fmt(preview.conference_series)}</p><p>{t('历史元数据文件 ')}{fmt(preview.existing_article_files)}</p></div>
      <ConfirmButton id="update" confirm={confirm} setConfirm={setConfirm} primary disabled={busy} label={t('按此范围启动后台作业')} confirmLabel={t('确认启动后台作业')} onConfirm={()=>operation('update')}/></>}
    </section>
    <section className="panel jobs-list"><h2>{t('最近作业')}</h2>{jobs===null?<p className="muted" role="status">{t('正在读取…')}</p>:!jobs.length?<p className="muted">{t('暂无更新作业。')}</p>:jobs.map(j=><button key={j.id} type="button" className={'job-option '+(j.id===selected?'selected':'')} aria-pressed={j.id===selected} onClick={()=>{setSelected(j.id);setLog('');setConfirm(null);}}><span className="job-option-top"><Badge state={j.status}/><small>{time(j.created_at)}</small></span><code>{j.id}</code></button>)}</section>
   </aside><section className="panel job-detail"><div className="section-heading"><h2>{t('作业详情')}</h2>{job&&<Badge state={job.observed_status||job.status}/>}</div>{job?<>
    <code className="job-id">{job.id}</code><p className="muted">{t('心跳 ')}{time(job.heartbeat)}{t(' · 阶段 ')}{stageLabel(job.params?.stage||'all')}</p>
    <div className="job-counts">{['done','pending','failed','blocked','deferred'].map(k=><div key={k} className={'job-count job-count-'+k}><span>{t(statusNames[k]||k)}</span><strong>{fmt(job.counts?.[k])}</strong></div>)}</div>
    <p className="hint">{t('单位：任务数')}</p>
    {job.error&&<div className="error-box">{t(job.error)}</div>}
    <div className="actions">
     <ConfirmButton id="resume" confirm={confirm} setConfirm={setConfirm} disabled={busy||running} label={t('恢复待办任务')} confirmLabel={t('确认恢复待办任务')} onConfirm={()=>operation('resume')}/>
     <ConfirmButton id="retry" confirm={confirm} setConfirm={setConfirm} disabled={busy||running} label={t('重试失败 / 受限任务')} confirmLabel={t('确认重试失败 / 受限任务')} onConfirm={()=>operation('retry')}/>
     <button onClick={()=>void api('/api/admin/runs/'+selected+'/logs').then(r=>setLog(r.log)).catch(e=>setError(e.message))}>{t('读取运行日志')}</button>
    </div>
    <details><summary>{t('已导入 / 已抓取记录统计')}</summary><pre>{JSON.stringify(job.stats,null,2)}</pre></details>
    <h3>{t('失败与受限记录')}</h3>{!job.errors?.length?<p className="muted">{t('当前没有失败记录。')}</p>:<div className="table-scroll"><table><thead><tr><th>{t('阶段 / 任务')}</th><th>{t('状态')}</th><th>{t('原因')}</th></tr></thead><tbody>{job.errors.map((e:any,i:number)=><tr key={i}><td>{stageLabel(e.kind)}<br/><code>{e.task_key}</code></td><td><Badge state={e.status}/></td><td>{t(e.error)}</td></tr>)}</tbody></table></div>}
    {!!job.deferred?.length&&<details><summary>{t('待后续发布的目录任务')}</summary><pre>{JSON.stringify(job.deferred,null,2)}</pre></details>}
    {log&&<details open><summary>{t('日志末尾（最多 64 KiB）')}</summary><pre>{log}</pre></details>}
   </>:<p className="muted">{jobs===null?t('正在读取…'):t('暂无更新作业。')}</p>}</section></div>}
   {section==='index'&&<><OverviewCards overview={index?.overview}/><div className="admin-grid admin-grid-index"><section className="admin-column"><IndexStatus index={index}/><section className="panel"><h2>{t('服务预检')}</h2><p className="muted">{t('检查数据库、目录与迁移状态。')}</p><button disabled={busy} onClick={()=>void operation('doctor')}>{t('执行预检')}</button>{diagnostics&&<pre>{JSON.stringify(diagnostics,null,2)}</pre>}</section></section>
    <section className="panel"><h2>{t('字段覆盖')}</h2>{!index?.overview?.field_states?.length?<p className="muted">{t('暂无字段统计。')}</p>:<div className="table-scroll"><table><thead><tr><th>{t('摘要')}</th><th>{t('关键词')}</th><th className="numeric">{t('论文数')}</th></tr></thead><tbody>{index.overview.field_states.map((s,i)=><tr key={i}><td><Badge state={s.abstract_state}/></td><td><Badge state={s.keywords_state}/></td><td className="numeric">{fmt(s.n)}</td></tr>)}</tbody></table></div>}<p className="hint">{t('采样时间：')}{time(index?.overview?.sampled_at)}</p></section></div></>}
   {section==='resources'&&<div className="admin-stack"><MaintenanceStatus api={api}/><ResourceSettings api={api}/></div>}
   {section==='accounts'&&<div className="admin-grid"><aside className="admin-aside"><section className="panel"><h2>{t('新增读者 / 重置密码')}</h2><label>{t('用户名')}<input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="off"/></label><label>{t('初始 / 重置密码')}<input value={newPassword} onChange={e=>setNewPassword(e.target.value)} type="password" minLength={8} autoComplete="new-password"/></label><p className="hint">{t('新建或重置后须在首次登录时改密。')}</p>
    <div className="actions"><button className="primary" disabled={!username||newPassword.length<8} onClick={()=>void userAction('create')}>{t('新增读者')}</button><ConfirmButton id={'reset:'+username} confirm={confirm} setConfirm={setConfirm} disabled={!username||newPassword.length<8} label={t('重置密码')} confirmLabel={t('确认重置 {name} 的密码',{name:username})} onConfirm={()=>userAction('reset')}/></div></section></aside>
    <section className="panel admin-column"><div className="section-heading"><h2>{t('网站账户')}</h2><input className="admin-filter" type="search" aria-label={t('按用户名筛选账户')} placeholder={t('筛选用户名')} value={filter} onChange={e=>setFilter(e.target.value)}/></div>
     {users===null?<p className="muted" role="status">{t('正在读取…')}</p>:!visibleUsers.length?<p className="muted">{t('没有匹配的账户。')}</p>:<div className="table-scroll"><table><thead><tr><th>{t('用户名')}</th><th>{t('权限')}</th><th>{t('来源')}</th><th>{t('状态')}</th><th>{t('操作')}</th></tr></thead><tbody>{visibleUsers.map(u=><tr key={u.username}><td><button type="button" className="text-button" onClick={()=>setUsername(u.username)}>{u.username}</button></td><td>{u.role==='admin'?t('管理员'):t('读者')}</td><td>{u.origin==='self'?t('自主注册'):t('管理员开通')}</td><td><span className={'badge '+(u.active?'complete':'paused')}>{u.active?t('已启用'):t('已禁用')}</span>{u.must_change?t(' · 待改密'):''}</td>
      <td>{u.username===current?<span className="muted">{t('当前账户')}</span>:u.active?<ConfirmButton id={'disable:'+u.username} confirm={confirm} setConfirm={setConfirm} label={t('禁用')} confirmLabel={t('确认禁用')} onConfirm={()=>userAction('active',u.username,false)}/>:<button type="button" className="compact" onClick={()=>void userAction('active',u.username,true)}>{t('启用')}</button>}</td></tr>)}</tbody></table></div>}</section></div>}
   {section==='audit'&&<section className="panel"><h2>{t('最近管理操作')}</h2>{events===null?<p className="muted" role="status">{t('正在读取…')}</p>:!events.length?<p className="muted">{t('暂无记录。')}</p>:<div className="table-scroll"><table><thead><tr><th>{t('时间')}</th><th>{t('操作者')}</th><th>{t('动作')}</th><th>{t('对象')}</th></tr></thead><tbody>{events.map(e=><tr key={e.id}><td>{new Date(e.at*1000).toLocaleString(locale())}</td><td>{e.actor}</td><td>{auditLabel(e.action)}</td><td>{e.target}</td></tr>)}</tbody></table></div>}</section>}
  </div>
 </main>;
}
