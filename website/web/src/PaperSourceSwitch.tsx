import {t,useLanguage} from './i18n';
/** `source` is null on pages that belong to neither source (favorites, account). */
export default function SourceSwitch({source}:{source:'ieee'|'arxiv'|null}){
 useLanguage();
 const href=(target:'ieee'|'arxiv')=>{const q=new URLSearchParams(location.search).get('q')||'';return '/?'+new URLSearchParams(target==='arxiv'?{source:'arxiv',q}:{q});};
 return <nav className="header-source-switch" aria-label={t('论文来源')}><a className={source==='ieee'?'button active':'button'} aria-current={source==='ieee'?'page':undefined} href={href('ieee')} onPointerDown={e=>{e.currentTarget.href=href('ieee');}} onClick={e=>{e.currentTarget.href=href('ieee');}}>IEEE</a><a className={source==='arxiv'?'button active':'button'} aria-current={source==='arxiv'?'page':undefined} href={href('arxiv')} onPointerDown={e=>{e.currentTarget.href=href('arxiv');}} onClick={e=>{e.currentTarget.href=href('arxiv');}}>arXiv</a></nav>;
}
