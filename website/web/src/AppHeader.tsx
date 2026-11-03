import {useEffect,useId,useRef,useState} from 'react';
import {t,useLanguage,setLanguage} from './i18n';
import ThemeControl from './ThemeControl';
import Icon from './Icon';
import type {User} from './types';

export function BrandMark(){
 return <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><rect width="32" height="32" rx="8"/><path className="brand-mark-arc" d="M21.2 11.1a7.4 7.4 0 1 0 0 9.8"/><path className="brand-mark-node" d="M17.4 16h4.6"/><circle className="brand-mark-dot" cx="23.4" cy="16" r="1.9"/></svg>;
}
function LanguageSwitch(){
 const lang=useLanguage();
 return <div className="language-switch" role="group" aria-label={t('界面语言')}><button type="button" lang="zh-CN" aria-pressed={lang==='zh'} onClick={()=>setLanguage('zh')}>{t('中文')}</button><button type="button" lang="en" aria-pressed={lang==='en'} onClick={()=>setLanguage('en')}>{t('English')}</button></div>;
}
function HeaderMenu({user,nav,current,onPassword,onLogout}:{user:User|null;nav:boolean;current:string;onPassword:()=>void;onLogout:()=>void}){
 const [open,setOpen]=useState(false),root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),id=useId();
 useEffect(()=>{
  if(!open)return;
  const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target))setOpen(false);};
  const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){setOpen(false);trigger.current?.focus();}};
  document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
  return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key);};
 },[open]);
 return <div className={'header-menu'+(user?'':' nav-only')} ref={root} onBlur={event=>{if(open&&event.relatedTarget instanceof Node&&!root.current?.contains(event.relatedTarget))setOpen(false);}}>
  <button ref={trigger} type="button" className="header-menu-trigger" aria-expanded={open} aria-controls={id} aria-label={user?t('账户菜单：{name}',{name:user.username}):t('菜单')} onClick={()=>setOpen(value=>!value)}>
   {user?<><span className="avatar" aria-hidden="true">{user.username.slice(0,1).toUpperCase()}</span><span className="header-menu-name">{user.username}</span></>:<Icon name="menu"/>}
   <Icon name="down" className="header-menu-caret"/>
  </button>
  <div id={id} className="header-menu-panel" hidden={!open}>
   {nav&&<nav className="header-menu-nav" aria-label={t('主导航')}><a href="/" aria-current={current==='search'?'page':undefined}>{t('论文检索')}</a><a href="/developers/ai" aria-current={current==='ai'?'page':undefined}>{t('AI 接入')}</a></nav>}
   {user&&<div className="header-menu-account"><p className="header-menu-user"><span>{t('当前账户')}</span><strong>{user.username}</strong></p>
    <button type="button" className="menu-item" onClick={()=>{setOpen(false);onPassword();}}><Icon name="key"/>{t('修改密码')}</button>
    <button type="button" className="menu-item" onClick={()=>{setOpen(false);onLogout();}}><Icon name="logout"/>{t('退出')}</button></div>}
  </div>
 </div>;
}
export default function AppHeader({mode,user,publicReader,current,onPassword,onLogout}:{mode:string;user:User|null;publicReader:boolean;current:string;onPassword:()=>void;onLogout:()=>void}){
 useLanguage();
 const admin=mode==='admin',account=user&&!publicReader?user:null;
 return <header className={'app-header'+(publicReader?' public-reader-header':'')}>
  <div className="app-header-inner">
   <a className="brand" href={admin?'/admin/':'/'}><BrandMark/><span className="brand-name">{t('CIRDC ')}<em>{t('Pro')}</em></span><span className="brand-sub">{admin?t('管理员工作台'):t('文献数据库')}</span></a>
   {!admin&&<nav className="app-nav" aria-label={t('主导航')}><a href="/" aria-current={current==='search'?'page':undefined}>{t('论文检索')}</a><a href="/developers/ai" aria-current={current==='ai'?'page':undefined}>{t('AI 接入')}</a></nav>}
   <div className="header-tools"><LanguageSwitch/><ThemeControl/>{(account||!admin)&&<HeaderMenu user={account} nav={!admin} current={current} onPassword={onPassword} onLogout={onLogout}/>}</div>
  </div>
 </header>;
}
