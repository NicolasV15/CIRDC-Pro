/* Fixture-only browser acceptance. Set PLAYWRIGHT_MODULE, optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE and CIRDC_BROWSER_OUTPUT for local tooling. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://patent-citations.test',number='83000002',other='83000003';
const v1='11111111111111111111111111111111',v2='22222222222222222222222222222222';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
async function main(){
 const fixture=JSON.parse(await fs.readFile(path.join(__dirname,'fixtures/patentCitations.json'),'utf8'));
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const profile of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844},{name:'narrow-dark',width:320,height:760,dark:true}]){
  const context=await browser.newContext({viewport:{width:profile.width,height:profile.height},locale:'zh-CN',timezoneId:'Asia/Shanghai',colorScheme:profile.dark?'dark':'light'});
  const requests=[],posts=[],blocked=[],errors=[];let mode='old',state='queued',badPage=false,readError=false,ensureError=false,holdEnsure=false,heldResolve,releaseHeld,heldResponse,paperGroups='both';
  function patentData(url,id=number){
   const version=url.searchParams.get('version'),offset=Number(url.searchParams.get('offset')||0),limit=Number(url.searchParams.get('limit')||50);
   const kind=id===other?'disabled':version===v1?'old':version===v2?'new':mode;
   const count=kind==='old'?52:kind==='new'?3:kind==='fixture'?2:0,source=kind==='old'?55:kind==='new'||kind==='fixture'?3:kind==='zero'?0:null;
   const terminal=['absent','zero','unknown','disabled','failure'].includes(kind);
   return {...fixture,number:id,state:kind==='absent'||kind==='zero'?'no_data':kind==='unknown'||kind==='failure'?'failed':kind==='disabled'?'disabled':kind==='fixture'?'partial':state,
    version:['unknown','disabled','failure'].includes(kind)?null:kind==='old'||kind==='fixture'?v1:kind==='new'?v2:kind==='absent'?'33333333333333333333333333333333':'44444444444444444444444444444444',total:count,expected_total:source,
    source_presence:kind==='absent'?'absent':['unknown','disabled','failure'].includes(kind)?'unknown':'present',empty_reason:kind==='absent'?'section_absent':kind==='zero'?'zero_count':null,
    checked_at:['unknown','disabled','failure'].includes(kind)?null:fixture.checked_at,last_attempt_at:'2026-11-01T00:01:00Z',stale:kind==='old',error:['unknown','failure'].includes(kind)?'patent_citations_unavailable':kind==='fixture'?fixture.error:null,
    offset,limit,next_offset:!terminal&&offset+limit<count?offset+limit:null,items:Array.from({length:Math.max(0,Math.min(limit,count-offset))},(_,i)=>({...fixture.items[(offset+i)%2],order:offset+i+1,label:String(offset+i+1),text:fixture.items[(offset+i)%2].text+' '+kind}))};
  }
  function paperCitations(url,id){
   const group=url.searchParams.get('group')||'ieee',count=group==='ieee'?2:paperGroups==='both'?1:0;
   if(paperGroups==='absent')return {...fixture,number:id,state:'no_data',version:v1,group,total:0,expected_total:null,counts:{ieee:null,nonIeee:null,total:null},stored_counts:{ieee:0,nonIeee:0,total:0},group_states:{ieee:'no_data',nonIeee:'no_data'},source_presence:'absent',empty_reason:'section_absent',last_attempt_at:'2026-11-01T00:01:00Z',error:null,stale:false,next_offset:null,items:[]};
   return {...fixture,number:id,state:'complete',version:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',group,total:count,expected_total:count,counts:{ieee:2,nonIeee:paperGroups==='both'?1:0,total:paperGroups==='both'?3:2},stored_counts:{ieee:2,nonIeee:paperGroups==='both'?1:0,total:paperGroups==='both'?3:2},group_states:{ieee:'complete',nonIeee:'complete'},error:null,stale:false,next_offset:null,
    items:Array.from({length:count},(_,i)=>({group,order:i+1,label:String(i+1),source_id:'fixture-paper',text:'Fixture citing paper',title:'Fixture citing paper',target_number:group==='ieee'?'99999999':null,doi:null,target_kind:group==='ieee'?'paper':'scholar',target_url:group==='ieee'?'/papers/99999999':'https://scholar.google.com/scholar?q=fixture'}))};
  }
  function references(id){return {...fixture,number:id,state:'unavailable',version:null,total:0,expected_total:null,source_presence:'absent',empty_reason:'section_absent',availability_checked_at:fixture.checked_at,needs_availability_check:false,error:null,next_offset:null,items:[]};}
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname,match=p.match(/^\/api\/papers\/(\d+)/),id=match?.[1];
   if(url.origin!==origin){blocked.push(req.method()+' '+req.url());return route.abort();}
   requests.push({method:req.method(),path:p,version:url.searchParams.get('version'),offset:Number(url.searchParams.get('offset')||0)});
   if(req.method()==='POST'){
    posts.push({path:p,data:req.postDataJSON()});
    if(p==='/api/papers/'+id+'/patent-citations/ensure'){
     if(holdEnsure&&id===number){heldResolve();heldResponse=patentData(url,id);await new Promise(resolve=>{releaseHeld=resolve;});return route.fulfill({json:heldResponse});}
     return ensureError?route.fulfill({status:503,json:{error:'patent_citations_unavailable'}}):route.fulfill({json:patentData(url,id)});
    }
    if(p==='/api/papers/'+id+'/citations/ensure')return route.fulfill({json:paperCitations(url,id)});
    blocked.push(req.method()+' '+p);return route.abort();
   }
   if(req.method()!=='GET'){blocked.push(req.method()+' '+p);return route.abort();}
   if(p.startsWith('/papers/')||p==='/')return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:'fixture'}});
   if(p==='/api/overview')return route.fulfill({json:{index:{phase:'ready',year_range:{min:1884,max:2027},overview:{papers:1,venues:[],field_states:[]}}}});
   if(p==='/api/venues')return route.fulfill({json:{items:[]}});
   if(p==='/api/papers/'+id+'/metadata/status')return route.fulfill({json:{state:'disabled'}});
   if(p==='/api/papers/'+id+'/references')return route.fulfill({json:references(id)});
   if(p==='/api/papers/'+id+'/citations')return route.fulfill({json:paperCitations(url,id)});
   if(p==='/api/papers/'+id+'/patent-citations'){
    if(readError)return route.fulfill({status:503,json:{error:'patent_citations_unavailable'}});
    let data=patentData(url,id);if(badPage&&data.offset){badPage=false;data={...data,version:'bad'};}return route.fulfill({json:data});
   }
   if(p==='/api/papers/'+id)return route.fulfill({json:{paper:{number:id,record:{articleTitle:'Fixture $g_m$ paper '+id,publicationTitle:'Fixture Journal',publicationYear:'2025',articleContentType:'Journals',authors:[],abstract:'Cached fixture abstract',keywords:{'Author Keywords':['RF']}},resources:[]}}});
   blocked.push(p);return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));await page.clock.install({time:new Date('2026-11-01T01:00:00+08:00')});await page.clock.pauseAt(new Date('2026-11-01T01:00:01+08:00'));
  const combined=()=>page.locator('.paper-citation-panel'),panel=()=>page.locator('.paper-patent-citations'),toggle=()=>combined().locator('.reference-toggle'),patentTab=()=>combined().locator('.citation-type-tab[id$="-tab-patents"]'),paperTab=()=>combined().locator('.citation-type-tab[id$="-tab-papers"]'),pposts=()=>posts.filter(x=>x.path.endsWith('/patent-citations/ensure')),preads=()=>requests.filter(x=>x.path.endsWith('/patent-citations'));
  async function settled(){await page.waitForFunction(()=>{const p=document.querySelector('.paper-patent-citations');return !!p&&!p.textContent.includes('正在读取专利被引…');});}
  async function refresh(){await panel().getByRole('button',{name:'刷新状态',exact:true}).click();await settled();}
  async function update(){await panel().getByRole('button',{name:'更新专利被引',exact:true}).click();await settled();}
  async function open(){await page.goto(origin+'/papers/'+number,{waitUntil:'networkidle'});await toggle().waitFor();if(await toggle().getAttribute('aria-expanded')==='false')await toggle().click();await patentTab().click();await settled();}
  await page.goto(origin+'/papers/'+number,{waitUntil:'networkidle'});assert.equal(await toggle().getAttribute('aria-expanded'),'false');assert.equal(pposts().length,1);assert.deepEqual(pposts()[0].data,{});
  assert(await panel().evaluate(el=>!!(document.querySelector('.paper-citations').compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING)&&!!(el.compareDocumentPosition(document.querySelector('.keywords-panel'))&Node.DOCUMENT_POSITION_FOLLOWING)));
  assert.equal(await combined().locator('h2').count(),1);assert.equal(await combined().innerText(),'被引');assert.equal(await combined().locator('.citation-overview').count(),0);assert.equal(await page.locator('.paper-citations [role="tab"]').count(),2);
  await toggle().click();assert.equal(await paperTab().locator('span').innerText(),'3');assert.equal(await patentTab().locator('span').innerText(),'55');assert.equal(await paperTab().getAttribute('aria-selected'),'true');await patentTab().click();await settled();
  const initialPosts=posts.length;for(let i=0;i<3;i++){await paperTab().click();await patentTab().click();}assert.equal(posts.length,initialPosts);assert.equal(await panel().locator('li').count(),50);await paperTab().click();await paperTab().press('ArrowRight');assert.equal(await patentTab().getAttribute('aria-selected'),'true');await patentTab().press('Home');assert.equal(await paperTab().getAttribute('aria-selected'),'true');await patentTab().click();
  assert.equal(await panel().locator('li').count(),50);assert((await panel().innerText()).includes('已载入 50 / 55 条'));assert.equal(await panel().getByRole('button',{name:'更新专利被引'}).isDisabled(),true);
  assert.equal(await panel().locator('li').first().locator('a').getAttribute('href'),'https://patents.google.com/patent/US1234567B2/en');assert((await panel().locator('li').nth(1).locator('a').getAttribute('href')).startsWith('https://patents.google.com/?q='));assert.equal(await panel().locator('a[href^="/papers/"]').count(),0);assert(await panel().locator('.katex').count()>0);
  const headingStyles=await toggle().evaluate(el=>({fontSize:getComputedStyle(el).fontSize,fontWeight:getComputedStyle(el).fontWeight}));assert.deepEqual(headingStyles,{fontSize:'17px',fontWeight:'650'});
  mode='new';state='complete';badPage=true;await panel().getByRole('button',{name:'加载更多专利被引'}).click();await panel().getByRole('alert').waitFor();assert.equal(await panel().locator('li').count(),50);assert((await panel().getByRole('alert').innerText()).includes('快照不一致'));
  await panel().getByRole('button',{name:'加载更多专利被引'}).click();await panel().locator('li').nth(51).waitFor();assert.equal(await panel().locator('li').count(),52);assert(preads().filter(x=>x.offset>0).every(x=>x.version===v1));await paperTab().click();await patentTab().click();assert.equal(await panel().locator('li').count(),52);assert.equal(pposts().length,1);
  await refresh();assert.equal(pposts().length,1);assert.equal(await panel().locator('li').count(),3);assert((await panel().locator('li').first().innerText()).includes('new'));
  state='fetching';await update();assert.equal(pposts().length,2);assert.deepEqual(pposts().at(-1).data,{refresh:true});assert.equal(await panel().locator('li').count(),3);
  readError=true;await page.clock.fastForward(2100);await panel().getByRole('alert').waitFor();assert.equal(await panel().locator('li').count(),3);const disconnectedReads=preads().length;await page.clock.fastForward(6100);assert.equal(preads().length,disconnectedReads);assert.equal(pposts().length,2);readError=false;
  mode='failure';await refresh();await panel().getByText('更新未完成，已有结果仍可查看。',{exact:true}).waitFor();assert.equal(await panel().locator('li').count(),3);assert((await panel().innerText()).includes('2026/10/20'));assert(!(await panel().innerText()).includes('patent_citations_unavailable'));
  const stopped=preads().length;await page.clock.fastForward(6100);assert.equal(preads().length,stopped);assert.equal(pposts().length,2);
  mode='absent';await refresh();assert.equal(await combined().locator('.citation-overview').count(),0);assert.equal((await panel().innerText()).split('官网未提供专利被引栏目').length-1,1);assert(!(await panel().innerText()).includes('官网当前记录 0 条专利被引'));assert.equal(await patentTab().locator('span').innerText(),'—');
  mode='zero';await refresh();assert.equal(await panel().locator('.references-status>span').innerText(),'官网当前记录 0 条专利被引');assert.equal(await patentTab().locator('span').innerText(),'0');assert.equal(await panel().locator('li').count(),0);await page.getByRole('button',{name:'English',exact:true}).click();assert.equal(await panel().locator('.references-status>span').innerText(),'IEEE Xplore currently lists 0 patent citations');assert.equal(await panel().locator('.patent-citations-empty').count(),0);assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));await page.getByRole('button',{name:'中文',exact:true}).click();
  mode='unknown';await open();assert((await panel().innerText()).includes('数量待确认'));assert.equal(await patentTab().locator('span').innerText(),'—');assert(!(await panel().innerText()).includes('0 / 0'));assert(!(await panel().innerText()).includes('patent_citations_unavailable'));
  mode='fixture';await refresh();assert.equal(await panel().locator('li').count(),2);assert((await panel().innerText()).includes('已载入 2 / 3 条'));
  readError=true;await refresh();assert.equal(await panel().locator('li').count(),2);assert.equal(await panel().getByRole('alert').innerText(),'专利被引暂不可读取。');readError=false;
  ensureError=true;await update();assert.equal(await panel().locator('li').count(),2);assert(!(await panel().innerText()).includes('patent_citations_unavailable'));ensureError=false;await refresh();
  await page.getByRole('button',{name:'English',exact:true}).click();assert.equal(await toggle().innerText(),'Citations');assert.equal(await toggle().getAttribute('aria-label'),'Collapse citations');assert((await panel().innerText()).includes('2 / 3 loaded'));assert((await panel().innerText()).includes('Patent on Google Patents'));await page.getByRole('button',{name:'中文',exact:true}).click();
  if(process.env.CIRDC_BROWSER_OUTPUT){await fs.mkdir(process.env.CIRDC_BROWSER_OUTPUT,{recursive:true});await combined().screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,profile.name+'-patent-panel.png')});}
  mode='disabled';const beforeDisabled=pposts().length;await open();assert.equal(pposts().length,beforeDisabled);assert.equal(await panel().getByRole('button',{name:'更新专利被引'}).isDisabled(),true);await refresh();assert.equal(pposts().length,beforeDisabled);
  mode='unknown';await open();assert.equal(pposts().length,beforeDisabled+1);assert.equal(await patentTab().locator('span').innerText(),'—');const unknownReads=preads().length;await page.clock.fastForward(6100);assert.equal(preads().length,unknownReads);
  mode='old';state='queued';holdEnsure=true;const held=new Promise(resolve=>{heldResolve=resolve;});await page.reload({waitUntil:'domcontentloaded'});await held;
  await page.evaluate(id=>{history.pushState({},'','/papers/'+id);dispatchEvent(new PopStateEvent('popstate'));},other);await page.locator('#paper-patent-citations-'+other).waitFor({state:'attached'});releaseHeld();holdEnsure=false;await toggle().click();await patentTab().click();await settled();assert((await panel().innerText()).includes('专利被引功能尚未启用'));assert.equal(await panel().locator('li').count(),0);assert.equal(pposts().filter(x=>x.path.includes('/'+other+'/')).length,0);
  const oldReads=preads().filter(x=>x.path.includes('/'+number+'/')).length;await page.clock.fastForward(4100);assert.equal(preads().filter(x=>x.path.includes('/'+number+'/')).length,oldReads);
  mode='fixture';state='complete';paperGroups='single';await open();await paperTab().click();assert.equal(await page.locator('.paper-citations [role="tab"]').count(),0);await patentTab().click();assert.equal(await panel().locator('li').count(),2);assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);
  paperGroups='both';mode='fixture';await open();await paperTab().click();
  const styles=await paperTab().evaluate(el=>{const css=getComputedStyle(el);return {radius:css.borderTopLeftRadius,border:css.borderTopWidth,background:css.backgroundColor,size:css.fontSize};});
  const inner=await page.locator('.paper-citations .citation-groups [aria-selected="true"]').evaluate(el=>{const css=getComputedStyle(el);return {radius:css.borderTopLeftRadius,border:css.borderTopWidth,background:css.backgroundColor,size:css.fontSize};});assert.deepEqual(styles,inner);assert.equal(styles.border,'1px');assert.notEqual(styles.radius,'0px');
  paperGroups='absent';mode='absent';await open();await paperTab().click();await page.waitForFunction(()=>document.querySelector('.paper-citations .references-status>span')?.textContent==='官网未提供被引论文栏目');
  assert.equal((await combined().innerText()).split('官网未提供被引论文栏目').length-1,1);assert.equal(await combined().locator('.citation-overview').count(),0);assert.equal(await page.locator('.paper-citations .citation-snapshot-meta time').count(),1);assert(!(await combined().innerText()).includes('上次检查'));assert(!(await combined().innerText()).includes('最近更新尝试'));assert((await page.locator('.paper-citations time').getAttribute('title')).includes('最近更新尝试'));
  await patentTab().click();await settled();assert.equal((await combined().innerText()).split('官网未提供专利被引栏目').length-1,1);assert.equal(await panel().locator('.citation-snapshot-meta time').count(),1);
  if(process.env.CIRDC_BROWSER_OUTPUT)await combined().screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,profile.name+'-single-absence.png')});
  await toggle().click();assert.equal(await combined().innerText(),'被引');assert.equal(await combined().locator('.citation-overview').count(),0);
  await page.getByRole('button',{name:'English',exact:true}).click();assert.equal(await combined().innerText(),'Citations');await toggle().click();assert((await paperTab().innerText()).includes('By Papers'));assert((await patentTab().innerText()).includes('By Patents'));assert.equal(await patentTab().getAttribute('aria-selected'),'true');assert((await panel().locator('time').innerText()).startsWith('Checked:'));
  const report={profile:profile.name,collapsedTitleOnly:true,expandedTabCountsPreserved:true,localizedTypeTabs:true,tabStylesMatchGroupButtons:true,singleStatusMessage:true,singleCheckTime:true,latestAttemptAvailableOnHover:true,mergedPanel:true,twoCitationTypeTabs:true,tabSwitchDoesNotEnsureAgain:true,keyboardTabNavigation:true,defaultCollapsed:true,placement:true,independentPaperCounts:true,paperGroupVisibilityPreserved:true,sourceAndSavedCounts:true,pinnedPagination:true,mismatchRejected:true,statusRefreshReadOnly:true,ensureOncePerOpen:true,explicitRefresh:true,pendingOnlyPolling:true,pollingStopsOnReadError:true,preservedFailedSnapshot:true,absenceZeroUnknownDistinct:true,zeroCountsBoundedToPublisher:true,internalErrorsHidden:true,disabledDoesNotPost:true,paperSwitchRaceCleared:true,googlePatentsOnly:true,formulaRendering:true,bilingual:true,noHorizontalOverflow:true,sourceRequests:0,realApiRequests:0};reports.push(report);console.log(JSON.stringify(report));await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'browser-result.json'),JSON.stringify({reports},null,2)+'\n');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
