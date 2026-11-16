import {lazy,memo,Suspense,useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import './personal.css';
import {t,useLanguage} from './i18n';
import {api,setCsrf} from './api';
import AppHeader from './AppHeader';
import AdminPage from './AdminPage';
import ReaderPage from './ReaderPage';
import {Login,PasswordForm,Register} from './AuthPages';
import {returnPath,setAccount,signInHref} from './account';
import {forgetFavorites} from './favorites';
import {AuthorProfile} from './AuthorProfile';
import {agentAccessEntry} from './agentAccessEntry';
import type {User} from './types';

const AgentAccess=lazy(()=>import('./AgentAccessPage'));
const AccountPage=lazy(()=>import('./AccountPage'));
const FavoritesPage=lazy(()=>import('./FavoritesPage'));
const Reader=memo(ReaderPage);
// Restore the legacy link's author route before mounting any page. Mounting the
// browse page here would replace the URL before the modal's first render.
const agentEntry=agentAccessEntry(window.location.href,document.referrer);
if(agentEntry.returnPath)history.replaceState(history.state,'',agentEntry.returnPath);

function App(){
 useLanguage();
 const [agentOpen,setAgentOpen]=useState(agentEntry.open),agentOpener=useRef<HTMLElement|null>(null);
 function openAgentAccess(opener:HTMLElement){agentOpener.current=opener;setAgentOpen(true);}
 function closeAgentAccess(){setAgentOpen(false);if(window.location.pathname==='/developers/ai')history.replaceState({},'','/'+window.location.search);}
 const profileRoute=window.location.pathname.match(/^\/authors\/(ieee)\/([0-9]{1,64})$/);
 const [user,setUser]=useState<User|null>(null),[mode,setMode]=useState('reader'),[loading,setLoading]=useState(true),[error,setError]=useState(''),[change,setChange]=useState(false),[authRequired,setAuthRequired]=useState(true),[registration,setRegistration]=useState(false);
 async function session(){try{
  const r=await api('/api/auth/session');
  setCsrf(r.csrf);setUser(r.user);setMode(r.interface);
  setAuthRequired(r.interface==='admin'||r.authentication_required!==false);setRegistration(!!r.registration);
 }catch{
  setError(t('暂时无法连接服务，请刷新页面。'));
 }finally{
  setLoading(false);
 }}
 useEffect(()=>{void session();const expired=()=>{setUser(null);void session();};window.addEventListener('cirdc-auth-expired',expired);return()=>window.removeEventListener('cirdc-auth-expired',expired);},[]);
 async function logout(){try{
  await api('/api/auth/logout','POST',{});
  // Personal pages have nothing to show once signed out; leave before the page re-renders anonymously.
  if(['/account','/favorites'].includes(window.location.pathname)){window.location.replace('/');return;}
  setUser(null);setChange(false);forgetFavorites();
  await session();
 }catch(e){
  setError(String((e as Error).message));
 }}
 const publicReader=mode==='reader'&&!authRequired;
 useEffect(()=>{if(!loading)setAccount(user,publicReader,registration);},[user,publicReader,registration,loading]);
 const path=window.location.pathname,next=returnPath(new URLSearchParams(window.location.search).get('next'));
 /** After signing in from the sign-in or registration page, return to the page that sent the reader there. */
 function signedIn(u:User){setCsrf(u.csrf);if(['/login','/register'].includes(path)&&!u.must_change){window.location.replace(next);return;}setUser(u);}
 const personal=path==='/account'||path==='/favorites';
 if(!loading&&personal&&!user&&mode==='reader'&&publicReader){window.location.replace(signInHref(path+window.location.search));return null;}
 if(loading)return <div className="app-loading" role="status"><span className="spinner" aria-hidden="true"/>{t('正在连接文献数据库…')}</div>;
 return <>
  <a className="skip-link" href="#main">{t('跳到主要内容')}</a>
  <AppHeader mode={mode} user={user} publicReader={publicReader} registration={registration} agentOpen={agentOpen} onAgentAccess={openAgentAccess} onPassword={()=>setChange(true)} onLogout={()=>void logout()}/>
  {error&&<div className="global-error" role="alert"><span>{t(error)}</span><button type="button" className="ghost" onClick={()=>setError('')}>{t('关闭')}</button></div>}
  {!publicReader&&!user?(path==='/register'&&registration?<Register onLogin={signedIn} next={next}/>:<Login mode={mode} registration={registration} next={next} onLogin={signedIn}/>):user&&(user.must_change||change)?<PasswordForm forced={!!user.must_change} done={()=>{setChange(false);setUser(null);void session();}} cancel={()=>setChange(false)}/>:mode==='admin'?<AdminPage/>
   :path==='/login'&&!user?<Login mode={mode} publicReader registration={registration} next={next} onLogin={signedIn}/>:path==='/register'&&registration&&!user?<Register onLogin={signedIn} next={next}/>
   :path==='/account'&&user?<Suspense fallback={null}><AccountPage onPassword={()=>setChange(true)} onLogout={()=>void logout()}/></Suspense>:path==='/favorites'&&user?<Suspense fallback={null}><FavoritesPage/></Suspense>
   :profileRoute?<AuthorProfile source={profileRoute[1]} authorId={profileRoute[2]} fetcher={api}/>:<Reader/>}
  <footer className="app-footer"><span>{t('CIRDC Pro ')}</span><span aria-hidden="true">·</span><span>{t(' IEEE 与 arXiv 论文元数据 ')}</span>{mode==='reader'&&<><span aria-hidden="true">·</span><button type="button" aria-haspopup="dialog" aria-controls="agent-access-dialog" aria-expanded={agentOpen} onClick={event=>openAgentAccess(event.currentTarget)}>{t('AI 接入')}</button></>}</footer>
  {agentOpen&&<Suspense fallback={null}><AgentAccess onClose={closeAgentAccess} returnFocus={agentOpener.current}/></Suspense>}
 </>;
}
createRoot(document.getElementById('root')!).render(<App/>);
