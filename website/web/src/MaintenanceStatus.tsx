import {useEffect,useState} from 'react';
import {t} from './i18n';
export default function MaintenanceStatus({api}:{api:(path:string)=>Promise<any>}){
 const [value,setValue]=useState<any>(),[error,setError]=useState('');
 useEffect(()=>{let active=true;async function read(){try{const data=await api('/api/admin/maintenance');if(active){setValue(data);setError('');}}catch{if(active)setError(t('暂时无法读取采集状态'));}}
 void read();const timer=setInterval(()=>void read(),15000);return()=>{active=false;clearInterval(timer);};},[api]);
 return <section className="panel"><h2>{t('采集与补全')}</h2>{error&&<p role="status">{error}</p>}
 {value&&<><p>{t('服务状态')}：{value.service||t('未配置')} · {t('待提交结果')}：{value.pending_results??'—'}</p>
 <table><thead><tr><th>{t('任务')}</th><th>{t('已完成')}</th><th>{t('待处理')}</th><th>{t('失败 / 受限')}</th><th>{t('待发布')}</th></tr></thead>
 <tbody>{Object.entries(value.jobs||{}).map(([name,job]:[string,any])=><tr key={name}><td>{name}</td><td>{job.counts?.done??0}</td><td>{job.counts?.pending??0}</td><td>{(job.counts?.failed||0)+' / '+(job.counts?.blocked||0)}</td><td>{job.counts?.exports_pending??0}</td></tr>)}</tbody></table>
 <p className="hint">{t('任务进度与论文覆盖率分别统计。')}</p>
 <table><thead><tr><th>{t('节点')}</th><th>{t('最近心跳')}</th></tr></thead><tbody>{(value.workers||[]).map((worker:any)=><tr key={worker.id}><td>{worker.id}</td><td>{new Date(worker.last_seen*1000).toLocaleString()}</td></tr>)}</tbody></table>
 <p>{t('出口数量')}：{value.exits?.length??0} · {t('预算许可次数')}：{(value.exits||[]).reduce((n:number,row:any)=>n+row.requests,0)}</p></>}
 </section>;
}
