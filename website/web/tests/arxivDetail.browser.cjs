/* arXiv detail: version switching/history, version-bound resources, explicit acquisition, author and
 * category browsing. Set PLAYWRIGHT_MODULE and optionally PLAYWRIGHT_CHROMIUM_EXECUTABLE. All requests are fixtures. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://arxiv-detail.test';
const types={'.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
const authors=Array.from({length:12},(_,i)=>['Author'+(i+1),'Given','']);
const papers={
 1:{paper_id:'1',arxiv_id:'2402.08954',title:'Time-Interleaved ADC',authors_raw:'Lin Zhang, Wei Chen',abstract:'Current abstract.',metadata:{categories:['eess.SP','cs.AR'],submitted_at:'2024-02-13T20:30:00Z',license:'http://creativecommons.org/licenses/by/4.0/',authors_structured:[['Zhang','Lin',''],['Chen','Wei','']]},versions:[{version:1,version_date:'2024-02-14'},{version:2,version_date:'2024-03-02'},{version:3,version_date:'2024-06-19T20:30:00Z'}]},
 2:{paper_id:'2',arxiv_id:'hep-th/9901001',title:'Long author list',authors_raw:'',abstract:'',metadata:{categories:['hep-th'],authors_structured:authors},versions:[{version:1,version_date:'1999-01-04'}]},
};
const ready={state:'ready'},none={state:'not_requested'};
function initialStates(){return {
 '1:3':{state:'complete',resources:{html:ready,pdf:ready,source:ready},document:{source:'arxiv_html'},reading_state:'ready'},
 '1:2':{state:'partial',resources:{html:{state:'unavailable'},pdf:ready,source:{state:'failed'}},reading_state:'failed'},
 '1:1':{state:'not_requested',resources:{html:none,pdf:none,source:none}},
 '2:1':{state:'partial',resources:{html:{state:'unavailable'},pdf:{state:'unavailable'},source:{state:'unavailable'}},reading_state:'unavailable'},
};}
const body=v=>`<article class="ltx_document"><section><h2 id="s1">1 Introduction</h2><p class="version-marker">Body of version ${v}.</p></section></article>`;
async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const [language,width] of [['zh',1440],['en',390],['zh',320]]){
  const context=await browser.newContext({viewport:{width,height:900}});
  await context.addInitScript(lang=>localStorage.setItem('cirdc.ui.language',lang),language);
  const states=initialStates(),posts=[],errors=[],polls={};let delayV2=false;
  await context.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url()),p=u.pathname;
   if(u.origin!==origin)return route.abort();
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(req.method()!=='GET'){
    const m=/^\/api\/arxiv\/papers\/(\d+)\/versions\/(\d+)\/ensure$/.exec(p);assert.ok(m,'unexpected write '+p);
    posts.push({key:m[1]+':'+m[2],body:req.postDataJSON()});states[m[1]+':'+m[2]]={state:'queued',resources:{html:{state:'queued'},pdf:{state:'queued'},source:{state:'queued'}},reading_state:'queued'};polls[m[1]+':'+m[2]]=0;
    return route.fulfill({status:202,json:{accepted:true,state:'queued',request_id:'a'.repeat(64)}});
   }
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
   let m=/^\/api\/arxiv\/papers\/(\d+)$/.exec(p);
   if(m)return papers[m[1]]?route.fulfill({json:{paper:papers[m[1]]}}):route.fulfill({status:404,json:{paper:null}});
   m=/^\/api\/arxiv\/papers\/(\d+)\/versions\/(\d+)\/(resources|document|body)$/.exec(p);
   if(m){const key=m[1]+':'+m[2];
    if(m[3]==='resources'){
     if(states[key].state==='queued'&&++polls[key]>1)states[key]={state:'complete',resources:{html:ready,pdf:ready,source:{state:'unavailable'}},document:{source:'arxiv_html'},reading_state:'ready'};
     if(key==='1:2'&&delayV2)await new Promise(resolve=>setTimeout(resolve,600));
     return route.fulfill({json:states[key]});}
    if(m[3]==='document')return route.fulfill({json:{state:'ready',document:{source:'arxiv_html',version:'v'+m[2],body_url:'/api/arxiv/papers/'+m[1]+'/versions/'+m[2]+'/body',toc:[{id:'s1',title:'1 Introduction',level:2}],assets_ready:0,assets_total:0}}});
    return route.fulfill({contentType:'text/html',body:body(m[2])});}
   return route.fulfill({status:404,json:{error:'not_found'}});
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const zh=language==='zh',label=(a,b)=>zh?a:b;
  const versionButton=v=>page.locator('.arxiv-version-switch button').filter({hasText:'v'+v});
  const marker=()=>page.locator('.version-marker').allTextContents();
  // Opening without a version selects and records the latest observed version.
  await page.goto(origin+'/arxiv/papers/1?source=arxiv&q=adc');
  await page.locator('.version-marker').waitFor();
  assert.equal(new URL(page.url()).searchParams.get('v'),'3');
  assert.deepEqual(await marker(),['Body of version 3.']);
  assert.match(await page.locator('.document-progress').innerText(),/arXiv HTML/);
  assert.equal(await versionButton(3).getAttribute('aria-pressed'),'true');
  assert.match(await versionButton(3).innerText(),/2024-06-20/);
  assert.equal(await page.locator('.bibliographic-row').filter({has:page.locator('dt',{hasText:label('投稿时间','Submitted')})}).locator('dd').innerText(),'2024-02-14');
  assert.equal(await page.locator('.arxiv-version-note').count(),0);
  assert.equal(await page.locator('.bibliographic a',{hasText:'CC BY 4.0'}).count(),1);
  assert.equal(await page.locator('.arxiv-kicker a[href*="category=eess.SP"]').count(),1);
  assert.equal(await page.locator('.arxiv-resource-download').count(),3);
  // A slower older version never shows the newer body or statuses while it loads.
  delayV2=true;await versionButton(2).click();
  assert.equal(new URL(page.url()).searchParams.get('v'),'2');
  assert.deepEqual(await marker(),[]);
  assert.equal(await page.locator('.arxiv-resource-list').count(),0);
  await page.locator('.arxiv-resource-list').waitFor();delayV2=false;
  assert.deepEqual(await marker(),[]);
  assert.equal(await page.locator('.arxiv-version-note').count(),1);
  assert.equal(await page.locator('.arxiv-resource-download').count(),1);
  assert.match(await page.locator('.arxiv-resource-download').getAttribute('href'),/\/versions\/2\/files\/pdf$/);
  assert.equal(await page.locator('a.detail-pdf-trigger').getAttribute('href'),'/api/arxiv/papers/1/versions/2/pdf/reader');
  assert.match(await page.locator('.detail-record-actions a.detail-source-link').getAttribute('href'),/2402\.08954v2$/);
  // Browser history restores versions without another request for writes.
  await page.goBack();await page.locator('.version-marker').waitFor();
  assert.deepEqual(await marker(),['Body of version 3.']);
  await page.goForward();await page.locator('.arxiv-resource-list').waitFor();
  assert.equal(await versionButton(2).getAttribute('aria-pressed'),'true');
  assert.deepEqual(posts,[]);
  // A partial version offers an explicit retry; an unrequested version offers one first request.
  await page.getByRole('button',{name:label('重试未完成项','Retry unfinished resources'),exact:true}).click();
  await page.locator('.version-marker').waitFor({timeout:10000});
  assert.deepEqual(posts,[{key:'1:2',body:{retry:true}}]);
  assert.deepEqual(await marker(),['Body of version 2.']);
  await versionButton(1).click();
  await page.getByRole('button',{name:label('获取本版本资料','Get files for this version'),exact:true}).click();
  await page.locator('.arxiv-resource-progress').waitFor();
  await page.locator('.version-marker').waitFor({timeout:10000});
  assert.deepEqual(posts.map(p=>p.key),['1:2','1:1']);assert.deepEqual(posts[1].body,{retry:false});
  await page.reload();await page.locator('.version-marker').waitFor();
  assert.equal(posts.length,2);
  // An invalid version link is reported and replaced by the latest version.
  await page.goto(origin+'/arxiv/papers/1?source=arxiv&v=9');await page.locator('.version-marker').waitFor();
  assert.equal(new URL(page.url()).searchParams.get('v'),'3');
  assert.match(await page.locator('.detail-header [role=status]').first().innerText(),/v9/);
  // Long author lists collapse; names link to an author search; nothing to retry when all are confirmed missing.
  await page.goto(origin+'/arxiv/papers/2?source=arxiv');await page.locator('.arxiv-resource-list').waitFor();
  assert.equal(await page.locator('.arxiv-author-link').count(),8);
  await page.locator('.detail-authors-toggle').click();
  assert.equal(await page.locator('.arxiv-author-link').count(),12);
  assert.equal(new URL(await page.locator('.arxiv-author-link').first().getAttribute('href'),origin).searchParams.get('field'),'authors');
  assert.equal(await page.locator('.arxiv-resource-actions button').count(),0);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  // Unknown papers show a not-found page instead of a generic error.
  await page.goto(origin+'/arxiv/papers/99?source=arxiv');
  await page.getByRole('heading',{name:label('未找到该 arXiv 论文','arXiv paper not found')}).waitFor();
  assert.equal(posts.length,2);assert.deepEqual(errors,[]);
  reports.push({language,width,versionHistory:true,noStaleBody:true,explicitPosts:posts.length,authors:12});
  await context.close();
 }console.log(JSON.stringify(reports));}finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
