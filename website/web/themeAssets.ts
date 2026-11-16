import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import type {Plugin} from 'vite';
import {themeSpecs,themeTokens,buildThemeCss} from './src/themeCatalog.ts';
export function themeAssets():Plugin{
 // Keep the fallback artwork and all themed favicons in the same source asset.
 const artwork=fs.readFileSync(fileURLToPath(new URL('./public/assets/favicon.svg',import.meta.url)),'utf8');
 const icons=themeSpecs.map(theme=>{
  const tokens=themeTokens(theme),source=artwork.replaceAll('#353535',tokens.accent).replaceAll('#FFFFFF',tokens['on-accent']);
  const digest=createHash('sha256').update(source).digest('hex').slice(0,12);
  return {id:theme.id,fileName:'assets/favicon-'+theme.id+'-'+digest+'.svg',source};
 });
 const script=()=>fs.readFileSync(fileURLToPath(new URL('./themeRuntime.js',import.meta.url)),'utf8').replace('/*THEME_CONFIG*/',JSON.stringify(themeSpecs.map(({id,scheme,bg},i)=>({id,scheme,bg,icon:'/'+icons[i].fileName}))));
 return {name:'cirdc-theme-assets',transformIndexHtml:{order:'post',handler:html=>html.replace('<!--cirdc-theme-assets-->','<script src="/assets/theme-init.js"></script><link rel="stylesheet" href="/assets/themes.css">')},generateBundle(){this.emitFile({type:'asset',fileName:'assets/themes.css',source:buildThemeCss()});this.emitFile({type:'asset',fileName:'assets/theme-init.js',source:script()});for(const icon of icons)this.emitFile({type:'asset',fileName:icon.fileName,source:icon.source});},configureServer(server){server.middlewares.use((req,res,next)=>{const icon=icons.find(item=>req.url==='/'+item.fileName);if(icon){res.setHeader('Content-Type','image/svg+xml');res.end(icon.source);}else if(req.url==='/assets/themes.css'||req.url==='/assets/theme-init.js'){res.setHeader('Content-Type',req.url.endsWith('.css')?'text/css':'text/javascript');res.setHeader('Cache-Control','no-cache');res.end(req.url.endsWith('.css')?buildThemeCss():script());}else next();});}};
}
