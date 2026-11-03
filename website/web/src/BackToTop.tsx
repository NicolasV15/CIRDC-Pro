import {useEffect,useState,type RefObject} from 'react';
import {t,useLanguage} from './i18n';

export default function BackToTop({target}:{target:RefObject<HTMLElement|null>}){
 useLanguage();
 const [visible,setVisible]=useState(()=>window.scrollY>400);
 useEffect(()=>{
  const update=()=>setVisible(window.scrollY>400);window.addEventListener('scroll',update,{passive:true});update();
  return()=>window.removeEventListener('scroll',update);
 },[]);
 if(!visible)return null;
 return <button type="button" className="back-to-top" aria-label={t('回到顶部')} title={t('回到顶部')} onClick={()=>{
  window.scrollTo({top:0,left:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  target.current?.focus({preventScroll:true});
 }}><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 13 6-6 6 6M12 7v12"/></svg></button>;
}
