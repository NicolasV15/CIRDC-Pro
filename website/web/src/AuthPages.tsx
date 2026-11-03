import React,{useState} from 'react';
import {t} from './i18n';
import {api,setCsrf} from './api';
import type {User} from './types';

function Illustration(){
 return <svg className="auth-illustration" viewBox="0 0 320 230" aria-hidden="true" focusable="false">
  <rect className="ill-sheet ill-back" x="84" y="20" width="196" height="176" rx="12" transform="rotate(7 182 108)"/>
  <rect className="ill-sheet" x="40" y="34" width="208" height="176" rx="12"/>
  <rect className="ill-accent" x="62" y="58" width="74" height="9" rx="4.5"/>
  <rect className="ill-line" x="62" y="80" width="164" height="6" rx="3"/><rect className="ill-line" x="62" y="94" width="142" height="6" rx="3"/>
  <path className="ill-trace" d="M62 146h30l7-20 12 40 12-40 12 40 12-40 7 20h30"/>
  <circle className="ill-node" cx="62" cy="146" r="4.5"/><circle className="ill-node" cx="204" cy="146" r="4.5"/>
  <rect className="ill-line" x="62" y="182" width="118" height="6" rx="3"/>
 </svg>;
}
export function Login({mode,onLogin}:{mode:string;onLogin:(u:User)=>void}){
 const [name,setName]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{const r=await api('/api/auth/login','POST',{username:name,password});setCsrf(r.csrf);onLogin(r.user);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <main id="main" className="auth-layout">
  <section className="auth-intro"><span className="eyebrow">{t('CIRCUITS · RESEARCH · DISCOVERY')}</span><h1>{t('从一篇论文，')}<br/>{t('开始下一步研究。')}</h1><p>{t('汇集期刊与会议元数据。检索标题、作者、关键词和摘要，查看完整记录与数据覆盖情况。')}</p><Illustration/></section>
  <section className="auth-card" aria-labelledby="login-title"><h2 id="login-title">{mode==='admin'?t('登录管理员工作台'):t('登录文献数据库')}</h2><p className="muted">{t('使用独立的网站账户。首次登录需要修改初始密码。')}</p>
   <form onSubmit={e=>void submit(e)}><label>{t('用户名')}<input name="username" autoComplete="username" required value={name} onChange={e=>setName(e.target.value)}/></label><PasswordInput label={t('密码')} name="password" value={password} onChange={setPassword} autoComplete="current-password"/>{error&&<p className="error" role="alert">{t(error)}</p>}<button className="primary wide" disabled={busy}>{busy?t('正在登录…'):t('登录')}</button></form>
   <p className="hint">{t('账户由管理员开通。忘记密码时请联系管理员。')}</p></section>
 </main>;
}
function PasswordInput({label,name,value,onChange,autoComplete,minLength}:{label:string;name?:string;value:string;onChange:(value:string)=>void;autoComplete:'current-password'|'new-password';minLength?:number}){
 const [visible,setVisible]=useState(false),id=React.useId();
 return <div className="password-field"><label htmlFor={id}>{label}</label><div className="password-input"><input id={id} name={name} type={visible?'text':'password'} autoComplete={autoComplete} minLength={minLength} value={value} onChange={e=>onChange(e.target.value)} required/><button className="password-visibility" type="button" aria-controls={id} aria-pressed={visible} aria-label={(visible?t('隐藏'):t('显示'))+' '+label.split(' · ')[0]} onClick={()=>setVisible(v=>!v)}><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>{visible&&<path d="m3 3 18 18"/>}</svg>{visible?t('隐藏'):t('显示')}</button></div></div>;
}
export function PasswordForm({forced,done,cancel}:{forced:boolean;done:()=>void;cancel:()=>void}){
 const [current,setCurrent]=useState(''),[next,setNext]=useState(''),[confirm,setConfirm]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function submit(e:React.FormEvent){e.preventDefault();if(next!==confirm){setError(t('两次输入的新密码不一致。'));return;}setBusy(true);try{await api('/api/auth/password','POST',{current_password:current,new_password:next});done();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <main id="main" className="password-page">
  <section className="auth-card" aria-labelledby="password-title"><span className="eyebrow">{t('ACCOUNT SECURITY')}</span><h1 id="password-title">{forced?t('设置你自己的密码'):t('修改密码')}</h1><p className="muted">{forced?t('首次登录，请先修改初始密码后继续。'):t('修改后所有已有会话会退出，请使用新密码重新登录。')}</p>
   <form onSubmit={e=>void submit(e)}><PasswordInput label={t('当前密码')} value={current} onChange={setCurrent} autoComplete="current-password"/><PasswordInput label={t('新密码 · 至少 8 个字符')} value={next} onChange={setNext} autoComplete="new-password" minLength={8}/><PasswordInput label={t('再次输入新密码')} value={confirm} onChange={setConfirm} autoComplete="new-password" minLength={8}/>{error&&<p className="error" role="alert">{t(error)}</p>}<div className="actions"><button className="primary" disabled={busy}>{busy?t('保存中…'):t('保存并重新登录')}</button>{!forced&&<button type="button" onClick={cancel}>{t('取消')}</button>}</div></form></section>
 </main>;
}
