import {useEffect,useRef,useState} from 'react';
import {t,useLanguage} from './i18n';
import {agentPrompts} from './agentAccess';
import Icon,{type IconName} from './Icon';
import './agentAccess.css';
import {skillBase,skillRelease,type SkillRelease} from './skillRelease';

function Prompt({title,value}:{title:string;value:string}){
 const [notice,setNotice]=useState<'copied'|'selected'|''>('');
 const field=useRef<HTMLTextAreaElement>(null);
 useEffect(()=>{setNotice('');if(field.current)field.current.scrollTop=0;},[value]);
 async function copy(){
  try{await navigator.clipboard.writeText(value);if(field.current?.value===value)setNotice('copied');}
  catch{if(field.current?.value!==value)return;field.current.focus();field.current.select();setNotice('selected');}
 }
 return <div className="agent-prompt">
  <div className="agent-prompt-heading"><span>{title}</span><button type="button" className={notice==='copied'?'is-copied':undefined} aria-label={title+' · '+t('复制 prompt')} onClick={()=>void copy()}><Icon name={notice==='copied'?'check':'copy'}/>{t('复制 prompt')}</button></div>
  <textarea ref={field} readOnly value={value} aria-label={title} spellCheck={false}/>
  <span className={'agent-copy-status'+(notice?' is-'+notice:'')} role="status">{notice?t(notice==='copied'?'已复制':'已选中文本，请手动复制。'):''}</span>
 </div>;
}
function Option({id,step,icon,title,description,prompt,value}:{id:string;step:string;icon:IconName;title:string;description:string;prompt:string;value:string}){
 return <section className="panel agent-prompt-card" aria-labelledby={id}>
  <div className="agent-choice-heading"><span className="agent-choice-icon" aria-hidden="true"><Icon name={icon}/><b>{step}</b></span><div><h3 id={id}>{title}</h3><p className="muted">{description}</p></div></div>
  <Prompt title={prompt} value={value}/>
 </section>;
}
export default function AgentAccess({onClose,returnFocus}:{onClose:()=>void;returnFocus:HTMLElement|null}){
 const language=useLanguage();
 const [release,setRelease]=useState<SkillRelease|null>(null);
 useEffect(()=>{let active=true;void skillRelease().then(value=>{if(active)setRelease(value);});return()=>{active=false;};},[]);
 const dialog=useRef<HTMLDialogElement>(null),close=useRef<HTMLButtonElement>(null);
 useEffect(()=>{
  const box=dialog.current;if(!box)return;
  const opener=returnFocus??(document.activeElement instanceof HTMLElement?document.activeElement:null),overflow=document.body.style.overflow;
  box.showModal();document.body.style.overflow='hidden';close.current?.focus();
  return()=>{if(box.open)box.close();document.body.style.overflow=overflow;if(opener?.isConnected)opener.focus({preventScroll:true});};
 },[]);
 const prompts=agentPrompts(window.location.origin,language);
 return <dialog id="agent-access-dialog" className="venue-guide-dialog agent-access-dialog" ref={dialog} aria-labelledby="agent-access-title" aria-describedby="agent-access-intro" onCancel={event=>{event.preventDefault();onClose();}} onClick={event=>{if(event.target!==event.currentTarget)return;const rect=event.currentTarget.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)onClose();}}>
  <header className="venue-guide-header agent-access-header"><div><h2 id="agent-access-title">{t('AI 接入')}</h2><p id="agent-access-intro">{t('在目标工作目录下打开 Agent 对话，复制对应 prompt 即可。')}</p></div><button type="button" className="venue-guide-close" ref={close} aria-label={t('关闭')} onClick={onClose}><Icon name="close"/></button><div className="agent-skill-meta"><p className="agent-skill-version">{t('本站 Skill 版本')}：{release?release.version:t('版本信息暂不可用')}</p><a className="agent-skill-help" href={skillBase+'/references/api.md#native-skill-installation'} target="_blank" rel="noreferrer"><span>{t('安装与更新说明')}</span><Icon name="external" className="icon-trailing"/></a></div></header>
  <div className="venue-guide-scroll" tabIndex={0}>
   <div className="agent-options">
   <Option id="agent-online-title" step="1" icon="link" title={t('连接当前站点')} description={t('安装在线 Skill 并绑定当前站点。')} prompt={t('在线安装 prompt')} value={prompts.remote}/>
   <Option id="agent-local-title" step="2" icon="server" title={t('部署到自己的机器')} description={t('在本地工作目录克隆、部署服务并安装 Skill。')} prompt={t('本地部署 prompt')} value={prompts.local}/>
  </div></div>
 </dialog>;
}
