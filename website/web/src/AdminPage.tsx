import {useEffect,useState} from 'react';
import {t,locale,stageLabel,auditLabel} from './i18n';
import {api} from './api';
import {fmt,time,statusNames} from './format';
import Icon from './Icon';
import {ResourceSettings} from './ResourceSettings';
import MaintenanceStatus from './MaintenanceStatus';
import {IndexStatus,OverviewCards} from './Overview';
import type {Index} from './types';

export function Badge({state}:{state:string}){return <span className={'badge '+state}>{t(statusNames[state]||state)}</span>;}
export default function AdminPage(){
 const [tab,setTab]=useState('jobs'),[jobs,setJobs]=useState<any[]>([]),[selected,setSelected]=useState(''),[job,setJob]=useState<any>(),[index,setIndex]=useState<Index>(),[error,setError]=useState(''),[notice,setNotice]=useState<{key:string;values?:Record<string,string>}|null>(null),[busy,setBusy]=useState(false),[log,setLog]=useState(''),[diagnostics,setDiagnostics]=useState<any>(),[preview,setPreview]=useState<any>(),[params,setParams]=useState({stage:'all',publication:'',year:''}),[users,setUsers]=useState<any[]>([]),[events,setEvents]=useState<any[]>([]),[username,setUsername]=useState(''),[newPassword,setNewPassword]=useState('');
 async function refresh(){try{
  const [j,o]=await Promise.all([api('/api/admin/runs'),api('/api/admin/overview')]);
  setJobs(j.items);
  setIndex(o.index);
  const id=selected||j.items[0]?.id;
  if(id){setSelected(id);setJob(await api('/api/admin/runs/'+id));}
 }catch(e){setError((e as Error).message);}}
 useEffect(()=>{void refresh();const timer=setInterval(()=>{if(!document.hidden)void refresh();},5000);return()=>clearInterval(timer);},[selected]);
 async function accounts(){try{const [u,a]=await Promise.all([api('/api/admin/users'),api('/api/admin/audit')]);setUsers(u.items);setEvents(a.items);}catch(e){setError((e as Error).message);}}
 useEffect(()=>{if(tab==='accounts')void accounts();},[tab]);
 async function operation(action:string){setBusy(true);setError('');setNotice(null);try{
  const r=await api('/api/admin/actions/'+action,'POST',action==='resume'||action==='retry'?{run_id:selected}:params);
  if(action==='plan')setPreview(r);
  else if(action==='doctor')setDiagnostics(r);
  else{setNotice({key:t('作业请求已提交：{id}。请以实际进度为准。'),values:{id:r.run_id||selected}});setPreview(undefined);await refresh();}
 }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function userAction(action:string,name=username,active?:boolean){setError('');try{
  await api('/api/admin/users/'+action,'POST',{username:name,password:newPassword,...(active!==undefined?{active}:{})});
  setNewPassword('');setNotice({key:t('账户操作已完成。')});await accounts();
 }catch(e){setError((e as Error).message);}}
 const tabs:[string,string][]=[['jobs',t('更新作业')],['index',t('索引与预检')],['accounts',t('账户与审计')]];
 const running=!!job&&['running','queued'].includes(job.status);
 return <main id="main" className="workspace admin-workspace">
  <div className="page-heading"><div><h1>{t('数据维护工作台')}</h1><p className="muted">{t('管理更新作业、搜索索引与网站账户。')}</p></div><span className="source-pill"><Icon name="lock"/>{t('仅本机管理入口')}</span></div>
  <nav className="tabs" aria-label={t('工作台分区')}>{tabs.map(([v,l])=><button type="button" className={tab===v?'active':''} aria-current={tab===v?'page':undefined} key={v} onClick={()=>{setTab(v);setNotice(null);setError('');}}>{l}</button>)}</nav>
  {error&&<div className="error-box" role="alert">{t(error)}</div>}{notice&&<div className="notice" role="status">{t(notice.key,notice.values)}</div>}
  {tab==='jobs'&&<div className="admin-grid"><aside className="admin-aside">
   <section className="panel"><h2>{t('启动更新')}</h2><p className="muted">{t('默认覆盖全部刊会，可按需限定范围。')}</p>
    <label>{t('更新阶段')}<select value={params.stage} onChange={e=>{setParams({...params,stage:e.target.value});setPreview(undefined);}}>{[['all',t('全部阶段')],['catalog',t('刊会目录')],['metadata',t('论文元数据')],['enrich',t('摘要与关键词')]].map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label>
    <label>{t('刊会编号')}<input inputMode="numeric" value={params.publication} placeholder={t('留空表示全部')} onChange={e=>{setParams({...params,publication:e.target.value});setPreview(undefined);}}/></label>
    <label>{t('年份')}<input type="number" value={params.year} placeholder={t('留空表示全部')} onChange={e=>{setParams({...params,year:e.target.value});setPreview(undefined);}}/></label>
    <button className="wide" disabled={busy} onClick={()=>void operation('plan')}>{t('预览更新范围')}</button>
    {preview&&<><div className="preview"><p><span>{t('范围：')}</span>{params.publication||t('全部刊会')} / {params.year||t('全部年份')} / {stageLabel(params.stage)}</p><p>{t('期刊 ')}{fmt(preview.journals)}{t(' · 会议系列 ')}{fmt(preview.conference_series)}</p><p>{t('历史元数据文件 ')}{fmt(preview.existing_article_files)}</p></div><button className="primary wide" disabled={busy} onClick={()=>void operation('update')}>{t('按此范围启动后台作业')}</button></>}
   </section>
   {jobs.length>0&&<section className="panel jobs-list"><h2>{t('最近作业')}</h2>{jobs.map(j=><button key={j.id} type="button" className={'job-option '+(j.id===selected?'selected':'')} aria-pressed={j.id===selected} onClick={()=>setSelected(j.id)}><span className="job-option-top"><Badge state={j.status}/><small>{time(j.created_at)}</small></span><code>{j.id}</code></button>)}</section>}
  </aside><section className="panel job-detail"><div className="section-heading"><h2>{t('作业详情')}</h2>{job&&<Badge state={job.observed_status||job.status}/>}</div>{job?<>
   <code className="job-id">{job.id}</code><p className="muted">{t('心跳 ')}{time(job.heartbeat)}{t(' · 阶段 ')}{stageLabel(job.params?.stage||'all')}</p>
   <div className="job-counts">{['done','pending','failed','blocked','deferred'].map(k=><div key={k} className={'job-count job-count-'+k}><span>{t(statusNames[k]||k)}</span><strong>{fmt(job.counts?.[k])}</strong></div>)}</div>
   <p className="hint">{t('以上为任务数，不是论文数。待办未清零或仍有失败时，不代表全库已完成。')}</p>
   {job.error&&<div className="error-box">{t(job.error)}{t('。受限任务会保留，不会自动循环重试。')}</div>}
   <div className="actions"><button disabled={busy||running} onClick={()=>void operation('resume')}>{t('恢复待办任务')}</button><button disabled={busy||running} onClick={()=>void operation('retry')}>{t('重试失败 / 受限任务')}</button><button onClick={()=>void api('/api/admin/runs/'+selected+'/logs').then(r=>setLog(r.log)).catch(e=>setError(e.message))}>{t('读取运行日志')}</button></div>
   <details><summary>{t('已导入 / 已抓取记录统计')}</summary><pre>{JSON.stringify(job.stats,null,2)}</pre></details>
   <h3>{t('失败与受限记录')}</h3>{!job.errors?.length?<p className="muted">{t('当前没有失败记录。')}</p>:<div className="table-scroll"><table><thead><tr><th>{t('阶段 / 任务')}</th><th>{t('状态')}</th><th>{t('原因')}</th></tr></thead><tbody>{job.errors.map((e:any,i:number)=><tr key={i}><td>{stageLabel(e.kind)}<br/><code>{e.task_key}</code></td><td><Badge state={e.status}/></td><td>{t(e.error)}</td></tr>)}</tbody></table></div>}
   {!!job.deferred?.length&&<details><summary>{t('待后续发布的目录任务')}</summary><pre>{JSON.stringify(job.deferred,null,2)}</pre></details>}
   {log&&<details open><summary>{t('日志末尾（最多 64 KiB）')}</summary><pre>{log}</pre></details>}
  </>:<p className="muted">{t('暂无更新作业。')}</p>}</section></div>}
  {tab==='index'&&<><OverviewCards overview={index?.overview}/><div className="admin-grid admin-grid-index"><section className="admin-column"><IndexStatus index={index}/><section className="panel"><h2>{t('服务预检')}</h2><p className="muted">{t('检查数据库、元数据目录与迁移状态，不触发采集。')}</p><button disabled={busy} onClick={()=>void operation('doctor')}>{t('执行预检')}</button>{diagnostics&&<pre>{JSON.stringify(diagnostics,null,2)}</pre>}</section><ResourceSettings api={api}/><MaintenanceStatus api={api}/></section>
   <section className="panel"><h2>{t('字段覆盖')}</h2><div className="table-scroll"><table><thead><tr><th>{t('摘要')}</th><th>{t('关键词')}</th><th className="numeric">{t('论文数')}</th></tr></thead><tbody>{index?.overview?.field_states.map((s,i)=><tr key={i}><td><Badge state={s.abstract_state}/></td><td><Badge state={s.keywords_state}/></td><td className="numeric">{fmt(s.n)}</td></tr>)}</tbody></table></div><p className="hint">{t('采样时间：')}{time(index?.overview?.sampled_at)}{t('。索引初次构建与论文元数据补全是两个独立过程。')}</p></section></div></>}
  {tab==='accounts'&&<div className="admin-grid"><aside className="admin-aside"><section className="panel"><h2>{t('账户操作')}</h2><label>{t('用户名')}<input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="off"/></label><label>{t('初始 / 重置密码')}<input value={newPassword} onChange={e=>setNewPassword(e.target.value)} type="password" minLength={8} autoComplete="new-password"/></label><p className="hint">{t('仅保存在网站账户系统。新建或重置后须在首次登录时改密。')}</p><div className="actions"><button className="primary" onClick={()=>void userAction('create')}>{t('新增读者')}</button><button onClick={()=>void userAction('reset')}>{t('重置密码')}</button></div></section></aside>
   <section className="admin-column"><div className="panel"><h2>{t('网站账户')}</h2><div className="table-scroll"><table><thead><tr><th>{t('用户名')}</th><th>{t('权限')}</th><th>{t('状态')}</th><th>{t('操作')}</th></tr></thead><tbody>{users.map(u=><tr key={u.username}><td><button type="button" className="text-button" onClick={()=>setUsername(u.username)}>{u.username}</button></td><td>{u.role==='admin'?t('管理员'):t('读者')}</td><td><span className={'badge '+(u.active?'complete':'paused')}>{u.active?t('已启用'):t('已禁用')}</span>{u.must_change?t(' · 待改密'):''}</td><td><button type="button" className="compact" onClick={()=>void userAction('active',u.username,!u.active)}>{u.active?t('禁用'):t('启用')}</button></td></tr>)}</tbody></table></div></div>
   <div className="panel"><h2>{t('最近管理操作')}</h2><div className="table-scroll"><table><thead><tr><th>{t('时间')}</th><th>{t('操作者')}</th><th>{t('动作')}</th><th>{t('对象')}</th></tr></thead><tbody>{events.map(e=><tr key={e.id}><td>{new Date(e.at*1000).toLocaleString(locale())}</td><td>{e.actor}</td><td>{auditLabel(e.action)}</td><td>{e.target}</td></tr>)}</tbody></table></div></div></section></div>}
 </main>;
}
