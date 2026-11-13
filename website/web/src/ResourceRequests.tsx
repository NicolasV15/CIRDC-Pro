import {useEffect,useState} from 'react';
import {t} from './i18n';
type API=(path:string,method?:string,data?:unknown)=>Promise<any>;
export function ResourceRequests({api,jobs=[]}:{api:API;jobs?:any[]}){
 const [value,setValue]=useState<any>(),[error,setError]=useState('');
 useEffect(()=>{let active=true;async function load(){try{const v=await api('/api/admin/resource-requests');if(active){setValue(v);setError('');}}catch{if(active)setError('接口诊断暂不可读取');}}void load();const timer=setInterval(()=>void load(),5000);return()=>{active=false;clearInterval(timer);};},[api]);
 return <div className="resource-node-diagnostics"><h3>{t('API 请求与回执诊断')}</h3><p className="hint">{t('接口超时不代表后台任务失败。按回执 ID、任务 ID 和节点 ID 核对；没有记录的关联保持未知。')}</p>{error&&<p role="alert">{t(error)}</p>}
  {value&&<><h4>{t('最近回执')}</h4><table><thead><tr><th>{t('论文编号')}</th><th>{t('回执 ID')}</th><th>{t('任务 ID 与历史')}</th></tr></thead><tbody>{(value.requests||[]).map((r:any)=><tr key={r.id} id={'resource-receipt-'+r.id}><td>{r.number}</td><td><code>{r.id}</code></td><td>{Object.values(r.references_json||{}).flatMap((ref:any)=>ref?.jobs||[]).map((id:any)=><div key={id}>{jobs.some(j=>j.id===id)?<a href={'#resource-job-'+id}><code>{id}</code></a>:<code>{id}</code>}</div>)}<details><summary>{t('关联记录')}</summary><pre>{JSON.stringify({references:r.references_json,history:r.history,api_request_ids:(value.events||[]).filter((e:any)=>e.detail.request_id===r.id&&e.detail.id).map((e:any)=>e.detail.id)},null,2)}</pre></details></td></tr>)}</tbody></table>
  <h4>{t('接口错误与原始异常（已脱敏）')}</h4><table><thead><tr><th>{t('时间')}</th><th>{t('回执 ID')}</th><th>{t('详情')}</th></tr></thead><tbody>{(value.events||[]).map((e:any)=><tr key={e.id}><td>{new Date(e.at*1000).toLocaleString()}</td><td>{(value.requests||[]).some((r:any)=>r.id===e.target)?<a href={'#resource-receipt-'+e.target}><code>{e.target}</code></a>:<code>{e.target||'—'}</code>}</td><td><details><summary>{e.detail.phase||e.action} · {e.detail.error||e.detail.number}</summary><pre>{JSON.stringify(e.detail,null,2)}</pre></details></td></tr>)}</tbody></table></>}
 </div>;
}
