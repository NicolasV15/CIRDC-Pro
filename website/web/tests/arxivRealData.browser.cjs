/* Review of the arXiv pages against the offline real-data demo (`sh tools/web demo`); no mocked API responses.
 * Set CIRDC_DEMO_ORIGIN, PLAYWRIGHT_MODULE and optionally PLAYWRIGHT_CHROMIUM_EXECUTABLE. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const origin=process.env.CIRDC_DEMO_ORIGIN;if(!origin)throw Error('Set CIRDC_DEMO_ORIGIN to the standalone demo URL');
 assert.equal((await fetch(origin+'/api/demo').then(r=>r.json())).offline,true);
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const [language,width] of [['zh',1440],['en',390],['zh',320]]){
  const context=await browser.newContext({viewport:{width,height:900}});
  await context.addInitScript(lang=>localStorage.setItem('cirdc.ui.language',lang),language);
  const writes=[],errors=[];
  context.on('request',request=>{if(request.method()!=='GET')writes.push(request.method()+' '+request.url());});
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  const zh=language==='zh',noOverflow=async()=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  // Result rows show TeX-encoded author names as letters (9 of the 43 real records use TeX accents).
  await page.goto(origin+'/?source=arxiv&limit=100');await page.locator('.paper-row').nth(42).waitFor();
  const authors=await page.locator('.paper-row .authors').allTextContents();
  assert.equal(authors.length,43);assert.ok(authors.every(text=>!/\\['"`^~=.vc]/.test(text)),'raw TeX accent in a result row');
  assert.ok(authors.some(text=>text.includes('C. Balázs'))&&authors.some(text=>text.includes('Mercangöz')));
  assert.ok((await page.locator('.paper-row .paper-title').allTextContents()).some(text=>text.includes('moiré rhombohedral')));
  await noOverflow();
  // Titles and abstracts display letters while the copy source keeps the original metadata bytes.
  await page.goto(origin+'/arxiv/papers/3300028?source=arxiv');await page.locator('.detail-header h1').waitFor();
  assert.match(await page.locator('.detail-header h1').innerText(),/moiré rhombohedral graphene/);
  assert.equal(await page.locator('.detail-header h1 .scientific-title').getAttribute('data-copy-source-html'),"Evidence of anomalous Hall crystals in moir\\'e rhombohedral graphene");
  assert.match(await page.locator('#arxiv-abstract').innerText(),/moiré lattice/);
  // Author links search the authors field and find the paper even when its index entry is TeX-encoded.
  await page.goto(origin+'/arxiv/papers/1?source=arxiv');await page.locator('.arxiv-author-link').first().waitFor();
  assert.equal(await page.locator('.arxiv-author-link').first().innerText(),'C. Balázs');
  const sidebar=page.locator('.bibliographic');
  assert.match(await sidebar.innerText(),zh?/提交者\s*Pavel Nadolsky/:/Submitter\s*Pavel Nadolsky/);
  assert.match(await sidebar.innerText(),/ANL-HEP-PR-07-12/);
  assert.equal(await sidebar.locator('a[href="https://doi.org/10.1103/PhysRevD.76.013009"]').count(),1);
  await page.locator('.arxiv-author-link').first().click();
  await page.waitForURL(url=>new URL(url).searchParams.get('field')==='authors');
  await page.locator('.paper-row').first().waitFor();
  assert.deepEqual(await page.locator('.paper-row .paper-number').allTextContents(),['0704.0001']);
  // Web addresses in comments are links.
  await page.goto(origin+'/arxiv/papers/3300797?source=arxiv');await sidebar.waitFor();
  assert.equal(await sidebar.locator('a[href="https://codiscovery.ai/contrastive-discovery/"]').count(),1);
  // Files not bundled in the demo are labelled as such; there is nothing to request.
  await page.goto(origin+'/arxiv/papers/3300802?source=arxiv&v=1');await page.locator('.document-progress').waitFor();
  const items=page.locator('.arxiv-resource-list li');
  assert.deepEqual(await items.evaluateAll(list=>list.map(li=>li.dataset.state)),['ready','not_packaged','not_packaged','ready']);
  assert.match(await items.nth(1).innerText(),zh?/未打包/:/Not packaged/);
  assert.equal(await page.locator('.arxiv-resource-actions button').count(),0);
  assert.match(await page.locator('.arxiv-resource-download').getAttribute('href'),/\/versions\/1\/files\/html$/);
  assert.match(await page.locator('.document-progress').innerText(),/arXiv HTML/);
  await noOverflow();
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);
  reports.push({language,width,rows:43,accentsDecoded:true,authorSearch:true,notPackaged:true,writes:writes.length});
  await context.close();
 }console.log(JSON.stringify(reports));}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
