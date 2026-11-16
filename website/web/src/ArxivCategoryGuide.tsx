import {useEffect,useRef} from 'react';
import {useLanguage} from './i18n';
import {arxivCategoryProfiles,arxivCategoryReviewed,arxivCategorySource} from './arxivCategoryGuideData';
import Icon from './Icon';

export default function ArxivCategoryGuide({onClose}:{onClose:()=>void}){
 const lang=useLanguage(),zh=lang==='zh',dialog=useRef<HTMLDialogElement>(null),close=useRef<HTMLButtonElement>(null);
 useEffect(()=>{const box=dialog.current;if(!box)return;const opener=document.activeElement instanceof HTMLElement?document.activeElement:null,overflow=document.body.style.overflow;box.showModal();document.body.style.overflow='hidden';close.current?.focus();return()=>{if(box.open)box.close();document.body.style.overflow=overflow;opener?.focus();};},[]);
 function jump(code:string){document.getElementById('arxiv-profile-'+code)?.scrollIntoView({block:'start'});}
 return <dialog className="venue-guide-dialog" id="arxiv-category-guide-dialog" ref={dialog} aria-labelledby="arxiv-category-guide-title" aria-describedby="arxiv-category-guide-intro" onCancel={e=>{e.preventDefault();onClose();}} onClick={e=>{if(e.target!==e.currentTarget)return;const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}>
  <header className="venue-guide-header"><div><h2 id="arxiv-category-guide-title">{zh?'电路相关分类介绍':'Circuit-related category guide'}</h2><p>{zh?'核对日期':'Reviewed'} · {arxivCategoryReviewed}</p></div><button type="button" className="venue-guide-close" ref={close} onClick={onClose} aria-label={zh?'关闭分类介绍':'Close category guide'}><Icon name="close"/></button></header>
  <div className="venue-guide-scroll" tabIndex={0}><p className="venue-guide-intro" id="arxiv-category-guide-intro">{zh?'这些 arXiv 分类覆盖电路、器件及 AI、优化等交叉研究方向。分类范围依据官方说明概述；下方选文建议由本站整理。':'These arXiv categories cover circuits, devices and related AI and optimization research. Scope summaries follow the official taxonomy; reading tips are CIRDC editorial guidance.'}</p><p>{zh?'可以同时选择多个分类，匹配其中任意一个即纳入结果；同一篇交叉分类论文只显示一次。未选择时检索全部 arXiv。':'Select multiple categories to match any one of them. Cross-listed papers appear once. With no selection, search all of arXiv.'}</p>
   <nav className="venue-guide-nav" aria-label={zh?'跳转到分类':'Jump to category'}>{arxivCategoryProfiles.map(p=><button type="button" key={p.code} onClick={()=>jump(p.code)}>{p.code}</button>)}</nav>
   {arxivCategoryProfiles.map(p=><article className="venue-guide-profile" id={'arxiv-profile-'+p.code} key={p.code}><div className="venue-guide-profile-heading"><h3>{p.code}</h3><span>{p.name[lang]}</span></div>{zh&&<p className="venue-guide-fullname">{p.name.en}</p>}<dl><div><dt>{zh?'分类范围':'Scope'}</dt><dd>{p.scope[lang]}</dd></div><div><dt>{zh?'选文建议':'Reading tips'}</dt><dd>{p.reading[lang]}</dd></div></dl><div className="venue-guide-references"><a href={arxivCategorySource+'#'+p.code} target="_blank" rel="noopener noreferrer">{zh?'arXiv 官方分类说明':'Official arXiv category description'} ↗</a></div></article>)}
  </div>
 </dialog>;
}
