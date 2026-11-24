// Run against the standalone demo only; no mocked API responses.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
(async()=>{
 const origin=process.env.CIRDC_DEMO_ORIGIN;if(!origin)throw Error('Set CIRDC_DEMO_ORIGIN to the standalone demo URL');
 const about=await fetch(origin+'/api/demo').then(r=>r.json());assert.equal(about.offline,true);
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});
 try{for(const width of [1440,390,320]){
  const context=await browser.newContext({viewport:{width,height:1000},acceptDownloads:true});
  await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  const page=await context.newPage(),errors=[],writes=[],external=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.url());});
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==new URL(origin).origin){external.push(route.request().url());return route.abort();}return route.continue();});
  await page.goto(origin+'/?sources=arxiv');await page.locator('.paper-row').nth(24).waitFor();
  await page.getByRole('button',{name:'加载更多论文',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===43);
  // The first row (2611.14519v1) now carries a packaged PDF; the no-PDF dialog is checked on the second row.
  await page.locator('.paper-row input[type=checkbox]').nth(1).check();
  await page.getByRole('button',{name:'批量引用',exact:true}).click();await page.getByRole('textbox',{name:'引用文本',exact:true}).waitFor();
  assert.ok((await page.getByRole('textbox',{name:'引用文本',exact:true}).inputValue()).includes('arxiv.org/abs/'));
  await page.getByRole('button',{name:'关闭引用格式',exact:true}).click();
  await page.getByRole('button',{name:'批量下载 PDF',exact:true}).click();await page.locator('.download-preview-list li[data-status=not_available]').waitFor();
  await page.getByRole('button',{name:'关闭下载设置',exact:true}).click();
  await page.goto(origin+'/arxiv/papers/1?source=arxiv&v=2');await page.locator('.arxiv-version-switch').waitFor();
  await page.locator('.arxiv-version-switch button').first().click();await page.waitForURL(/v=1/);await page.goBack();await page.waitForURL(/v=2/);
  const sample=about.reading;await page.goto(origin+'/arxiv/papers/'+sample.paper_id+'?source=arxiv&v=1');
  await page.locator('.document-body section').first().waitFor();assert.ok((await page.locator('.document-body').innerText()).length>10000);
  assert.ok(await page.locator('.document-body .katex').count()>0);
  const download=page.waitForEvent('download');await page.getByRole('link',{name:'下载HTML 原件',exact:true}).click();
  const file=await download,bytes=await fs.readFile(await file.path());
  const manifest=JSON.parse(await fs.readFile(path.resolve(__dirname,'../../demo/arxiv/manifest.json'),'utf8'));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),manifest.files.find(f=>f.attachment).sha256);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'real body overflows at '+width);
  if(process.env.CIRDC_BROWSER_OUTPUT){await fs.mkdir(process.env.CIRDC_BROWSER_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,'arxiv-demo-'+width+'.png')});}
  await page.goto(origin+'/?sources=ieee');await page.locator('.paper-row').nth(2).waitFor();assert.equal(await page.locator('.paper-row').count(),3);
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.deepEqual(external,[]);
  console.log(JSON.stringify({width,realArxiv:43,realIEEE:3,pagination:true,citation:true,versionHistory:true,realBody:true,htmlHash:true,acquisitions:0,missingImages:4}));
  await context.close();
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
