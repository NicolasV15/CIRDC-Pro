/* Isolated search loading acceptance. Set PLAYWRIGHT_MODULE, optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE and CIRDC_BROWSER_OUTPUT. All requests are mocked. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://search-startup.test';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const profile of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844,touch:true},{name:'narrow-dark',width:320,height:760,touch:true,dark:true}]){
  const context=await browser.newContext({viewport:{width:profile.width,height:profile.height},locale:'zh-CN',isMobile:!!profile.touch,hasTouch:!!profile.touch,colorScheme:profile.dark?'dark':'light'});
  await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  const page=await context.newPage();page.setDefaultTimeout(12000);const requests=[],blocked=[],errors=[];let releaseInitial,releaseOld,initialPending=false,oldPending=false,failCount=true,venueCalls=0;
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   if(req.method()!=='GET'||url.origin!==origin){blocked.push(req.method()+' '+req.url());return route.abort();}
   requests.push(p+url.search);
   if(p==='/')return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
   if(p==='/api/overview')return route.fulfill({json:{index:{phase:'ready',year_range:{min:1884,max:2027},overview:{papers:173,venues:[],field_states:[]}}}});
   if(p==='/api/venues'){
    venueCalls++;if(venueCalls===1)return route.fulfill({status:503,json:{error:'temporarily_unavailable'}});
    return route.fulfill({json:{items:[{kind:'Journals',number:'4',title:'Fixture JSSC'},{kind:'Conferences',number:'200',title:'Fixture Conference'}]}});
   }
   if(p==='/api/papers'){
    const q=url.searchParams.get('q')||'',mode=url.searchParams.get('totals'),limit=Number(url.searchParams.get('limit')||25),total=q==='New'?12:q==='Fail'?17:173;
    if(mode==='only'){
     assert(await page.locator('.paper-row').count()>0,'Rows must be mounted before the total request');
     if(!q&&!initialPending){initialPending=true;await new Promise(resolve=>{releaseInitial=resolve;});}
     if(q==='Old'){oldPending=true;await new Promise(resolve=>{releaseOld=resolve;});try{return await route.fulfill({json:{total:999,items:[],next_cursor:null,partial:false}});}catch{return;}}
     if(q==='Fail'&&failCount)return route.fulfill({status:503,json:{error:'search_busy'}});
     return route.fulfill({json:{total,items:[],next_cursor:null,partial:false}});
    }
    assert.equal(mode,'defer');if(q==='Broken')return route.fulfill({status:503,json:{error:'search_busy'}});const offset=url.searchParams.has('cursor')?limit:0;
    return route.fulfill({json:{items:Array.from({length:Math.min(limit,Math.max(0,total-offset))},(_,i)=>({number:String(83010000+offset+i),title:(q||'Fixture')+' '+(offset+i),authors:'',author_refs:[],publication:'Fixture',venue:'4',kind:'Journals',year:2026,snippet:'Cached summary.',resources:[]})),total:null,next_cursor:offset+limit<total?'fixture-next':null,partial:false}});
   }
   blocked.push(p);return route.abort();
  });
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});await page.locator('.paper-row').first().waitFor();assert.equal(await page.locator('.paper-row').count(),25);await page.waitForFunction(()=>document.querySelector('.result-total')?.textContent.includes('正在统计'));
  await page.waitForTimeout(80);assert(initialPending);assert(!requests.includes('/api/venues'));assert((await page.locator('.result-loaded').innerText()).includes('25'));releaseInitial();await page.waitForFunction(()=>document.querySelector('.result-total')?.textContent.includes('173'));
  await page.getByRole('button',{name:'加载更多论文',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===50);assert((await page.locator('.result-loaded').innerText()).includes('50'));
  const first=page.locator('.paper-selection-control input').first();await first.check();await page.getByLabel('每页条数',{exact:true}).selectOption('100');await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===100);assert(!await page.locator('.paper-selection-control input').first().isChecked());
  async function search(value){await page.getByRole('textbox',{name:'搜索论文',exact:true}).fill(value);await page.locator('.search-box').evaluate(el=>el.requestSubmit());await page.waitForFunction(value=>document.querySelector('.paper-title')?.textContent.startsWith(value),value);}
  await search('Old');while(!oldPending)await page.waitForTimeout(20);await search('New');await page.waitForFunction(()=>document.querySelector('.result-total')?.textContent.includes('12'));releaseOld();await page.waitForTimeout(100);assert(!(await page.locator('.result-total').innerText()).includes('999'));
  await page.getByRole('textbox',{name:'搜索论文',exact:true}).fill('Broken');await page.locator('.search-box').evaluate(el=>el.requestSubmit());await page.locator('.error-box').waitFor();assert((await page.locator('.result-total').innerText()).includes('总数暂不可用'));assert.equal(await page.getByRole('button',{name:'重试统计',exact:true}).count(),0);
  await search('Fail');await page.getByRole('button',{name:'重试统计',exact:true}).waitFor();assert.equal(await page.locator('.paper-row').count(),17);assert((await page.locator('.result-total').innerText()).includes('总数暂不可用'));failCount=false;await page.getByRole('button',{name:'重试统计',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.result-total')?.textContent.includes('17'));
  const venue=page.locator('input[list="venues"]');if(!await venue.isVisible())await page.locator('.filter-disclosure > summary').click();await venue.focus();await page.getByText('刊会列表暂不可用，可输入刊会编号。',{exact:true}).waitFor();await venue.blur();await venue.focus();await page.waitForFunction(()=>document.querySelectorAll('#venues option').length===2);assert.equal(venueCalls,2);
  await venue.fill('4 · Fixture JSSC');await page.locator('.search-box').evaluate(el=>el.requestSubmit());await page.waitForTimeout(150);assert(requests.some(url=>url.startsWith('/api/papers?')&&url.includes('venue=4')));
  await page.getByRole('button',{name:'English',exact:true}).click();assert((await page.locator('.result-loaded').innerText()).includes('17'));
  assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  reports.push({profile:profile.name,rowsVisibleBeforeCount:true,exactTotalAfterwards:true,loadedCountAndPagination:true,pageSizeSelectionCleared:true,staleCountIgnored:true,countFailureAndRetry:true,rowFailureStopsCounting:true,catalogLazy:true,catalogRetry:true,venueFiltering:true,bilingual:true,realSourceRequests:0,pdfConversions:0});console.log(JSON.stringify(reports.at(-1)));await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'search-startup-result.json'),JSON.stringify({reports},null,2)+'\n');
}
main().catch(error=>{console.error(error);process.exitCode=1});
