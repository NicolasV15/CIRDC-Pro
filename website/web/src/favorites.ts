import {useEffect,useSyncExternalStore} from 'react';
import {api} from './api';
import {accountState,signInHref} from './account';

/** Favorite identity: IEEE by article number; arXiv by internal ID and a pinned version ('latest' from lists). */
export type FavoriteTarget={source:'ieee';paperId:string}|{source:'arxiv';paperId:string;version:number|'latest'};
export type FavoriteState={id:number|null;versions?:Record<string,number>};
const known=new Map<string,FavoriteState>(),listeners=new Set<()=>void>();
let revision=0;
function changed(){revision++;listeners.forEach(listener=>listener());}
function subscribe(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};}
/** List rows ask about any version of an arXiv paper; the detail page asks about the selected version. */
export function favoriteKey(target:FavoriteTarget){return target.source==='arxiv'&&target.version!=='latest'?`arxiv:${target.paperId}:${target.version}`:`${target.source}:${target.paperId}`;}
export function useFavoriteRevision(){return useSyncExternalStore(subscribe,()=>revision,()=>revision);}
export function favoriteState(target:FavoriteTarget){return known.get(favoriteKey(target));}
export function forgetFavorites(){known.clear();changed();}

/** Load the saved state of the given papers for the signed-in reader (one request, at most 200 keys). */
export function useFavoriteStates(targets:FavoriteTarget[],signedIn:boolean){
 const keys=[...new Set(targets.map(favoriteKey))].join(',');
 useEffect(()=>{
  if(!signedIn||!keys)return;let active=true;
  void api('/api/me/favorites/state?keys='+encodeURIComponent(keys)).then(value=>{
   if(!active)return;
   for(const [key,entry] of Object.entries(value.items as Record<string,number|null|{versions:Record<string,number>}>))
    known.set(key,entry&&typeof entry==='object'?{id:Object.values(entry.versions)[0]??null,versions:entry.versions}:{id:entry});
   changed();
  }).catch(()=>{/* The buttons stay usable; saving reports its own errors. */});
  return()=>{active=false;};
 },[keys,signedIn]);
 return useFavoriteRevision();
}

export function isFavorite(state:FavoriteState|undefined){return !!state&&(state.id!==null||!!state.versions&&Object.keys(state.versions).length>0);}

/** Save or remove a favorite. Anonymous readers go to sign-in and come back; nothing is saved on their behalf. */
export async function toggleFavorite(target:FavoriteTarget){
 if(!accountState().user){location.href=signInHref();return;}
 const key=favoriteKey(target),state=known.get(key);
 if(isFavorite(state)){
  const ids=state!.versions?Object.values(state!.versions):[state!.id!];
  await api('/api/me/favorites/remove','POST',{ids});
  for(const [existing,entry] of known){
   if(existing!==key&&!existing.startsWith(`${target.source}:${target.paperId}:`)&&existing!==`${target.source}:${target.paperId}`)continue;
   const versions=entry.versions&&Object.fromEntries(Object.entries(entry.versions).filter(([,id])=>!ids.includes(id)));
   known.set(existing,{id:entry.id!==null&&ids.includes(entry.id)?(versions&&Object.values(versions)[0])??null:entry.id,...(versions?{versions}:{})});
  }
 }else{
  const item=target.source==='arxiv'?{source:'arxiv',paper_id:target.paperId,version:target.version}:{source:'ieee',paper_id:target.paperId};
  const value=await api('/api/me/favorites','POST',{items:[item]});
  for(const [saved,id] of Object.entries(value.items as Record<string,number>)){
   known.set(saved,{id});
   if(target.source==='arxiv'){const list=known.get(`arxiv:${target.paperId}`);known.set(`arxiv:${target.paperId}`,{id,versions:{...list?.versions,[saved.split(':')[2]]:id}});}
  }
 }
 changed();
}
