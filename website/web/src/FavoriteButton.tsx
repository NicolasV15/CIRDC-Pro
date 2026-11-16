import {useState} from 'react';
import {t,useLanguage} from './i18n';
import Icon from './Icon';
import {favoriteState,isFavorite,toggleFavorite,useFavoriteRevision,type FavoriteTarget} from './favorites';

/** Save or remove a paper; on arXiv lists the newest observed version is pinned when saving. */
export default function FavoriteButton({target,title,detail=false}:{target:FavoriteTarget;title:string;detail?:boolean}){
 useLanguage();useFavoriteRevision();
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const state=favoriteState(target),saved=isFavorite(state);
 const versions=state?.versions?Object.keys(state.versions).map(v=>'v'+v).join(t('、')):'';
 const label=saved?(versions?t('取消收藏（{versions}）：',{versions}):t('取消收藏：')):t('收藏论文：');
 async function click(){setBusy(true);setError('');try{await toggleFavorite(target);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <span className="favorite-control"><button type="button" className={(detail?'detail-favorite-trigger':'favorite-trigger')+(saved?' is-saved':'')} aria-pressed={saved} aria-label={label+title} title={saved&&versions?t('已收藏 {versions}',{versions}):undefined} disabled={busy} onClick={()=>void click()}><Icon name={saved?'starFilled':'star'}/>{saved?t('已收藏'):t('收藏')}{saved&&versions&&<small>{versions}</small>}</button>{error&&<span className="favorite-error" role="alert">{t(error)}</span>}</span>;
}
