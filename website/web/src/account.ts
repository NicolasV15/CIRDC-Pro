import {useSyncExternalStore} from 'react';
import {api} from './api';
import {resolveLanguagePreference,setLanguage,currentLanguage,type Language} from './i18n';
import type {User} from './types';
import type {ThemePreference} from './themeCatalog';

/** The signed-in reader shared by the header, favorites and settings pages. */
type State={user:User|null;publicReader:boolean;registration:boolean;syncError:string};
let state:State={user:null,publicReader:false,registration:false,syncError:''};
const listeners=new Set<()=>void>();
function update(next:Partial<State>){state={...state,...next};listeners.forEach(listener=>listener());}
export function useAccount(){return useSyncExternalStore(subscribe,()=>state,()=>state);}
function subscribe(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};}
export function accountState(){return state;}
export function setAccount(user:User|null,publicReader:boolean,registration:boolean){
 const previous=state.user?.username;update({user,publicReader,registration});
 if(user&&!user.must_change&&previous!==user.username)void startPreferences();
 if(!user&&previous)endPreferences();
}

/** A same-site path to return to after signing in; anything else falls back to the home page. */
export function returnPath(value:string|null){return value&&/^\/(?!\/)[^\s\\]*$/.test(value)&&!value.startsWith('/api/')?value:'/';}
export function signInHref(path=location.pathname+location.search){return '/login?next='+encodeURIComponent(path);}

// Theme and language follow the account while signed in; this browser's anonymous choice stays saved.
type Theme=ThemePreference;
let synced=false;
function browserTheme():Theme{return ((window.CIRDCTheme?.getSnapshot()||'system/plain-white').split('/')[0]||'system') as Theme;}
function storedLanguage(){try{return resolveLanguagePreference(localStorage.getItem('cirdc.ui.language'));}catch{return resolveLanguagePreference(undefined);}}
async function save(values:{theme?:Theme;language?:Language}){
 try{await api('/api/me/settings','PUT',values);update({syncError:''});}
 catch{update({syncError:'偏好未能保存到账户，本次更改仅在当前页面生效。'});}
}
async function startPreferences(){
 try{
  const {settings}=await api('/api/me/settings');
  synced=true;
  if(!settings.theme&&!settings.language){await save({theme:browserTheme(),language:currentLanguage()});return;}
  if(settings.theme)window.CIRDCTheme?.applyAccount(settings.theme);
  if(settings.language)setLanguage(settings.language,false);
 }catch{update({syncError:'暂时无法读取账户偏好，当前使用此浏览器的设置。'});}
}
function endPreferences(){
 if(!synced)return;synced=false;
 window.CIRDCTheme?.restore();setLanguage(storedLanguage(),false);update({syncError:''});
}
export function chooseTheme(value:Theme){
 if(synced){window.CIRDCTheme?.applyAccount(value);void save({theme:value});}
 else window.CIRDCTheme?.setPreference(value);
}
export function chooseLanguage(value:Language){
 if(synced){setLanguage(value,false);void save({language:value});}
 else setLanguage(value);
}
export function dismissSyncError(){update({syncError:''});}
