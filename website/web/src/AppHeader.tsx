import {useEffect,useId,useRef,useState} from 'react';
import {t,useLanguage,setLanguage} from './i18n';
import ThemeControl from './ThemeControl';
import Icon from './Icon';
import SourceSwitch from './PaperSourceSwitch';
import type {User} from './types';

export function BrandMark(){
 return <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><rect width="32" height="32" rx="8"/><path className="brand-mark-arc" d="M21.2 11.1a7.4 7.4 0 1 0 0 9.8"/><path className="brand-mark-node" d="M17.4 16h4.6"/><circle className="brand-mark-dot" cx="23.4" cy="16" r="1.9"/></svg>;
}
function LanguageSwitch(){
 const lang=useLanguage();
 return <div className="language-switch" role="group" aria-label={t('界面语言')}><button type="button" lang="zh-CN" aria-pressed={lang==='zh'} onClick={()=>setLanguage('zh')}>{t('中文')}</button><button type="button" lang="en" aria-pressed={lang==='en'} onClick={()=>setLanguage('en')}>{t('English')}</button></div>;
}
function HeaderMenu({user,onPassword,onLogout}:{user:User;onPassword:()=>void;onLogout:()=>void}){
 const [open,setOpen]=useState(false),root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),id=useId();
 useEffect(()=>{
  if(!open)return;
  const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target))setOpen(false);};
  const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){setOpen(false);trigger.current?.focus();}};
  document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
  return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key);};
 },[open]);
 return <div className="header-menu" ref={root} onBlur={event=>{if(open&&event.relatedTarget instanceof Node&&!root.current?.contains(event.relatedTarget))setOpen(false);}}>
  <button ref={trigger} type="button" className="header-menu-trigger" aria-expanded={open} aria-controls={id} aria-label={t('账户菜单：{name}',{name:user.username})} onClick={()=>setOpen(value=>!value)}>
   <span className="avatar" aria-hidden="true">{user.username.slice(0,1).toUpperCase()}</span><span className="header-menu-name">{user.username}</span>
   <Icon name="down" className="header-menu-caret"/>
  </button>
  <div id={id} className="header-menu-panel" hidden={!open}>
   <div className="header-menu-account"><p className="header-menu-user"><span>{t('当前账户')}</span><strong>{user.username}</strong></p>
    <button type="button" className="menu-item" onClick={()=>{setOpen(false);onPassword();}}><Icon name="key"/>{t('修改密码')}</button>
    <button type="button" className="menu-item" onClick={()=>{setOpen(false);onLogout();}}><Icon name="logout"/>{t('退出')}</button></div>
  </div>
 </div>;
}
export default function AppHeader({mode,user,publicReader,agentOpen,onAgentAccess,onPassword,onLogout}:{mode:string;user:User|null;publicReader:boolean;agentOpen:boolean;onAgentAccess:(opener:HTMLElement)=>void;onPassword:()=>void;onLogout:()=>void}){
 useLanguage();
 const admin=mode==='admin',account=user&&!publicReader?user:null;
 const source=location.pathname.startsWith('/arxiv/')||new URLSearchParams(location.search).get('source')==='arxiv'?'arxiv':'ieee';
 return <header className={'app-header'+(publicReader?' public-reader-header':'')}>
  <div className="app-header-inner">
   <div className="header-brand-group"><a className="brand" href={admin?'/admin/':'/'}><BrandMark/><span className="brand-name">{t('CIRDC ')}<em>{t('Pro')}</em></span><span className="brand-sub">{admin?t('管理员工作台'):t('文献数据库')}</span></a>{!admin&&<SourceSwitch source={source}/>}</div>
   <div className="header-tools">{!admin&&<button type="button" className="header-ai-trigger" aria-haspopup="dialog" aria-controls="agent-access-dialog" aria-expanded={agentOpen} onClick={event=>onAgentAccess(event.currentTarget)}>{t('AI 接入')}</button>}<LanguageSwitch/><ThemeControl/>{account&&<HeaderMenu user={account} onPassword={onPassword} onLogout={onLogout}/>}</div>
  </div>
 </header>;
}
