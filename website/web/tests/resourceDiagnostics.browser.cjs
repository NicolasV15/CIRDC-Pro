/* Read-only administrator fixture: no source requests, retries or configuration writes. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=process.env.CIRDC_WEB_STATIC||path.resolve(__dirname,'../../src/cirdc/web/static');
const origin='http://resource-outcomes.test';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff'};
const diagnostic={nodes:[{id:'fixture-node',label:'Fixture node',last_seen:Date.now()/1000}],counts:{},
 pdf_acquisition_counts:{ready:2,queued:0,fetching:0,unavailable:1,failed:3},
 jobs:[{id:'unlicensed',number:'12345678',node:'fixture-node',kind:'ieee_pdf',state:'unavailable',attempt_state:'failed',error:'pdf_not_entitled',unavailable_reason:'institution_not_licensed',errors:JSON.stringify([{code:'pdf_not_entitled'}])},
       {id:'network',number:'12345679',kind:'ieee_pdf',state:'failed',attempt_state:'failed',error:'network_error',deferred:true},
       {id:'refresh',number:'12345680',kind:'ieee_pdf',state:'failed',attempt_state:'failed',error:'network_error',availability_state:'ready',is_refresh:true}],
 pdf_todos:[{number:'12345679',state:'pending',reason:'network_error',updated:0,attempts:1,auto_attempts:1,auto_max_attempts:3,auto_retry_eligible:true,next_retry_at:1800021600},{number:'12345681',state:'pending',reason:'access_restricted',updated:0,attempts:3,auto_attempts:3,auto_max_attempts:3,auto_retry_eligible:true,auto_retry_exhausted:true,next_retry_at:null},{number:'12345682',state:'pending',reason:'pdf_upload_changed',updated:0,attempts:0,auto_attempts:0,auto_max_attempts:3,auto_retry_eligible:false}],pdf_todo_counts:{pending:3}};

async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});
 const reports=[];
 try{for(const profile of [{name:'desktop-zh',width:1440,lang:'zh'},{name:'mobile-zh',width:390,lang:'zh'},{name:'mobile-en',width:390,lang:'en'}]){
  const context=await browser.newContext({viewport:{width:profile.width,height:1000},locale:profile.lang==='en'?'en-US':'zh-CN'});
  const mutations=[],external=[],errors=[];
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   if(req.method()!=='GET'){mutations.push(p);return route.abort();}
   if(url.origin!==origin){external.push(req.url());return route.abort();}
   if(p==='/admin/')return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'admin',user:{username:'fixture-admin',role:'admin',must_change:false},csrf:'fixture'}});
   if(p==='/api/admin/runs')return route.fulfill({json:{items:[]}});
   if(p==='/api/admin/overview')return route.fulfill({json:{index:{phase:'ready',overview:{papers:4,field_states:[],venues:[]}}}});
   if(p==='/api/admin/resources')return route.fulfill({json:{items:[{id:'fixture-resources',title:'Fixture resources',description:'Read-only diagnostic fixture',root_dir:'/fixture',diagnostics:diagnostic}]}});
   if(p.startsWith('/api/'))return route.fulfill({json:{status:'disabled',items:[]}});
   return route.abort();
  });
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin+'/admin/');
  if(profile.lang==='en')await page.getByRole('button',{name:'English',exact:true}).click();
  await page.getByRole('button',{name:profile.lang==='en'?'Index and diagnostics':'索引与预检',exact:true}).click();
  const section=page.locator('.resource-settings');
  const heading=section.getByRole('heading',{name:profile.lang==='en'?'PDF retrieval outcomes (per paper)':'PDF 获取结果（按论文）'});
  await heading.waitFor();
  const summary=heading.locator('xpath=following-sibling::table[1]');
  const unlicensedLabel=profile.lang==='en'?'Confirmed unavailable (institution not licensed)':'已确认不可获取（机构未授权）';
  assert.equal(await summary.getByRole('row').filter({hasText:unlicensedLabel}).locator('td').last().innerText(),'1');
  assert.equal(await summary.getByRole('row').filter({hasText:profile.lang==='en'?'Other unresolved exceptions':'其他待处理异常'}).locator('td').last().innerText(),'3');
  const unlicensedRow=section.getByRole('row').filter({hasText:'12345678'});
  assert.match(await unlicensedRow.locator('td').nth(2).innerText(),profile.lang==='en'?/not licensed/:/机构未授权/);
  assert.doesNotMatch(await unlicensedRow.locator('td').nth(2).innerText(),/failed|失败|待后续补全/);
  const original=unlicensedRow.getByText(profile.lang==='en'?'Original retrieval attempt':'原始获取记录',{exact:true});
  await original.click();assert.match(await unlicensedRow.innerText(),/failed/);assert.match(await unlicensedRow.innerText(),/pdf_not_entitled/);
  const refreshRow=section.getByRole('row').filter({hasText:'12345680'});
  assert.match(await refreshRow.locator('td').nth(2).innerText(),profile.lang==='en'?/Existing PDF available/:/已有 PDF/);
  const pendingHeading=section.getByRole('heading',{name:profile.lang==='en'?'PDF follow-up list':'PDF 后续补全清单'});
  await pendingHeading.waitFor();const pending=pendingHeading.locator('xpath=following-sibling::table[1]');
  assert.equal(await pending.getByRole('row').filter({hasText:'12345678'}).count(),0);
  assert.equal(await pending.getByRole('row').filter({hasText:'12345679'}).count(),1);
  const waiting=pending.getByRole('row').filter({hasText:'12345679'});assert.match(await waiting.innerText(),/1\/3/);assert.match(await waiting.innerText(),profile.lang==='en'?/Next retry:/:/下次重试/);
  const exhausted=pending.getByRole('row').filter({hasText:'12345681'});assert.match(await exhausted.innerText(),/3\/3/);assert.match(await exhausted.innerText(),profile.lang==='en'?/Retry limit reached/:/次数耗尽/);
  const manual=pending.getByRole('row').filter({hasText:'12345682'});assert.match(await manual.innerText(),profile.lang==='en'?/Manual handling required/:/待人工处理/);
  assert.deepEqual(mutations,[]);assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
  if(process.env.CIRDC_BROWSER_OUTPUT){await fs.mkdir(process.env.CIRDC_BROWSER_OUTPUT,{recursive:true});await pending.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,profile.name+'-retry.png')});await section.locator('.resource-node-diagnostics').evaluate(el=>{el.scrollTop=0});await section.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,profile.name+'.png')});}
  reports.push({...profile,unavailable:1,unresolved:3,pending:3,rawHistoryPreserved:true,existingPdfRefreshPreserved:true,mutations:0,sourceRequests:0});
  await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'result.json'),JSON.stringify(reports,null,2)+'\n');
 console.log(JSON.stringify(reports));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
