const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://author-fixture.test';
(async()=>{const browser=await chromium.launch({headless:true});const reports=[];
try{for(const width of [1440,390,320]){const context=await browser.newContext({viewport:{width,height:900}});let state='missing',author=null,posts=0,polls=0;const errors=[];
await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
await context.route('**/*',async route=>{const r=route.request(),p=new URL(r.url()).pathname;
 if(p.startsWith('/assets/'))return route.fulfill({body:await fs.readFile(root+p),contentType:p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':'application/octet-stream'});
 if(p==='/authors/ieee/123')return route.fulfill({body:await fs.readFile(root+'/index.html'),contentType:'text/html'});
 if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
 if(p==='/api/authors/ieee/123')return route.fulfill({json:{author:{display_name:'Example Author',papers:1}}});
 if(p==='/api/author-profiles/ieee/123/ensure'){posts++;assert.equal(r.method(),'POST');state='queued';polls=0;return route.fulfill({status:202,json:{acquisition:{state,id:'job-1'}}});}
 if(p==='/api/author-profiles/ieee/123'){if(state==='queued'&&++polls>=2){state=posts===1?'complete':'blocked';author={fetched_at:'2026-01-01T00:00:00Z',fetch_state:state,profile:{preferred_name:'Example Author',bio_paragraphs:['Stored biography'],is_hidden:false}};}
 return route.fulfill({json:{author,acquisition:{state,id:'job-1'}}});}
 errors.push(p);return route.abort();});
const page=await context.newPage();await page.goto(origin+'/authors/ieee/123',{waitUntil:'networkidle'});assert.equal(posts,0);
await page.getByRole('button',{name:'获取作者资料',exact:true}).click();await page.getByText('Stored biography').waitFor();assert.equal(posts,1);
await page.getByRole('button',{name:'更新资料',exact:true}).click();await page.getByText('采集状态：访问受限',{exact:true}).waitFor();assert.equal(posts,2);assert(await page.getByText('Stored biography').isVisible());
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);reports.push({width,posts,getDoesNotCollect:true,oldProfileRetained:true});await context.close();}}
finally{await browser.close()}console.log(JSON.stringify({status:'passed',reports}));})().catch(e=>{console.error(e);process.exitCode=1});
