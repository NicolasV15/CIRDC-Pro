const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../src/cirdc/web/static');
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});try{
for(const width of [1440,390,320]){const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();let posts=0,ensured=false;const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',async route=>{const u=new URL(route.request().url()),p=u.pathname;
if(p.startsWith('/api/')){let data={};
if(p==='/api/auth/session')data={interface:'reader',authentication_required:false,user:null};
else if(p==='/api/arxiv/papers/1')data={paper:{paper_id:'1',arxiv_id:'2402.08954',title:'arXiv sample',authors_raw:'A. Author',abstract:'Abstract body',metadata:{categories:['cs.DL']},versions:[{version:1,version_date:'2024-02-14'}]}};
else if(p.endsWith('/ensure')){posts++;ensured=true;data={state:'queued'};}
else if(p.endsWith('/resources'))data={state:ensured?'partial':'not_requested',resources:{pdf:{state:ensured?'ready':'not_requested'},html:{state:'unavailable'},source:{state:'unavailable'}},reading_state:ensured?'failed':'queued'};
return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});}
let file=p.startsWith('/assets/')?path.join(root,p):path.join(root,'index.html');const mime=p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':p.endsWith('.woff2')?'font/woff2':'text/html';try{return route.fulfill({contentType:mime,body:await fs.readFile(file)});}catch{return route.abort();}});
await page.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));await page.goto('http://arxiv-fixture.test/arxiv/papers/1?source=arxiv&v=1');await page.getByRole('heading',{name:'arXiv sample'}).waitFor();assert.equal(posts,0);await page.getByRole('button',{name:'获取论文资料',exact:true}).click();await page.getByRole('link',{name:'阅读 PDF',exact:true}).waitFor();assert.equal(posts,1);await page.reload();await page.getByRole('heading',{name:'arXiv sample'}).waitFor();assert.equal(posts,1);assert.deepEqual(errors,[]);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));console.log(JSON.stringify({width,posts,queriesReadOnly:true,reloadReadOnly:true}));await context.close();}
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
