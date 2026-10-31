import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import vm from 'node:vm';
import {themeSpecs,themeTokens,contrast,buildThemeCss} from '../src/themeCatalog.ts';
const source=fs.readFileSync(new URL('../themeRuntime.js',import.meta.url),'utf8').replace('/*THEME_CONFIG*/',JSON.stringify(themeSpecs));
function runtime({dark=false,saved=null,blocked=false}:{dark?:boolean;saved?:string|null;blocked?:boolean}={}){
 const events=new Map<string,(e:any)=>void>(),mediaEvents=new Map<string,()=>void>(),memory=new Map<string,string>();if(saved!==null)memory.set('cirdc.ui.theme.v1',saved);
 const meta={content:'',name:'theme-color'},root={dataset:{} as Record<string,string>,style:{} as Record<string,string>};
 const document={documentElement:root,title:'123-Paper title',querySelector:()=>meta,createElement:()=>meta,head:{appendChild:()=>{}}};
 const media={matches:dark,addEventListener:(name:string,fn:()=>void)=>mediaEvents.set(name,fn)};
 const window={matchMedia:()=>media,addEventListener:(name:string,fn:(e:any)=>void)=>events.set(name,fn)} as any;
 const localStorage={getItem:(key:string)=>{if(blocked)throw Error('blocked');return memory.get(key)??null;},setItem:(key:string,value:string)=>{if(blocked)throw Error('blocked');memory.set(key,value);}};
 vm.runInNewContext(source,{window,document,localStorage,Set});return {api:window.CIRDCTheme,root,document,meta,media,mediaEvents,events,memory};
}
test('six palettes keep every normal role readable on its intended backgrounds',()=>{
 assert.equal(themeSpecs.length,6);assert.equal(new Set(themeSpecs.map(t=>t.id)).size,6);const keys=Object.keys(themeTokens(themeSpecs[0])).sort();
 for(const spec of themeSpecs){const p=themeTokens(spec);assert.deepEqual(Object.keys(p).sort(),keys);assert(contrast(p.text,p.surface)>=4.5);assert(contrast(p.accent,p.surface)>=4.5);assert(contrast(p['on-accent'],p.accent)>=4.5);assert(contrast(p['on-accent'],p['accent-hover'])>=4.5);assert(contrast(p['border-strong'],p.surface)>=3);
  for(const role of ['muted','faint'])for(const background of ['bg','surface','surface-alt','hover','selected','success-bg','warning-bg','error-bg','info-bg'])assert(contrast(p[role],p[background])>=4.5,spec.id+' '+role+' / '+background);
  for(const state of ['success','warning','error','info'])assert(contrast(p[state+'-fg'],p[state+'-bg'])>=4.5);
 }
 assert(buildThemeCss().includes(':root:not([data-theme])'));assert(buildThemeCss().includes('.swatch-graphite'));
});
test('first paint defaults to system, valid preferences restore, invalid values cannot become CSS',()=>{
 for(const dark of [false,true]){const r=runtime({dark});assert.equal(r.root.dataset.theme,dark?'graphite':'plain-white');assert.equal(r.api.getSnapshot(),'system/'+r.root.dataset.theme);assert.equal(r.document.title,'123-Paper title');}
 const restored=runtime({dark:true,saved:'paper'});assert.equal(restored.root.dataset.theme,'paper');assert.equal(restored.root.style.colorScheme,'light');
 const invalid=runtime({saved:'url(javascript:bad)'});assert.equal(invalid.root.dataset.theme,'plain-white');
});
test('fixed themes ignore OS changes; system themes react; local switching notifies without page or title changes',()=>{
 const r=runtime();let count=0;const stop=r.api.subscribe(()=>count++);r.api.setPreference('midnight');assert.equal(r.memory.get('cirdc.ui.theme.v1'),'midnight');assert.equal(r.meta.content,'#111827');r.media.matches=true;r.mediaEvents.get('change')!();assert.equal(r.root.dataset.theme,'midnight');
 r.api.setPreference('system');assert.equal(r.root.dataset.theme,'graphite');r.media.matches=false;r.mediaEvents.get('change')!();assert.equal(r.root.dataset.theme,'plain-white');assert.equal(r.document.title,'123-Paper title');assert.equal(count,3);stop();r.api.setPreference('paper');assert.equal(count,3);
});
test('same-origin storage changes synchronize; blocked storage leaves in-memory controls working',()=>{
 const r=runtime();r.events.get('storage')!({key:'cirdc.ui.theme.v1',newValue:'lavender'});assert.equal(r.root.dataset.theme,'lavender');r.events.get('storage')!({key:'other',newValue:'graphite'});assert.equal(r.root.dataset.theme,'lavender');r.events.get('storage')!({key:null});assert.equal(r.api.getSnapshot(),'system/plain-white');
 const blocked=runtime({blocked:true,dark:true});blocked.api.setPreference('paper');assert.equal(blocked.root.dataset.theme,'paper');assert.equal(blocked.document.title,'123-Paper title');
});
