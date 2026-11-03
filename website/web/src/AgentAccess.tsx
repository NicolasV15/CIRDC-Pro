import {useEffect,useRef,useState} from 'react';
import {t,useLanguage} from './i18n';
import {agentPrompts} from './agentAccess';
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
  <div className="agent-prompt-heading"><span>{title}</span><button type="button" aria-label={title+' · '+t('复制 prompt')} onClick={()=>void copy()}>{t('复制 prompt')}</button></div>
  <textarea ref={field} readOnly value={value} aria-label={title} spellCheck={false}/>
  <span className="agent-copy-status" role="status">{notice?t(notice==='copied'?'已复制':'已选中文本，请手动复制。'):''}</span>
 </div>;
}

export default function AgentAccess(){
 const language=useLanguage();
 const prompts=agentPrompts(window.location.origin,language);
 return <main className="workspace agent-access">
  <div className="page-heading"><div><span className="eyebrow">AGENT SETUP</span><h1>{t('AI 接入')}</h1><p className="muted">{t('在目标工作目录下打开 Agent 对话，复制对应 prompt 即可。')}</p></div><a className="text-button" href="/">{t('返回论文检索')}</a></div>
  <section className="panel agent-prompt-card" aria-labelledby="agent-online-title">
   <div className="agent-choice-heading"><span className="agent-choice-number" aria-hidden="true">1</span><div><h2 id="agent-online-title">{t('连接当前站点')}</h2><p className="muted">{t('Agent 安装在线 Skill，自动保存当前站点地址，随后即可在你的项目中使用。')}</p></div></div>
   <Prompt title={t('在线安装 prompt')} value={prompts.remote}/>
  </section>
  <section className="panel agent-prompt-card" aria-labelledby="agent-local-title">
   <div className="agent-choice-heading"><span className="agent-choice-number" aria-hidden="true">2</span><div><h2 id="agent-local-title">{t('部署到自己的机器')}</h2><p className="muted">{t('Agent 在当前对话的工作目录中克隆源码、部署网页，并安装指向该实例的 Skill。')}</p></div></div>
   <Prompt title={t('本地部署 prompt')} value={prompts.local}/>
  </section>
 </main>;
}
