/* Semantic arXiv typography in the shared reader; no source acquisition. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://typography-fixture.test';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
const tex=String.raw`x^{2}+y^{2}=z^{2}`;
const body='<article class="ltx_document"><h1 id="title" class="ltx_title ltx_title_document">Paper title</h1><div class="ltx_authors">A. Author</div><div class="ltx_dates">2026-11-13</div><div class="ltx_abstract"><h6 id="abstract" class="ltx_title ltx_title_abstract">Abstract</h6><p id="abstract-p">Original abstract text.</p></div><h6 class="ltx_title ltx_title_keywords">Keywords</h6><section><h2 id="section">I. Introduction</h2><p id="prose">Original paragraph text.</p><p><span class="doc-math" data-copy-tex="'+tex+'">'+tex+'</span></p><figure><figcaption>Figure 1: Original caption.</figcaption></figure></section></article>';
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];try{for(const source of ['arxiv_html','arxiv_source','ieee_html'])for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:1000},locale:'zh-CN'}),page=await context.newPage();let posts=0;
 await context.route('**/*',async route=>{const req=route.request(),p=new URL(req.url()).pathname;if(req.method()!=='GET'){posts++;return route.abort();}
 if(p.startsWith('/api/')){
 let value={};if(p==='/api/auth/session')value={interface:'reader',authentication_required:false,user:null};
 else if(p==='/api/overview')value={index:{phase:'ready',overview:{papers:1}}};
 else if(p==='/api/papers/100')value={paper:{number:'100',record:{articleTitle:'Host title',abstract:'Cached abstract.',authors:[],keywords:{}},resources:[{kind:'document',href:'/api/fixture-content'}]}};
 else if(p==='/api/fixture-content')value={state:'ready',document:{source,version:'fixed',body_url:'/api/fixture-body',toc:[{id:'section',title:'I. Introduction',level:2}],assets_ready:0,assets_total:0}};
 else if(p==='/api/fixture-body')return route.fulfill({contentType:'text/html',body});
 else if(p.endsWith('/metadata/status'))value={state:'disabled'};
 else if(p.endsWith('/references')||p.endsWith('/citations')||p.endsWith('/patent-citations'))value={state:'disabled',items:[],counts:{},stored_counts:{}};
 return route.fulfill({json:value});}
 const file=p.startsWith('/assets/')?root+p:root+'/index.html';return route.fulfill({contentType:types[path.extname(file)]||'text/html',body:await fs.readFile(file)});
 });
 await page.goto(origin+'/papers/100');await page.locator('.document-body .katex').waitFor();
 const read=()=>page.locator('.document-body').evaluate(el=>{const style=s=>{const e=el.querySelector(s),c=getComputedStyle(e);return {size:parseFloat(c.fontSize),family:c.fontFamily,line:c.lineHeight,marginTop:c.marginTop};};return {source:el.dataset.documentSource,title:style('#title'),abstract:style('#abstract'),section:style('#section'),text:style('#prose'),authors:style('.ltx_authors'),caption:style('figcaption'),abstractText:el.querySelector('#abstract-p').textContent,prose:el.querySelector('#prose').textContent,tex:el.querySelector('.doc-math').dataset.copyTex};});
 const initial=await read();assert.equal(initial.source,source);assert.equal(initial.abstractText,'Original abstract text.');assert.equal(initial.prose,'Original paragraph text.');assert.equal(initial.tex,tex);
 if(source.startsWith('arxiv_')){assert.equal(initial.abstract.size,initial.section.size);assert.equal(initial.abstract.family,initial.section.family);assert.equal(initial.title.family,initial.text.family);assert.ok(initial.title.size>initial.abstract.size);assert.ok(initial.text.size>initial.authors.size);assert.equal(initial.title.marginTop,'0px');}
 else {assert.ok(initial.abstract.size<initial.section.size);assert.notEqual(initial.title.family,initial.text.family);}
 await page.locator('.reader-layout-controls summary').click();const font=page.locator('.reader-layout-popover input[type=range]').first();await font.focus();await font.press('End');const enlarged=await read();assert.ok(enlarged.text.size>initial.text.size);if(source.startsWith('arxiv_'))assert.equal(enlarged.abstract.size,enlarged.section.size);assert.equal(enlarged.tex,tex);const original=await page.evaluate(async()=>await (await fetch('/api/fixture-body')).text());assert.equal(original,body);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(posts,0);reports.push({source,width,abstractSize:initial.abstract.size,sectionSize:initial.section.size,scaledAbstractSize:enlarged.abstract.size,sourcePreserved:true,posts});await context.close();
}console.log(JSON.stringify(reports));}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
