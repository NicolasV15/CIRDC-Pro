/* Cached-profile fixtures only. No author acquisition or database writes.
 * Optional CIRDC_AUTHOR_IDENTITY_FIXTURE / CIRDC_AUTHOR_PROFILE_FIXTURE use a
 * private cached example; CIRDC_AUTHOR_LIVE_ORIGIN serves only HTML/assets live. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin=process.env.CIRDC_AUTHOR_LIVE_ORIGIN||'http://author-affiliation.test';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.woff2':'font/woff2','.woff':'font/woff'};
async function main(){
 const local=process.env.CIRDC_AUTHOR_IDENTITY_FIXTURE?JSON.parse(await fs.readFile(process.env.CIRDC_AUTHOR_IDENTITY_FIXTURE,'utf8')).author:{source:'ieee',author_id:'87000001',identity_key:'ieee:87000001',display_name:'Example Author',papers:19,first_year:2017,last_year:2026,name_variants:['Example Author']};
 const profile=process.env.CIRDC_AUTHOR_PROFILE_FIXTURE?JSON.parse(await fs.readFile(process.env.CIRDC_AUTHOR_PROFILE_FIXTURE,'utf8')):{author:{source:'ieee',author_id:local.author_id,fetch_state:'complete',profile:{is_hidden:false,current_affiliations:['Department of Electrical Engineering, Example University, Example City']}}};
 const other={...local,author_id:'87000002',identity_key:'ieee:87000002',papers:5},baseAffiliations=profile.author.profile.current_affiliations;
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const settings of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844,touch:true},{name:'narrow-dark',width:320,height:760,touch:true,dark:true}]){
  const context=await browser.newContext({viewport:{width:settings.width,height:settings.height},isMobile:!!settings.touch,hasTouch:!!settings.touch,colorScheme:settings.dark?'dark':'light'}),requests=[],blocked=[],errors=[];let mode='ready',held=null,heldReady;let heldPromise=new Promise(resolve=>{heldReady=resolve;});
  await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  const authorURL=id=>origin+'/?'+new URLSearchParams({field:'authors',q:local.display_name,author_source:'ieee',author_id:id,limit:'25'});
  const paper={number:'83001101',title:'Cached author paper',authors:local.display_name,author_refs:[],kind:'Journals',venue:'4',publication:'Fixture',year:2026,snippet:'Cached summary.',resources:[]};
  function response(id,scenario=mode){const value=JSON.parse(JSON.stringify(profile));value.author.source='ieee';value.author.author_id=id;
   if(id===other.author_id)value.author.profile.current_affiliations=['Other identity institution'];
   if(scenario==='empty')value.author.profile.current_affiliations=[];
   if(scenario==='missing')return {author:null,status:'not_fetched'};
   if(scenario==='hidden'){value.author.fetch_state='hidden';value.author.profile.is_hidden=true;value.author.profile.current_affiliations=['HIDDEN STORED VALUE'];}
   if(scenario==='mismatch')value.author.author_id='87000999';
   if(scenario==='multiple')value.author.profile.current_affiliations=[...baseAffiliations,'Second Institute · '+('LongInstitutionName'.repeat(12))];
   return value;
  }
  await context.route('**/*',async route=>{const req=route.request(),u=new URL(req.url()),p=u.pathname;requests.push({method:req.method(),path:p});if(req.method()!=='GET'||u.origin!==origin){blocked.push(req.method()+' '+req.url());return route.abort();}
   if(p==='/')return process.env.CIRDC_AUTHOR_LIVE_ORIGIN?route.continue():route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return process.env.CIRDC_AUTHOR_LIVE_ORIGIN?route.continue():route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
   if(p==='/api/overview')return route.fulfill({json:{index:{phase:'ready',year_range:{min:1884,max:2027},overview:{papers:19,venues:[],field_states:[]}}}});
   if(p==='/api/venues')return route.fulfill({json:{items:[]}});
   if(p==='/api/papers')return route.fulfill({json:{items:[paper],total:19,next_cursor:null,partial:false}});
   if(p==='/api/authors')return route.fulfill({json:{items:[local,other],next_cursor:null,unidentified_papers:0,index:{authors_phase:'ready'}}});
   if(p.startsWith('/api/authors/ieee/'))return route.fulfill({json:{author:p.endsWith(other.author_id)?other:local}});
   if(p.startsWith('/api/author-profiles/ieee/')){const id=p.split('/').at(-1);if(mode==='hold'&&id===local.author_id){held={route,id};heldReady();return;}if(mode==='error')return route.fulfill({status:503,json:{error:'fixture_unavailable'}});return route.fulfill({json:response(id)});}
   blocked.push(p);return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
  const card=()=>page.locator('.pinned-author>.author-match'),aff=()=>card().locator('.author-affiliation');
  const profileRequests=()=>requests.filter(r=>r.path.startsWith('/api/author-profiles/'));
  async function heldRequest(){let timer;try{await Promise.race([heldPromise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Profile request not held')),12000);})]);}finally{clearTimeout(timer);}}
  async function switchIdentity(id){await page.evaluate(({id,name})=>{history.pushState({},'','/?'+new URLSearchParams({field:'authors',q:name,author_source:'ieee',author_id:id,limit:'25'}));dispatchEvent(new PopStateEvent('popstate'));},{id,name:local.display_name});await page.locator('.pinned-author>.author-match[data-author-id="'+id+'"]').waitFor();}
  // Ordinary author-name browsing does not request profiles for every candidate.
  await page.goto(origin+'/?field=authors&q='+encodeURIComponent(local.display_name),{waitUntil:'networkidle'});await page.locator('.author-candidate-card').first().waitFor();assert.equal(profileRequests().length,0);
  mode='hold';await page.goto(authorURL(local.author_id),{waitUntil:'domcontentloaded'});await page.locator('.paper-row').first().waitFor();await card().getByText(local.display_name,{exact:true}).waitFor();await heldRequest();assert.equal(await aff().count(),0);assert.equal(await page.locator('.paper-row').count(),1,'Paper results must not wait for the profile');mode='ready';await held.route.fulfill({json:response(held.id,'ready')});await aff().waitFor();assert.deepEqual(await aff().locator('li').allTextContents(),baseAffiliations);
  const label=await aff().locator('dt').innerText();assert.equal(label,'机构');const a=await aff().boundingBox(),summary=await card().locator('.author-identity-summary').boundingBox();if(settings.touch)assert(a.y>=summary.y+summary.height);else assert(a.x>=summary.x+summary.width);
  const reads=profileRequests().length;await page.getByRole('button',{name:'展开其他同名作者',exact:true}).click();await page.locator('.author-candidate-card').waitFor();assert.equal(profileRequests().length,reads,'Candidate expansion must not fetch candidate profiles');assert.equal(await page.locator('.author-candidate-card [data-author-id="'+local.author_id+'"]').count(),0);
  assert((await page.locator('.pinned-author .author-profile-link').getAttribute('href')).endsWith('/'+local.author_id));assert((await page.locator('.pinned-author .ieee-author-source').getAttribute('href')).endsWith('/'+local.author_id));
  for(const theme of ['classic-green','plain-white','graphite','paper','midnight','lavender']){await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));}
  await page.evaluate(value=>document.documentElement.dataset.theme=value,settings.dark?'graphite':'plain-white');if(process.env.CIRDC_BROWSER_OUTPUT){await card().scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,'author-affiliation-'+settings.name+'.png')});}
  await page.getByRole('button',{name:'English',exact:true}).click();assert.equal(await aff().locator('dt').innerText(),'Affiliation');assert.deepEqual(await aff().locator('li').allTextContents(),baseAffiliations);assert.equal(profileRequests().length,reads);await page.getByRole('button',{name:'中文',exact:true}).click();
  await page.locator('.author-candidate-card [data-author-id="'+other.author_id+'"]').click();await card().filter({hasText:other.author_id}).waitFor();await aff().getByText('Other identity institution',{exact:true}).waitFor();assert(!(await aff().innerText()).includes(baseAffiliations[0]));
  // A response for a previous same-name identity cannot replace the new identity.
  mode='hold';held=null;heldPromise=new Promise(resolve=>{heldReady=resolve;});await switchIdentity(local.author_id);await heldRequest();assert.equal(await aff().count(),0);await switchIdentity(other.author_id);await aff().getByText('Other identity institution',{exact:true}).waitFor();await held.route.fulfill({json:response(local.author_id,'ready')});await page.waitForLoadState('networkidle');assert.deepEqual(await aff().locator('li').allTextContents(),['Other identity institution']);
  for(const scenario of ['empty','missing','hidden','mismatch','error']){mode=scenario;await page.goto(authorURL(local.author_id),{waitUntil:'networkidle'});await card().getByText(local.display_name,{exact:true}).waitFor();assert.equal(await aff().count(),0,scenario);assert.equal(await page.locator('.paper-row').count(),1);assert.equal(await page.locator('.pinned-author [role=alert]').count(),0,scenario+' must not block the identity');}
  mode='multiple';await page.goto(authorURL(local.author_id),{waitUntil:'networkidle'});await aff().waitFor();assert.equal(await aff().locator('li').count(),2);assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);reports.push({profile:settings.name,sourceAffiliation:true,responsiveCard:true,nonBlocking:true,onlySelectedProfileRequested:true,stableAcrossLanguageAndThemes:true,profileLinksPreserved:true,sameNameIdentityAndLateResponseSafe:true,missingHiddenMismatchAndFailureSafe:true,multipleLongAffiliations:true,sourceAcquisitions:0,writes:0});console.log(JSON.stringify(reports.at(-1)));await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'author-affiliation-result.json'),JSON.stringify({reports},null,2)+'\n');
}
main().catch(error=>{console.error(error);process.exitCode=1});
