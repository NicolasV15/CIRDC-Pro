const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});
 try{
  const origin=process.env.CIRDC_LINKED_ORIGIN,context=await browser.newContext({viewport:{width:390,height:950}}),page=await context.newPage(),posts=[],receipts=[],errors=[];let readSincePost=false,unreadSubmissions=0;
  await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{const p=new URL(r.url()).pathname;if(r.method()==='GET'&&p==='/api/content/100')readSincePost=true;if(r.method()==='POST'&&p.endsWith('/ensure')){if(!readSincePost)unreadSubmissions++;readSincePost=false;posts.push(r.postDataJSON());}if(p.includes('/api/agent/v1/requests/'))receipts.push(p);});
  await context.route('**/*',route=>{const p=new URL(route.request().url()).pathname;if(p.endsWith('/metadata/status')||/\/(references|citations|patent-citations)$/.test(p))return route.fulfill({json:{state:'disabled',items:[],counts:{},total:0}});return route.continue();});
  await page.goto(origin+'/papers/100');
  await page.getByText('请求超时，正在确认状态…',{exact:false}).waitFor();
  try{await page.waitForFunction(()=>document.querySelector('.document-reader .badge')?.textContent==='任务已排队');}catch(error){console.error(await page.locator('body').innerText(),posts,receipts,errors);throw error;}
  assert(posts.length>=1);assert.equal(unreadSubmissions,0,'Every recovery ensure must follow a read');assert(posts.every(p=>p.retry===false));
  await page.evaluate(()=>fetch('/fixture/wait'));
  await page.waitForFunction(()=>document.querySelector('.document-reader .badge')?.textContent==='等待自动重试');
  await page.getByText('后台下次获取重试：',{exact:false}).waitFor();
  assert(receipts.length>0,'Late committed receipt must be reattached and polled');
  assert.equal((await page.locator('body').innerText()).includes('繁忙'),false);
  const before=posts.length;await page.evaluate(()=>fetch('/fixture/stop'));
  await page.waitForFunction(()=>document.querySelector('.document-reader .badge')?.textContent==='自动重试次数已用尽，请联系管理员');
  const stopped=receipts.length;await page.waitForTimeout(250);assert.equal(receipts.length,stopped);assert.equal(posts.length,before);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({realHttp:true,unknownAcceptance:true,receiptQueries:receipts.length,submissions:posts.length,fetches:1,terminalPollingStopped:true}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
