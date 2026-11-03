/* Agent prompts only: opening and copying this page must not install, deploy or acquire anything. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://agent-fixture.test';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff'};
async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const width of [1440,390,320]){
  const context=await browser.newContext({viewport:{width,height:950}}),requests=[],errors=[];
  await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  await context.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());requests.push({method:req.method(),path:u.pathname});
   assert.equal(req.method(),'GET');assert.equal(u.origin,origin);
   if(u.pathname==='/developers/ai')return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'index.html'))});
   if(u.pathname.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(u.pathname)]||'application/octet-stream',body:await fs.readFile(root+u.pathname)});
   throw Error('Prompt page made an unexpected request '+u.pathname);
  });
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin+'/developers/ai',{waitUntil:'networkidle'});
  await page.getByRole('heading',{name:'AI 接入',exact:true}).waitFor();
  assert.equal(await page.locator('main textarea').count(),2);
  assert.equal(await page.locator('main button').count(),2);
  assert.equal(await page.locator('main input').count(),0);
  assert.equal(await page.locator('main a').count(),1); // Only the common return-to-search link.
  const online=page.getByRole('textbox',{name:'在线安装 prompt',exact:true});
  const remoteText=await online.inputValue();
  assert(remoteText.includes('--base-url '+origin));
  assert(remoteText.includes(origin+'/api/agent/v1/skills/cirdc-research/scripts/install_skill.py'));
  const onlineRegion=page.getByRole('region',{name:'连接当前站点',exact:true});
  await onlineRegion.getByRole('button').click();
  await onlineRegion.getByText('已选中文本，请手动复制。',{exact:true}).waitFor();
  assert.equal(await online.evaluate(el=>el.selectionEnd-el.selectionStart),remoteText.length);
  const localRegion=page.getByRole('region',{name:'部署到自己的机器',exact:true}),localButton=localRegion.getByRole('button');
  assert(await localButton.isEnabled());
  const local=page.getByRole('textbox',{name:'本地部署 prompt',exact:true});
  const localText=await local.inputValue();
  assert(localText.includes('当前对话的工作目录')&&localText.includes('pwd'));
  assert(!localText.includes(origin));
  assert(!localText.includes('【请填写'));
  await localButton.click();
  await localRegion.getByText('已选中文本，请手动复制。',{exact:true}).waitFor();
  assert.equal(await local.evaluate(el=>el.selectionEnd-el.selectionStart),localText.length);
  await page.locator('main textarea').evaluateAll(fields=>fields.forEach(field=>{field.blur();field.scrollTop=0;}));
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Chinese overflow at '+width);
  if(process.env.CIRDC_BROWSER_OUTPUT)await page.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,'agent-prompts-'+width+'.png'),fullPage:true});
  await page.getByRole('button',{name:'English',exact:true}).click();
  await page.getByRole('heading',{name:'AI access',exact:true}).waitFor();
  const englishRemote=page.getByRole('textbox',{name:'Online install prompt',exact:true});
  assert.notEqual(await englishRemote.inputValue(),remoteText);
  assert((await page.getByRole('textbox',{name:'Local deployment prompt',exact:true}).inputValue()).includes("conversation's current working directory"));
  assert.equal(await page.locator('main input').count(),0);
  await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.agentCopiedPrompt=text;}}}));
  await page.getByRole('region',{name:'Connect to this site',exact:true}).getByRole('button').click();
  await page.getByRole('region',{name:'Connect to this site',exact:true}).getByText('Copied',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>window.agentCopiedPrompt),await englishRemote.inputValue());
  assert(await page.getByRole('region',{name:'Deploy on your machine',exact:true}).getByRole('button').isEnabled());
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'English overflow at '+width);
  assert.equal(requests.filter(r=>r.path.startsWith('/api/')).length,0);
  assert.deepEqual(errors,[]);
  reports.push({width,prompts:2,bilingual:true,copyFallback:true,clipboard:true,conversationDirectory:true,remoteSiteNotInherited:true,apiRequests:0});await context.close();
 }}finally{await browser.close();}
 console.log(JSON.stringify(reports,null,2));
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'agent-prompts-browser.json'),JSON.stringify(reports,null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
