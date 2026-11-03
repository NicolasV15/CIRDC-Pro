/* Fixture-only full-text search and passage location. Set PLAYWRIGHT_MODULE, optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE and CIRDC_BROWSER_OUTPUT. All requests are mocked; nothing is written. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://fulltext-search.test';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
const fixture=require('./fixtures/fulltextPassages.json');
const alternatives=[['sar adc','sar adcs','successive approximation adc','successive approximation register adc']];
const hitOrdinals=[4,7,11];
function highlight(text){const ranges=[];for(const needle of ['successive-approximation ADC','SAR ADC']){let at=text.indexOf(needle);while(at>=0){ranges.push([at,at+needle.length]);at=text.indexOf(needle,at+1);}}return {text,highlights:ranges.sort((a,b)=>a[0]-b[0])};}
function passage(row,version='v1'){return {ordinal:row.ordinal,kind:row.kind,section:row.section,section_id:null,version,fingerprint:row.fingerprint,match:'terms',excerpt:highlight(row.text)};}
const hits=hitOrdinals.map(ordinal=>passage(fixture.passages[ordinal]));
function paper(number,title,extra){return {number,title,authors:'Lin Zhang',author_refs:[],publication:'IEEE Journal of Solid-State Circuits',venue:'4',venue_series:['4'],kind:'Journals',year:2025,doi:'',snippet:'Metadata abstract.',abstract_state:'complete',keywords_state:'complete',resources:[],...extra};}
const query={terms:'expand',groups:[{kind:'concept',text:'sar adc',label:'SAR ADC',alternatives:alternatives[0],equivalents:['successive approximation ADC','SAR analog-to-digital converter'],related:['pipelined ADC']}],match:'terms',alternatives};
async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const profile of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844,touch:true},{name:'narrow-dark',width:320,height:760,touch:true,dark:true}]){
  const context=await browser.newContext({viewport:{width:profile.width,height:profile.height},locale:'zh-CN',isMobile:!!profile.touch,hasTouch:!!profile.touch,colorScheme:profile.dark?'dark':'light'});
  await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  const requests=[],writes=[],blocked=[],errors=[];let document={version:'v1',html:fixture.html},passageMode='hits',indexFailed=false;
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   if(url.origin!==origin){blocked.push(req.url());return route.abort();}
   if(req.method()!=='GET'){writes.push(req.method()+' '+p);return route.abort();}
   requests.push(p+url.search);
   if(p==='/'||p.startsWith('/papers/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
   if(p==='/api/overview')return route.fulfill({json:{index:{phase:'ready',year_range:{min:1990,max:2027},overview:{papers:2,venues:[],field_states:[]}}}});
   if(p==='/api/papers'){
    const s=url.searchParams;
    if(s.get('field')==='body'){
     if(s.get('totals')==='only')return route.fulfill({json:{total:2,items:[],next_cursor:null}});
     return route.fulfill({json:{view:s.get('view')||'all',query:{...query,terms:s.get('terms')||'expand'},fulltext:{enabled:true,phase:'ready',documents:2,cataloged:indexFailed?3:2,pending:indexFailed?1:0,failed:indexFailed?1:0,blocked:indexFailed?1:0},total:s.get('totals')==='defer'?null:2,next_cursor:null,
      items:[paper('301','Pipelined-SAR fixture',{passages:hits,passage_total:3,position:s.get('view')==='top'?1:undefined}),paper('302','Second fixture',{passages:[passage({ordinal:1,kind:'text',section:'Results',text:'The SAR ADC achieves 62 dB.',fingerprint:'the sar adc achieves 62 db'})],passage_total:1,position:s.get('view')==='top'?2:undefined})]}});
    }
    if(s.get('view')==='top')return route.fulfill({json:{view:'top',k:Number(s.get('k')||20),total:2,next_cursor:null,query,items:[
     paper('301','Pipelined-SAR fixture',{position:1,flags:{exact_title:false,title_phrase:false,author_name:false},reasons:[{field:'title',terms:[{query:'sar adc',matched:['SAR ADC'],alias:false}]}],excerpt:{field:'abstract',...highlight('A SAR ADC abstract.')}}),
     paper('302','Second fixture',{position:2,flags:{},reasons:[{field:'abstract',terms:[{query:'sar adc',matched:['successive-approximation ADC'],alias:true}]}],excerpt:null})]}});
    return route.fulfill({json:{items:[paper('301','Pipelined-SAR fixture')],total:s.get('totals')==='defer'?null:1,next_cursor:null,query}});
   }
   if(p==='/api/papers/301'||p==='/api/papers/302')return route.fulfill({json:{paper:{number:p.slice(12),record:{articleTitle:'Fixture paper',authors:[],abstract:'Metadata abstract.',keywords:{}},resources:[{kind:'document',href:'/api/content/'+p.slice(12)}]}}});
   if(/^\/api\/content\/30[12]$/.test(p))return route.fulfill({json:{state:'ready',document:{source:'ieee_html',version:document.version,state:'ready',body_url:p+'/body',toc:[{id:'sec1-h',title:'I. Introduction',level:2},{id:'sec2-h',title:'II. Architecture',level:2}],assets_ready:0,assets_total:0}}});
   if(/^\/api\/content\/30[12]\/body$/.test(p))return route.fulfill({contentType:'text/html',body:document.html});
   if(/^\/api\/papers\/30[12]\/passages$/.test(p)){
    const items=passageMode==='all'?fixture.passages.map(row=>passage(row)):passageMode==='missing'?[{...hits[0],fingerprint:'a passage that is not in this document'}]:hits;
    return route.fulfill({json:{number:p.split('/')[3],state:'indexed',version:'v1',items,total:items.length,next_offset:null,query:{match:'terms',alternatives}}});
   }
   if(p.endsWith('/metadata/status'))return route.fulfill({json:{state:'disabled'}});
   if(p.endsWith('/references')||p.endsWith('/citations')||p.endsWith('/patent-citations'))return route.fulfill({json:{number:p.split('/')[3],state:'disabled',version:null,items:[],total:0,next_offset:null,group:url.searchParams.get('group')||'ieee',counts:{ieee:null,nonIeee:null,total:null},stored_counts:{ieee:0,nonIeee:0,total:0},group_states:{ieee:'disabled',nonIeee:'disabled'},source_presence:'unknown',empty_reason:null,expected_total:null,checked_at:null,last_attempt_at:null,next_check_at:null,stale:false,error:null,offset:0,limit:50}});
   blocked.push(p);return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
  const focused=()=>page.locator('.document-passage-focus');
  // Tokens of the focused block with the reader's own formula and label handling.
  const tokensOf=el=>{if(!el)return '';const copy=el.cloneNode(true);copy.querySelectorAll('.document-math-source,.document-section-number').forEach(n=>n.remove());copy.querySelectorAll('.doc-math').forEach(n=>n.replaceWith(' ⋯ '));copy.querySelectorAll('td,th,br').forEach(n=>n.before(' '));
   return Array.from(copy.textContent.normalize('NFKC').matchAll(/[\p{L}\p{N}]+/gu),m=>m[0].normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase()).slice(0,12).join(' ');};
  const focusedTokens=()=>page.evaluate(`(${tokensOf})(document.querySelector('.document-passage-focus'))`);
  // The navigator updates the address before the reader moves its highlight in the next commit.
  async function expectFocus(fingerprint,label){
   try{await page.waitForFunction(`(${tokensOf})(document.querySelector('.document-passage-focus'))===${JSON.stringify(fingerprint)}`,null,{timeout:5000});}
   catch{assert.equal(await focusedTokens(),fingerprint,label);}
  }
  const noOverflow=async label=>assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),label+' overflow at '+profile.name);

  // Full-text results explain their scope and show highlighted passages with sections.
  await page.goto(origin+'/?q=SAR+ADC&field=body',{waitUntil:'networkidle'});
  await page.locator('.passage-hit').first().waitFor();
  const insight=await page.locator('.search-insights').innerText();
  assert(insight.includes('正文检索范围：已索引 2 篇论文正文')&&insight.includes('同一段落同时包含全部检索词'));
  assert(insight.includes('同时匹配')&&insight.includes('pipelined ADC'));
  assert.equal(await page.locator('.paper-row').first().locator('.passage-hit').count(),3);
  assert.equal(await page.locator('.passage-hit').first().locator('mark.hit').first().innerText(),'successive-approximation ADC');
  assert((await page.locator('.passage-hit').first().locator('.passage-section').innerText()).includes('II. Architecture'));
  await page.waitForFunction(()=>document.querySelector('.result-total')?.textContent.includes('2'));
  await noOverflow('results');

  // A passage link opens the reader at that indexed paragraph and walks through every hit.
  await page.locator('.passage-hit').first().locator('.passage-open').click();
  await focused().waitFor();
  assert.equal(new URL(page.url()).pathname,'/papers/301');
  assert.equal(new URL(page.url()).searchParams.get('passage'),'4');
  await expectFocus(fixture.passages[4].fingerprint,'first hit');
  assert.equal(await page.locator('.passage-count').innerText(),'1 / 3');
  assert.equal(await page.locator('.passage-notice').count(),0);
  assert(await focused().evaluate(el=>{const r=el.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0;}),'focused passage is visible');
  for(const [index,ordinal] of hitOrdinals.entries()){
   if(index){await page.getByRole('button',{name:'下一处命中',exact:true}).click();await page.waitForFunction(o=>new URL(location.href).searchParams.get('passage')===String(o),ordinal);}
   await expectFocus(fixture.passages[ordinal].fingerprint,'hit '+ordinal);
  }
  assert.equal(await page.locator('.passage-count').innerText(),'3 / 3');
  assert(await page.getByRole('button',{name:'下一处命中',exact:true}).isDisabled());
  await noOverflow('reader');
  if(process.env.CIRDC_BROWSER_OUTPUT){await fs.mkdir(process.env.CIRDC_BROWSER_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,profile.name+'-located.png')});}
  await page.getByRole('button',{name:'退出定位',exact:true}).click();
  assert.equal(await page.locator('.passage-navigator').count(),0);
  assert.equal(await focused().count(),0);
  assert.equal(new URL(page.url()).search,'');

  // Every indexed passage, including headings after merged labels, captions and table rows, maps one-to-one.
  passageMode='all';
  await page.goto(origin+'/papers/301?passage=0&v=v1&q=all',{waitUntil:'networkidle'});
  await focused().waitFor();
  for(const row of fixture.passages){
   if(row.ordinal){await page.getByRole('button',{name:'下一处命中',exact:true}).click();await page.waitForFunction(o=>new URL(location.href).searchParams.get('passage')===String(o),row.ordinal);}
   await expectFocus(row.fingerprint,'ordinal '+row.ordinal);
   assert.equal(await page.locator('.passage-notice').count(),0,'ordinal '+row.ordinal+' located without relocation');
  }

  // A changed document version is relocated by wording; a missing paragraph is reported, never guessed.
  passageMode='hits';document={version:'v2',html:'<p>An erratum paragraph added before the original text.</p>'+fixture.html};
  await page.goto(origin+'/papers/301?passage=4&v=v1&q=SAR+ADC',{waitUntil:'networkidle'});
  await page.locator('.passage-notice').waitFor();
  assert.equal(await page.locator('.passage-notice').innerText(),'正文版本已更新，已按段落文字重新定位。');
  await expectFocus(fixture.passages[4].fingerprint,'relocated');
  passageMode='missing';
  await page.goto(origin+'/papers/301?passage=4&v=v1&q=SAR+ADC',{waitUntil:'networkidle'});
  await page.locator('.passage-notice.is-missing').waitFor();
  assert.equal(await focused().count(),0);
  passageMode='hits';document={version:'v1',html:fixture.html};

  // Top-K is a ranked, explained subset; the all-matches view keeps paging and exact totals.
  await page.goto(origin+'/?q=SAR+ADC&view=top&k=10',{waitUntil:'networkidle'});
  await page.locator('.paper-position').first().waitFor();
  assert.equal(await page.locator('.paper-position').first().innerText(),'#1');
  assert((await page.locator('.result-total').innerText()).includes('前 2 篇')&&(await page.locator('.result-total').innerText()).includes('共 2 篇匹配'));
  assert(await page.locator('.match-reasons li').first().innerText().then(text=>text.includes('标题')));
  assert((await page.locator('.match-reasons').nth(1).innerText()).includes('（等价写法）'));
  assert.equal(await page.locator('.load-more').count(),0);
  assert.equal(await page.locator('.page-size-control').count(),0);
  assert(requests.some(r=>r.startsWith('/api/papers?')&&r.includes('view=top')&&r.includes('k=10')));
  await page.locator('.alias-toggle input').uncheck();
  await page.waitForFunction(()=>new URL(location.href).searchParams.get('terms')==='exact');
  assert(requests.some(r=>r.startsWith('/api/papers?')&&r.includes('terms=exact')&&r.includes('view=top')));
  await noOverflow('top view');

  // Language switching keeps the reader state and localizes the explanations.
  await page.goto(origin+'/papers/301?passage=7&v=v1&q=SAR+ADC',{waitUntil:'networkidle'});
  await focused().waitFor();
  await page.getByRole('button',{name:'English',exact:true}).click();
  assert((await page.locator('.passage-navigator').innerText()).includes('Full-text hits'));
  await expectFocus(fixture.passages[7].fingerprint,'english');

  indexFailed=true;
  await page.goto(origin+'/?q=SAR+ADC&field=body',{waitUntil:'networkidle'});
  // The fixture init script restores Chinese on each full-page navigation.
  await page.getByText('其中 1 篇索引失败，1 篇已暂停重试。',{exact:true}).waitFor();
  await noOverflow('failed index chinese');
  await page.getByRole('button',{name:'English',exact:true}).click();
  await page.getByText('Indexing failed for 1 papers; retries are paused for 1.',{exact:true}).waitFor();
  await noOverflow('failed index english');

  assert.deepEqual(writes,[]);assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);
  reports.push({profile:profile.name,bodyResultsExplained:true,highlighted:true,locatedFromResult:true,hitNavigation:3,parityPassages:fixture.passages.length,versionRelocation:true,missingReported:true,topK:true,aliasToggle:true,bilingual:true,writes:0,sourceRequests:0});
  console.log(JSON.stringify(reports.at(-1)));await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'fulltext-search-result.json'),JSON.stringify({reports},null,2)+'\n');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
