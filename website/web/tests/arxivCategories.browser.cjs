/* arXiv category browsing: quick subject classes, archive filters and row category tags. Fixtures only. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://arxiv-categories.test';
const types={'.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
const rows=[['2401.00001',['eess.SP','cs.AR']],['2401.00002',['cs.AI']],['2401.00003',['eess.SY']],['2401.00004',['math-ph']]].map(([arxiv_id,categories],i)=>({paper_id:i+1,arxiv_id,title:'Paper '+(i+1),authors_raw:'A. Author',abstract:'Abstract.',categories,year:2024,submitted_at:i===3?null:'2024-01-01T20:00:00+00:00'}));
const matches=(row,category)=>!category||category.split(',').some(code=>row.categories.some(c=>c.toLowerCase()===code.toLowerCase()||c.toLowerCase().startsWith(code.toLowerCase()+'.')));
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const width of [1440,390,320]){
  const context=await browser.newContext({viewport:{width,height:900}});await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  const requests=[],errors=[];let writes=0;
  await context.route('**/*',async route=>{const req=route.request(),u=new URL(req.url()),p=u.pathname;
   if(req.method()!=='GET'){writes++;return route.abort();}
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
   if(p==='/api/arxiv/overview')return route.fulfill({json:{indexed:4,year_range:{min:1991,max:2026}}});
   if(p==='/api/arxiv/papers'){const category=u.searchParams.get('category')||'';requests.push(category);const items=rows.filter(row=>matches(row,category));
    return route.fulfill({json:{items:u.searchParams.get('totals')==='only'?[]:items,total:u.searchParams.get('totals')==='defer'?null:items.length,next_cursor:null,query:{terms:'expand',groups:[]}}});}
   return route.fulfill({status:404,json:{error:'not_found'}});
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/?source=arxiv');await page.locator('.paper-row').nth(3).waitFor();
  assert.equal(await page.getByRole('button',{name:'最新投稿',exact:true}).getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('.paper-year').first().innerText(),'2024-01-02');
  assert.equal(await page.getByText('日期未提供',{exact:true}).count(),1);
  if(width<1024)await page.locator('.filter-disclosure > summary').click();
  const group=page.getByRole('group',{name:'电路相关分类'});
  assert.equal(await group.getByRole('button',{name:'eess 全部',exact:true}).count(),0);
  await group.getByRole('button',{name:'eess.SP',exact:true}).click();
  await group.getByRole('button',{name:'cs.AR',exact:true}).click();
  await group.getByRole('button',{name:'eess.SY',exact:true}).click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('category')==='cs.AR,eess.SP,eess.SY');
  await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===2);
  assert.equal(await group.locator('[aria-pressed=true]').count(),3);
  assert.equal(await page.locator('.active-filters .filter-chip').count(),3);
  await page.reload();await page.locator('.paper-row').nth(1).waitFor();
  if(width<1024)await page.locator('.filter-disclosure > summary').click();
  assert.equal(await group.locator('[aria-pressed=true]').count(),3);
  await page.getByRole('button',{name:'移除条件：eess.SP · Signal Processing',exact:true}).click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('category')==='cs.AR,eess.SY');
  assert.equal(await group.locator('[aria-pressed=true]').count(),2);
  const disclosure=page.locator('.arxiv-category-filter');
  await page.getByRole('button',{name:'电路相关分类介绍',exact:true}).click();
  const guide=page.getByRole('dialog',{name:'电路相关分类介绍'});await guide.waitFor();
  assert.equal(await guide.locator('.venue-guide-profile').count(),13);
  assert.ok((await guide.innerText()).includes('匹配其中任意一个'));
  assert.equal(await guide.locator('a[href^="https://arxiv.org/category_taxonomy#"]').count(),13);
  assert.ok(await guide.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
  if(process.env.CIRDC_BROWSER_OUTPUT){await fs.mkdir(process.env.CIRDC_BROWSER_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,'category-guide-'+width+'.png')});}
  await page.keyboard.press('Escape');await guide.waitFor({state:'detached'});
  assert.ok(await disclosure.evaluate(el=>el.open));
  assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('aria-controls')),'arxiv-category-guide-dialog');
  await page.getByRole('button',{name:'清除分类',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===4);
  // New AI shortcuts combine with existing circuit categories.
  await group.getByRole('button',{name:'cs.AI',exact:true}).click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('category')==='cs.AI');
  await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===1);
  await group.getByRole('button',{name:'eess.SP',exact:true}).click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('category')==='cs.AI,eess.SP');
  await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===2);
  assert.equal(await group.locator('[aria-pressed=true]').count(),2);
  for(const code of ['cs.LG','cs.NE','stat.ML','math.OC','cs.CE'])assert.equal(await group.getByRole('button',{name:code,exact:true}).count(),1);
  await page.getByRole('button',{name:'清除分类',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===4);
  // A row's category tag filters by that exact subject class and names it.
  const tag=page.locator('.paper-row').nth(1).locator('.arxiv-category-tag',{hasText:'cs.AI'});
  assert.equal(await tag.getAttribute('title'),'Artificial Intelligence');
  await tag.click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('category')==='cs.AI');
  await page.waitForFunction(()=>document.querySelectorAll('.paper-row').length===1);
  assert.match(await page.locator('.active-filters .filter-chip').innerText(),/cs\.AI · Artificial Intelligence/);
  assert.equal(await page.locator('.arxiv-category-tag.is-active').count(),1);
  // The free-text field still accepts any code and lists official names.
  assert.equal(await page.locator('#arxiv-categories option[value="eess.SP"]').getAttribute('label'),'Signal Processing');
  assert.equal(await page.locator('.paper-row .arxiv-category-tag',{hasText:'math-ph'}).count(),0);
  assert.equal(writes,0);assert.deepEqual(errors,[]);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.getByRole('button',{name:'English',exact:true}).click();
  await page.getByRole('button',{name:'Circuit-related category guide',exact:true}).click();
  await page.getByRole('dialog',{name:'Circuit-related category guide'}).waitFor();
  assert.ok((await page.getByRole('dialog').innerText()).includes('Reading tips'));
  await page.getByRole('button',{name:'Close category guide',exact:true}).click();
  reports.push({width,multiCategoryUnion:true,duplicateRows:false,restore:true,guideProfiles:13,bilingual:true,rowTagFilter:true,writes});await context.close();
 }console.log(JSON.stringify(reports));}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
