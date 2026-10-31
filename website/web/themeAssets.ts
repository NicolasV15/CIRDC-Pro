import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import type {Plugin} from 'vite';
import {themeSpecs,buildThemeCss} from './src/themeCatalog.ts';
export function themeAssets():Plugin{
 const script=()=>fs.readFileSync(fileURLToPath(new URL('./themeRuntime.js',import.meta.url)),'utf8').replace('/*THEME_CONFIG*/',JSON.stringify(themeSpecs.map(({id,scheme,bg})=>({id,scheme,bg}))));
 return {name:'cirdc-theme-assets',transformIndexHtml:{order:'post',handler:html=>html.replace('<!--cirdc-theme-assets-->','<script src="/assets/theme-init.js"></script><link rel="stylesheet" href="/assets/themes.css">')},generateBundle(){this.emitFile({type:'asset',fileName:'assets/themes.css',source:buildThemeCss()});this.emitFile({type:'asset',fileName:'assets/theme-init.js',source:script()});},configureServer(server){server.middlewares.use((req,res,next)=>{if(req.url==='/assets/themes.css'||req.url==='/assets/theme-init.js'){res.setHeader('Content-Type',req.url.endsWith('.css')?'text/css':'text/javascript');res.setHeader('Cache-Control','no-cache');res.end(req.url.endsWith('.css')?buildThemeCss():script());}else next();});}};
}
