/* Matching publisher typography and resource controls; all API/file responses are fixtures. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../src/cirdc/web/static');
const http=require('node:http');
const types={'.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
(async()=>{const server=http.createServer((req,res)=>{const html=req.url.endsWith('/files/html');res.writeHead(200,{'Content-Type':html?'text/html':'application/gzip','Content-Disposition':'attachment; filename="'+(html?'article.html':'source.tar.gz')+'"'});res.end(html?'<article>HTML source</article>':'fixture archive bytes');});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});const reports=[];
try{for(const language of ['zh','en'])for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:1000},acceptDownloads:true});await context.addInitScript(lang=>localStorage.setItem('cirdc.ui.language',lang),language);let posts=0;
 await context.route('**/*',async route=>{const request=route.request(),u=new URL(request.url()),p=u.pathname;if(request.method()==='POST')posts++;
 if(p.startsWith('/api/')){let data={};
  if(p==='/api/auth/session')data={interface:'reader',authentication_required:false,user:null};
  else if(p==='/api/overview')data={index:{phase:'ready',indexed:1}};
  else if(p==='/api/papers/1')data={paper:{number:'1',record:{articleTitle:'Matching typography sample',abstract:'Same abstract text for both publisher readers.',authors:[{preferredName:'A. Author'}],keywords:{},articleContentType:'Journals'},resources:[{id:'pdf',kind:'pdf',href:'/api/resources/fixture.pdf',media_type:'application/pdf'}]}};
  else if(p==='/api/arxiv/papers/1')data={paper:{paper_id:'1',arxiv_id:'2402.08954',title:'Matching typography sample',abstract:'Same abstract text for both publisher readers.',authors_raw:'A. Author',metadata:{categories:['cs.DL']},versions:[{version:1,version_date:'2024-02-14'}]}};
  else if(p.endsWith('/resources'))data={state:'complete',reading_state:'failed',resources:{pdf:{state:'ready'},html:{state:'ready'},source:{state:'ready'}}};
  else if(p.endsWith('/files/html')||p.endsWith('/files/source'))return route.continue();
  else if(p.endsWith('/metadata/status'))data={state:'disabled'};
  else if(p.endsWith('/references')||p.endsWith('/citations')||p.endsWith('/patent-citations'))data={state:'disabled',items:[],total:0,counts:{},stored_counts:{}};
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 }
 const file=p.startsWith('/assets/')?path.join(root,p):path.join(root,'index.html');return route.fulfill({contentType:types[path.extname(file)]||'text/html',body:await fs.readFile(file)});
 });
 async function metrics(page){return page.evaluate(()=>{
  const style=selector=>{const el=document.querySelector(selector),s=getComputedStyle(el);return Object.fromEntries(['fontFamily','fontSize','fontWeight','lineHeight','paddingTop','paddingRight','paddingBottom','paddingLeft','borderRadius','backgroundColor','color'].map(k=>[k,s[k]]));};
  return {title:style('.detail-header h1'),abstract:style('.abstract'),pdf:style('a.detail-pdf-trigger'),source:style('a.detail-source-link'),gap:getComputedStyle(document.querySelector('.detail-record-actions')).gap};
 });}
 const ieee=await context.newPage();await ieee.goto(origin+'/papers/1');await ieee.locator('a.detail-pdf-trigger').waitFor();const expected=await metrics(ieee);
 const arxiv=await context.newPage();await arxiv.goto(origin+'/arxiv/papers/1?source=arxiv&v=1');await arxiv.locator('a.detail-pdf-trigger').waitFor();assert.deepEqual(await metrics(arxiv),expected);
 const actions=arxiv.locator('.detail-record-actions');assert.deepEqual(await actions.locator('a').evaluateAll(links=>links.map(l=>l.className)),['button detail-pdf-trigger','button detail-source-link','button detail-source-download','button detail-source-download']);
 const pdfBox=await actions.locator('a').nth(0).boundingBox(),sourceBox=await actions.locator('a').nth(1).boundingBox();assert.equal(pdfBox.y,sourceBox.y);assert.ok(sourceBox.x>pdfBox.x);
 for(const [index,name] of [[2,'article.html'],[3,'source.tar.gz']]){const pending=arxiv.waitForEvent('download');await actions.locator('a').nth(index).click();assert.equal((await pending).suggestedFilename(),name);}
 const before=await arxiv.locator('.abstract').evaluate(e=>getComputedStyle(e).fontSize);await arxiv.locator('.reader-layout-controls summary').click();const font=arxiv.locator('input[type=range]').first();await font.focus();await font.press('ArrowRight');assert.notEqual(await arxiv.locator('.abstract').evaluate(e=>getComputedStyle(e).fontSize),before);
 assert.equal(posts,0);assert.ok(await arxiv.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));reports.push({language,width,matchingTypography:true,matchingResourceButtons:true,downloads:2,posts});await context.close();
}console.log(JSON.stringify(reports));}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}})().catch(e=>{console.error(e);process.exitCode=1;});
