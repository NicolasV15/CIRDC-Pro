(function(config){
 'use strict';
 var key='cirdc.ui.theme.v1',listeners=new Set(),preference='system',snapshot='',media;
 var ids=new Set(config.map(function(t){return t.id;}));
 function normalize(value){return value==='system'||ids.has(value)?value:'system';}
 try{preference=normalize(localStorage.getItem(key));}catch(e){}
 try{media=window.matchMedia('(prefers-color-scheme: dark)');}catch(e){media={matches:false};}
 function apply(value,remember){
  preference=normalize(value);
  var effective=preference==='system'?(media.matches?'graphite':'plain-white'):preference;
  var theme=config.find(function(t){return t.id===effective;});
  document.documentElement.dataset.theme=effective;
  document.documentElement.dataset.themePreference=preference;
  document.documentElement.style.colorScheme=theme.scheme;
  var meta=document.querySelector('meta[name="theme-color"]');
  if(!meta){meta=document.createElement('meta');meta.name='theme-color';document.head.appendChild(meta);}
  meta.content=theme.bg;
  var icon=document.querySelector('link[rel~="icon"]');
  if(!icon){icon=document.createElement('link');icon.rel='icon';document.head.appendChild(icon);}
  icon.type='image/svg+xml';icon.href=theme.icon;
  if(remember){try{localStorage.setItem(key,preference);}catch(e){}}
  var next=preference+'/'+effective;
  if(next!==snapshot){snapshot=next;listeners.forEach(function(listener){listener();});}
 }
 // applyAccount shows a signed-in reader's synced theme without touching this browser's saved choice; restore returns to it.
 window.CIRDCTheme={getSnapshot:function(){return snapshot;},setPreference:function(value){apply(value,true);},applyAccount:function(value){apply(value,false);},restore:function(){var saved='system';try{saved=localStorage.getItem(key);}catch(e){}apply(saved,false);},subscribe:function(listener){listeners.add(listener);return function(){listeners.delete(listener);};}};
 apply(preference,false);
 var systemChange=function(){if(preference==='system')apply('system',false);};
 if(media.addEventListener)media.addEventListener('change',systemChange);else if(media.addListener)media.addListener(systemChange);
 window.addEventListener('storage',function(event){if(event.key===key)apply(event.newValue,false);else if(event.key===null)apply('system',false);});
})(/*THEME_CONFIG*/);
