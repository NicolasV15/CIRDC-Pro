import {useEffect,useRef,useState} from 'react';
import {t,useLanguage} from './i18n';
import {agentPrompts} from './agentAccess';
import Icon,{type IconName} from './Icon';
import './agentAccess.css';

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
  <div className="agent-choice-heading"><span className="agent-choice-icon" aria-hidden="true"><Icon name={icon}/><b>{step}</b></span><div><h2 id={id}>{title}</h2><p className="muted">{description}</p></div></div>
  <Prompt title={prompt} value={value}/>
 </section>;
}
export default function AgentAccess(){
 const language=useLanguage();
 const prompts=agentPrompts(window.location.origin,language);
 return <main id="main" className="workspace agent-access">
  <div className="agent-hero"><a className="back-link" href="/"><Icon name="back"/>{t('返回论文检索')}</a><h1>{t('AI 接入')}</h1><p className="muted">{t('在目标工作目录下打开 Agent 对话，复制对应 prompt 即可。')}</p></div>
  <div className="agent-options">
   <Option id="agent-online-title" step="1" icon="link" title={t('连接当前站点')} description={t('Agent 安装在线 Skill，自动保存当前站点地址，随后即可在你的项目中使用。')} prompt={t('在线安装 prompt')} value={prompts.remote}/>
   <Option id="agent-local-title" step="2" icon="server" title={t('部署到自己的机器')} description={t('Agent 在当前对话的工作目录中克隆源码、部署网页，并安装指向该实例的 Skill。')} prompt={t('本地部署 prompt')} value={prompts.local}/>
  </div>
 </main>;
}
