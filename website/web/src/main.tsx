import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import {t,useLanguage} from './i18n';
import {api,setCsrf} from './api';
import AppHeader from './AppHeader';
import AgentAccess from './AgentAccessPage';
import AdminPage from './AdminPage';
import ReaderPage from './ReaderPage';
import {Login,PasswordForm} from './AuthPages';
import {AuthorProfile} from './AuthorProfile';
import type {User} from './types';

function App(){
 useLanguage();
 const agentRoute=window.location.pathname==='/developers/ai';
 const profileRoute=window.location.pathname.match(/^\/authors\/(ieee)\/([0-9]{1,64})$/);
 const [user,setUser]=useState<User|null>(null),[mode,setMode]=useState('reader'),[loading,setLoading]=useState(true),[error,setError]=useState(''),[change,setChange]=useState(false),[authRequired,setAuthRequired]=useState(true);
 async function session(){try{
  const r=await api('/api/auth/session');
  setCsrf(r.csrf);setUser(r.user);setMode(r.interface);
  setAuthRequired(r.interface==='admin'||r.authentication_required!==false);
 }catch{
  setError(t('暂时无法连接服务，请刷新页面。'));
 }finally{
  setLoading(false);
 }}
 useEffect(()=>{if(agentRoute){setAuthRequired(false);setLoading(false);}else{void session();}const expired=()=>{setUser(null);void session();};window.addEventListener('cirdc-auth-expired',expired);return()=>window.removeEventListener('cirdc-auth-expired',expired);},[]);
 async function logout(){try{
  await api('/api/auth/logout','POST',{});
  setUser(null);setChange(false);
  await session();
 }catch(e){
  setError(String((e as Error).message));
 }}
 const publicReader=mode==='reader'&&!authRequired;
 if(loading)return <div className="app-loading" role="status"><span className="spinner" aria-hidden="true"/>{t('正在连接文献数据库…')}</div>;
 return <>
  <a className="skip-link" href="#main">{t('跳到主要内容')}</a>
  <AppHeader mode={mode} user={user} publicReader={publicReader} current={agentRoute?'ai':'search'} onPassword={()=>setChange(true)} onLogout={()=>void logout()}/>
  {error&&<div className="global-error" role="alert"><span>{t(error)}</span><button type="button" className="ghost" onClick={()=>setError('')}>{t('关闭')}</button></div>}
  {agentRoute?<AgentAccess/>:!publicReader&&!user?<Login mode={mode} onLogin={u=>{setUser(u);setCsrf(u.csrf);}}/>:!publicReader&&(user?.must_change||change)?<PasswordForm forced={!!user?.must_change} done={()=>{setChange(false);setUser(null);void session();}} cancel={()=>setChange(false)}/>:mode==='admin'?<AdminPage/>:profileRoute?<AuthorProfile source={profileRoute[1]} authorId={profileRoute[2]} fetcher={api}/>:<ReaderPage/>}
  <footer className="app-footer"><span>{t('CIRDC Pro ')}</span><span aria-hidden="true">·</span><span>{t(' IEEE 期刊与会议元数据 ')}</span>{mode==='reader'&&<><span aria-hidden="true">·</span><a href="/developers/ai">{t('AI 接入')}</a></>}</footer>
 </>;
}
createRoot(document.getElementById('root')!).render(<App/>);
