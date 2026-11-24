/* Isolated cached author fixture. No acquisition, database or source requests. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
/** Phones keep the language switch in the header menu. */
async function chooseLanguage(page,name){const menu=page.locator('.header-more-trigger');if(await menu.isVisible())await menu.click();await page.locator('.app-header .language-switch').getByRole('button',{name,exact:true}).click();}
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://author-years.test';
const initial=[{name:'2028',num_records:6},{name:'2020',num_records:0},{name:'2024',num_records:null},{name:'2026',num_records:12},{name:'2021',num_records:3}];
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}),reports=[];
try{for(const width of [1440,390,320]){
 const context=await browser.newContext({viewport:{width,height:960},isMobile:width<500,hasTouch:width<500,colorScheme:width===320?'dark':'light'});let years=initial,reads=0;const blocked=[],errors=[];
 await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
 await context.route('**/*',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;
  if(req.method()!=='GET'||url.origin!==origin){blocked.push(req.method()+' '+p);return route.abort();}
  if(p==='/authors/ieee/123')return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
  if(p.startsWith('/assets/'))return route.fulfill({contentType:p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':'application/octet-stream',body:await fs.readFile(root+p)});
  if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
  if(p==='/api/authors/ieee/123')return route.fulfill({json:{author:{display_name:'Example Author',papers:19}}});
  if(p==='/api/author-profiles/ieee/123'){reads++;return route.fulfill({json:{author:{fetched_at:'2026-01-01T00:00:00Z',fetch_state:'complete',field_states:{publication_years:years.length?'complete':'no_data'},profile:{preferred_name:'Example Author',current_affiliations:['Fixture Institute'],publication_years:years,is_hidden:false}},acquisition:{state:'disabled'}}});}
  blocked.push(p);return route.abort();
 });
 const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
 const section=()=>page.locator('.author-profile details').filter({has:page.locator('summary').filter({hasText:/^(发表年份分布|Publications by year)$/})});
 const columns=()=>section().locator('.author-year-column');
 await page.goto(origin+'/authors/ieee/123',{waitUntil:'networkidle'});await section().waitFor();assert.equal(await section().getAttribute('open'),null);
 await section().locator('summary').click();await section().locator('.author-year-scroll').waitFor({state:'visible'});
 assert.deepEqual(await columns().locator('.author-year-label').allTextContents(),['2020','2021','2024','2026','2028']);
 assert.deepEqual(await columns().locator('.author-year-count').allTextContents(),['0','3','—','12','6']);
 assert.equal(await columns().nth(2).locator('.author-year-bar').count(),0,'Missing count must not become zero');
 const heights=await columns().evaluateAll(rows=>rows.map(row=>row.querySelector('.author-year-bar')?.getBoundingClientRect().height??null));
 assert.equal(heights[0],0);assert(Math.abs(heights[1]-heights[3]/4)<1);assert(Math.abs(heights[4]-heights[3]/2)<1);
 assert((await columns().nth(2).getAttribute('aria-label')).includes('来源未提供'));assert.equal(await section().locator('table').count(),0);
 const colors=[];for(const theme of ['classic-green','plain-white','graphite','paper','midnight','lavender']){await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);colors.push(await columns().nth(3).locator('.author-year-bar').evaluate(el=>getComputedStyle(el).backgroundColor));assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));}
 assert(new Set(colors).size>1);if(process.env.CIRDC_BROWSER_OUTPUT){await section().scrollIntoViewIfNeeded();await section().screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,'author-years-'+width+'.png')});}
 const before=reads;await chooseLanguage(page,'English');assert.equal(await section().locator('figcaption').innerText(),'IEEE article count');assert.equal(reads,before);assert((await columns().nth(3).getAttribute('aria-label')).includes('IEEE article count'));
 await section().locator('summary').press('Enter');assert.equal(await section().getAttribute('open'),null);await section().locator('summary').press('Enter');assert.notEqual(await section().getAttribute('open'),null);
 years=Array.from({length:60},(_,i)=>({name:String(1960+i),num_records:i%13}));await page.reload({waitUntil:'networkidle'});await section().locator('summary').click();const scroll=section().locator('.author-year-scroll');
 assert.equal(await columns().count(),60);assert(await scroll.evaluate(el=>el.scrollWidth>el.clientWidth));await scroll.focus();await scroll.press('End');await scroll.evaluate(el=>el.scrollLeft=el.scrollWidth);assert(await scroll.evaluate(el=>el.scrollLeft>0));assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
 years=[{name:'2026',num_records:0},{name:'2025',num_records:0}];await page.reload({waitUntil:'networkidle'});await section().locator('summary').click();assert.deepEqual(await columns().locator('.author-year-count').allTextContents(),['0','0']);assert.deepEqual(await columns().locator('.author-year-bar').evaluateAll(bars=>bars.map(el=>el.getBoundingClientRect().height)),[0,0]);
 years=[{name:'2028',num_records:7}];await page.reload({waitUntil:'networkidle'});await section().locator('summary').click();assert.equal(await columns().count(),1);assert.equal(await columns().locator('.author-year-count').innerText(),'7');
 years=[];await page.reload({waitUntil:'networkidle'});await section().locator('summary').click();assert.equal(await section().locator('.author-year-chart').count(),0);assert((await section().innerText()).includes('来源未提供'));
 assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);reports.push({width,chronological:true,sourceCounts:true,proportionalBars:true,missingNotZero:true,futureYearAutomatic:true,zeroAndSingleYear:true,emptyState:true,internalScrollOnly:true,disclosureKeyboard:true,sixThemes:true,bilingual:true,sourceAcquisitions:0,writes:0});console.log(JSON.stringify(reports.at(-1)));await context.close();
}}finally{await browser.close();}
if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'author-years-result.json'),JSON.stringify({status:'passed',reports},null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1});
