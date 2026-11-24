import {useEffect,useId,useRef,useState,type ReactNode,type RefObject} from 'react';
import {t,useLanguage} from './i18n';
import {chooseLanguage,signInHref} from './account';
import ThemeControl from './ThemeControl';
import Icon from './Icon';
import type {User} from './types';

export function BrandMark(){
 return <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><rect width="32" height="32" rx="8"/><path className="brand-mark-arc" d="M21.2 11.1a7.4 7.4 0 1 0 0 9.8"/><path className="brand-mark-node" d="M17.4 16h4.6"/><circle className="brand-mark-dot" cx="23.4" cy="16" r="1.9"/></svg>;
}
function LanguageSwitch({onChoose}:{onChoose?:()=>void}){
 const lang=useLanguage(),choose=(value:'zh'|'en')=>{chooseLanguage(value);onChoose?.();};
 return <div className="language-switch" role="group" aria-label={t('界面语言')}><button type="button" lang="zh-CN" aria-pressed={lang==='zh'} onClick={()=>choose('zh')}>{t('中文')}</button><button type="button" lang="en" aria-pressed={lang==='en'} onClick={()=>choose('en')}>{t('English')}</button></div>;
}
/** Close a header popover on an outside pointer or Escape; Escape inside an open dialog belongs to that dialog. */
function useDismiss(open:boolean,close:()=>void,inside:RefObject<HTMLElement|null>[],trigger:RefObject<HTMLButtonElement|null>){
 useEffect(()=>{
  if(!open)return;
  const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!inside.some(ref=>ref.current?.contains(event.target as Node)))close();};
  const key=(event:KeyboardEvent)=>{if(event.key!=='Escape'||(event.target instanceof Element&&event.target.closest('dialog')))return;close();trigger.current?.focus();};
  document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
  return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key);};
 },[open]);
}
/** Site tools sit inline on wide screens; at phone width they fold into a menu opened by the last header button,
 * so the header stays on one line. `children` (account menu or sign-in) sit between them in reading and focus order. */
function HeaderTools({admin,agentOpen,onAgentAccess,register,children}:{admin:boolean;agentOpen:boolean;onAgentAccess:(opener:HTMLElement)=>void;register:string|null;children?:ReactNode}){
 const [open,setOpen]=useState(false),panel=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),id=useId(),close=()=>setOpen(false);
 useDismiss(open,close,[panel,trigger],trigger);
 return <>
  <div id={id} ref={panel} className={'header-more-panel'+(open?' is-open':'')}>
   {!admin&&<button type="button" className="header-ai-trigger" aria-haspopup="dialog" aria-controls="agent-access-dialog" aria-expanded={agentOpen} onClick={event=>{const opener=open&&trigger.current?trigger.current:event.currentTarget;close();onAgentAccess(opener);}}>{t('AI 接入')}</button>}
   <LanguageSwitch onChoose={close}/><ThemeControl/>
   {register&&<a className="header-register header-register-menu" href={register}>{t('注册')}</a>}
  </div>
  {children}
  {register&&<a className="header-register header-register-inline" href={register}>{t('注册')}</a>}
  <button ref={trigger} type="button" className="header-more-trigger" aria-expanded={open} aria-controls={id} aria-label={t('更多设置')} title={t('更多设置')} onClick={()=>setOpen(value=>!value)}><Icon name={open?'close':'menu'}/></button>
 </>;
}
function HeaderMenu({user,reader,onPassword,onLogout}:{user:User;reader:boolean;onPassword:()=>void;onLogout:()=>void}){
 const [open,setOpen]=useState(false),root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),id=useId();
 useDismiss(open,()=>setOpen(false),[root],trigger);
 return <div className="header-menu" ref={root} onBlur={event=>{if(open&&event.relatedTarget instanceof Node&&!root.current?.contains(event.relatedTarget))setOpen(false);}}>
  <button ref={trigger} type="button" className="header-menu-trigger" aria-expanded={open} aria-controls={id} aria-label={t('账户菜单：{name}',{name:user.username})} onClick={()=>setOpen(value=>!value)}>
   <span className="avatar" aria-hidden="true">{user.username.slice(0,1).toUpperCase()}</span><span className="header-menu-name">{user.username}</span>
   <Icon name="down" className="header-menu-caret"/>
  </button>
  <div id={id} className="header-menu-panel" hidden={!open}>
   <div className="header-menu-account"><p className="header-menu-user"><span>{t('当前账户')}</span><strong>{user.username}</strong></p>
    {reader&&<><a className="menu-item" href="/favorites"><Icon name="star"/>{t('我的收藏')}</a><a className="menu-item" href="/account"><Icon name="settings"/>{t('账户设置')}</a></>}
    <button type="button" className="menu-item" onClick={()=>{setOpen(false);onPassword();}}><Icon name="key"/>{t('修改密码')}</button>
    <button type="button" className="menu-item" onClick={()=>{setOpen(false);onLogout();}}><Icon name="logout"/>{t('退出')}</button></div>
  </div>
 </div>;
}
export default function AppHeader({mode,user,publicReader,registration=false,agentOpen,onAgentAccess,onPassword,onLogout}:{mode:string;user:User|null;publicReader:boolean;registration?:boolean;agentOpen:boolean;onAgentAccess:(opener:HTMLElement)=>void;onPassword:()=>void;onLogout:()=>void}){
 useLanguage();
 const admin=mode==='admin',account=user,signIn=publicReader&&!user&&!['/login','/register'].includes(location.pathname);
 return <header className={'app-header'+(publicReader?' public-reader-header':'')}>
  <div className="app-header-inner">
   <div className="header-brand-group"><a className="brand" href={admin?'/admin/':'/'}><BrandMark/><span className="brand-name">{t('CIRDC ')}<em>{t('Pro')}</em></span><span className="brand-sub">{admin?t('管理员工作台'):t('文献数据库')}</span></a></div>
   <div className="header-tools"><HeaderTools admin={admin} agentOpen={agentOpen} onAgentAccess={onAgentAccess} register={signIn&&registration?'/register?next='+encodeURIComponent(location.pathname+location.search):null}>{account&&<HeaderMenu user={account} reader={!admin} onPassword={onPassword} onLogout={onLogout}/>}{signIn&&<a className="button header-sign-in" href={signInHref()}>{t('登录')}</a>}</HeaderTools></div>
  </div>
 </header>;
}
