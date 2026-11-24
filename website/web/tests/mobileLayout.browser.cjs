/* Phone and desktop layout across the site, against the offline demo (`sh tools/web demo --admin-port PORT`).
 * Phones (390/320) keep a one-row header with the site tools in a menu, fold the search options behind a summary row,
 * and show no wrapped buttons, out-of-bounds controls or page overflow; 1440 keeps the desktop layout.
 * Set CIRDC_DEMO_ORIGIN, CIRDC_DEMO_ADMIN_ORIGIN (use localhost), CIRDC_DEMO_ADMIN_CREDENTIALS, PLAYWRIGHT_MODULE,
 * optionally PLAYWRIGHT_CHROMIUM_EXECUTABLE and CIRDC_SCREENSHOTS (a directory for page screenshots).
 * Registers one reader account; use a fresh demo state when the registration limit is reached. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const origin=process.env.CIRDC_DEMO_ORIGIN,adminOrigin=process.env.CIRDC_DEMO_ADMIN_ORIGIN,credentials=process.env.CIRDC_DEMO_ADMIN_CREDENTIALS,shots=process.env.CIRDC_SCREENSHOTS;
const profiles=[['zh',390],['en',390],['zh',320],['en',320],['zh',1440],['en',1440]];
/** Runs in the page: overflow, buttons whose own text breaks onto a second line, and controls outside the viewport. */
function layout(){
 const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden';};
 const clipped=e=>{for(let a=e.parentElement;a&&a!==document.body;a=a.parentElement){const o=getComputedStyle(a).overflowX;if(o!=='visible')return true;}return false;};
 const lines=node=>{const r=document.createRange();r.selectNodeContents(node);return new Set([...r.getClientRects()].filter(x=>x.width>1).map(x=>Math.round(x.top+x.height/2))).size;};
 const issues=[];
 for(const el of document.querySelectorAll('button,a.button,summary,label.select-loaded,.search-choice,.filter-chip,.menu-item,.header-register')){
  if(!visible(el)||el.closest('.document-body,details:not([open])>:not(summary),dialog:not([open])'))continue;
  const r=el.getBoundingClientRect(),name=(el.innerText||el.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ').slice(0,40);
  const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode()))if(node.textContent.trim()&&lines(node)>1){issues.push('wrapped: '+name);break;}
  if((r.right>innerWidth+1||r.left<-1)&&!clipped(el))issues.push('outside: '+name);
 }
 return {overflow:document.documentElement.scrollWidth-innerWidth,issues};
}
function header(){
 const inner=document.querySelector('.app-header-inner'),shown=e=>!!e&&e.getBoundingClientRect().width>0&&getComputedStyle(e).visibility!=='hidden';
 const controls=[...inner.querySelectorAll('a,button,.language-switch')].filter(e=>shown(e)&&!e.closest('.header-menu-panel,.header-more-panel.is-open,.language-switch>button'));
 const centers=controls.map(e=>{const r=e.getBoundingClientRect();return r.top+r.height/2;});
 return {height:inner.getBoundingClientRect().height,spread:Math.max(...centers)-Math.min(...centers),menu:shown(document.querySelector('.header-more-trigger')),
  inline:['.header-ai-trigger','.language-switch','.appearance-trigger'].filter(s=>document.querySelector(s)).map(s=>shown(document.querySelector(s))),overflow:document.documentElement.scrollWidth-innerWidth};
}
(async()=>{
 if(!origin||!adminOrigin||!credentials)throw Error('Set CIRDC_DEMO_ORIGIN, CIRDC_DEMO_ADMIN_ORIGIN and CIRDC_DEMO_ADMIN_CREDENTIALS');
 assert.equal((await fetch(origin+'/api/demo').then(r=>r.json())).offline,true);
 const password=fs.readFileSync(credentials,'utf8').split('password: ')[1].trim();
 if(shots)fs.mkdirSync(shots,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{
  // One reader with two favorites (one IEEE, one arXiv) for the personal pages.
  const setup=await browser.newContext();await setup.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  const sp=await setup.newPage(),reader='mobile-'+crypto.randomBytes(3).toString('hex');
  await sp.goto(origin+'/register');await sp.getByLabel('用户名',{exact:true}).fill(reader);
  const fields=sp.locator('input[type=password]');for(let i=0;i<await fields.count();i++)await fields.nth(i).fill('mobile-pass-123');
  await sp.getByRole('button',{name:'创建并登录'}).click();await sp.waitForURL(url=>!new URL(url).pathname.startsWith('/register'));
  for(const href of ['/','/?source=arxiv']){await sp.goto(origin+href);const star=sp.locator('.paper-row .favorite-trigger').first();await star.click();await sp.locator('.paper-row .favorite-trigger.is-saved').first().waitFor();}
  const signedIn=await setup.storageState();await setup.close();
  for(const [language,width] of profiles){
   const phone=width<=760,zh=language==='zh',L=(a,b)=>zh?a:b,report={language,width,pages:0};
   const open=async(state)=>{const context=await browser.newContext({viewport:{width,height:844},...(state?{storageState:state}:{})});await context.addInitScript(lang=>localStorage.setItem('cirdc.ui.language',lang),language);const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));return {context,page,errors};};
   const check=async(page,name)=>{const facts=await page.evaluate(layout);assert.ok(facts.overflow<=1,`${name} ${language}/${width}: page overflow ${facts.overflow}`);assert.deepEqual(facts.issues,[],`${name} ${language}/${width}`);report.pages++;if(shots)await page.screenshot({path:path.join(shots,`${name}-${language}-${width}.png`)});};
   const checkHeader=async(page,name)=>{const h=await page.evaluate(header);if(phone){assert.ok(h.height<=60,`${name}: header height ${h.height}`);assert.ok(h.spread<=2,`${name}: header controls on one row (${h.spread})`);assert.ok(h.menu);assert.ok(h.inline.every(shown=>!shown),`${name}: site tools fold into the menu`);}else{assert.ok(!h.menu);assert.ok(h.inline.every(Boolean));assert.ok(h.spread<=2);}assert.ok(h.overflow<=1);};
   // Anonymous reader: IEEE home.
   let {context,page,errors}=await open();
   await page.goto(origin+'/');await page.locator('.paper-row').first().waitFor();
   await checkHeader(page,'home');await check(page,'home');
   const trigger=page.locator('.header-more-trigger'),toggle=page.locator('.search-options-toggle'),options=page.locator('.search-options');
   if(phone){
    // Focus follows the visual order: brand, sources, sign-in, then the menu button.
    await page.locator('.brand').focus();const order=[];for(let i=0;i<4;i++){await page.keyboard.press('Tab');order.push(await page.evaluate(()=>document.activeElement.className||document.activeElement.textContent));}
    assert.deepEqual(order.slice(2),['button header-sign-in','header-more-trigger'],'header focus order');
    // Site tools fold into one menu that closes with Escape and returns focus.
    assert.equal(await trigger.getAttribute('aria-expanded'),'false');
    await trigger.click();assert.equal(await trigger.getAttribute('aria-expanded'),'true');
    const panel=page.locator('.header-more-panel');await panel.waitFor();
    const box=await panel.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1,'menu inside the viewport');
    for(const control of [page.locator('.header-more-panel .header-ai-trigger'),page.locator('.header-more-panel .language-switch'),page.locator('.header-more-panel .appearance-trigger'),page.locator('.header-more-panel .header-register')])assert.ok(await control.isVisible());
    assert.ok((await page.locator('.header-more-panel button,.header-more-panel a').evaluateAll(list=>list.map(e=>e.getBoundingClientRect().height))).every(h=>h>=40),'menu targets are touch sized');
    await check(page,'home-menu');
    await page.keyboard.press('Escape');assert.equal(await trigger.getAttribute('aria-expanded'),'false');assert.ok(await trigger.evaluate(e=>e===document.activeElement));
    // Choosing a language closes the menu.
    await trigger.click();await page.locator('.header-more-panel').getByRole('button',{name:zh?'English':'中文',exact:true}).click();
    await page.waitForFunction(lang=>document.documentElement.lang.startsWith(lang),zh?'en':'zh');assert.equal(await trigger.getAttribute('aria-expanded'),'false');
    await trigger.click();await page.locator('.header-more-panel').getByRole('button',{name:zh?'中文':'English',exact:true}).click();
    await page.waitForFunction(lang=>document.documentElement.lang.startsWith(lang),zh?'zh':'en');
    // The appearance dialog opens from the menu; Escape closes the dialog first, then the menu.
    await trigger.click();await page.locator('.header-more-panel .appearance-trigger').click();await page.locator('dialog.theme-dialog[open]').waitFor();
    await check(page,'appearance');await page.keyboard.press('Escape');await page.locator('dialog.theme-dialog').waitFor({state:'detached'});
    assert.equal(await trigger.getAttribute('aria-expanded'),'true');await page.keyboard.press('Escape');
    // AI access opens from the menu and returns focus to the menu button.
    await trigger.click();await page.locator('.header-more-panel .header-ai-trigger').click();await page.locator('#agent-access-dialog').waitFor();
    await check(page,'ai-access');await page.keyboard.press('Escape');await page.locator('#agent-access-dialog').waitFor({state:'detached'});
    assert.ok(await trigger.evaluate(e=>e===document.activeElement));
    // Search options sit behind one row that names the choices differing from the defaults.
    assert.ok(!await options.isVisible());assert.equal(await toggle.getAttribute('aria-expanded'),'false');
    assert.ok((await page.locator('.paper-row').first().boundingBox()).y<844,'first result on the first screen');
    await toggle.click();assert.ok(await options.isVisible());await check(page,'home-options');
    await options.getByRole('button',{name:L('标题','Title'),exact:true}).click();await page.locator('.paper-row').first().waitFor();
    if(await options.isVisible())await toggle.click();
    assert.match(await page.locator('.search-options-summary').innerText(),new RegExp(L('标题','Title')));
    await toggle.click();await options.getByRole('button',{name:L('全部','All'),exact:true}).click();await page.locator('.paper-row').first().waitFor();
    // The selection bar is one row until something is selected; then both actions share one row.
    const bar=page.locator('.paper-selection-toolbar');assert.ok((await bar.boundingBox()).height<=60);assert.ok(!await bar.locator('.paper-selection-actions').isVisible());
    await page.locator('.paper-row input[type=checkbox]').first().check();
    const actions=await bar.locator('.paper-selection-actions button').evaluateAll(list=>list.map(e=>Math.round(e.getBoundingClientRect().top)));
    assert.equal(new Set(actions).size,1,'selection actions share a row');
    assert.equal(await bar.getByRole('button',{name:L('批量下载 PDF','Download selected PDFs'),exact:true}).count(),1,'full action name kept');
    await check(page,'home-selected');
   }else{
    assert.ok(!await toggle.isVisible());assert.ok(await options.isVisible());
    await page.locator('.paper-row input[type=checkbox]').first().check();
   }
   // Citation dialog from a result row.
   await page.locator('.paper-row .citation-trigger').first().click();await page.locator('dialog.citation-dialog[open]').waitFor();
   await check(page,'citation');await page.keyboard.press('Escape');await page.locator('dialog.citation-dialog[open]').waitFor({state:'detached'});
   // Filters and the venue guide.
   const filters=page.locator('.filter-disclosure');if(!await filters.evaluate(e=>e.open))await filters.locator(':scope>summary').click();
   await page.locator('.venue-family-filter').waitFor();if(!await page.locator('.venue-family-filter').evaluate(e=>e.open))await page.locator('.venue-family-filter>summary').click();
   await check(page,'home-filters');
   await page.locator('.venue-family-filter .venue-guide-trigger').click();await page.locator('#venue-guide-dialog[open]').waitFor();await check(page,'venue-guide');await page.keyboard.press('Escape');
   // arXiv home with its category filter.
   await page.goto(origin+'/?source=arxiv');await page.locator('.paper-row').first().waitFor();await checkHeader(page,'arxiv');await check(page,'arxiv');
   if(phone){assert.ok(!await options.isVisible());assert.equal(await page.locator('.search-options-summary').count(),0,'newest first is the arXiv default');}
   const arxivFilters=page.locator('.filter-disclosure');if(!await arxivFilters.evaluate(e=>e.open))await arxivFilters.locator(':scope>summary').click();
   await check(page,'arxiv-filters');
   // Detail and reading pages.
   for(const [name,href,ready] of [['ieee-detail','/papers/11741266','.detail-record-actions'],['arxiv-detail','/arxiv/papers/3300802?source=arxiv&v=1','.document-body .katex'],['arxiv-reading','/arxiv/papers/9900001?source=arxiv&v=1','.document-body .katex']]){
    await page.goto(origin+href);await page.locator(ready).first().waitFor({timeout:20000});await checkHeader(page,name);await check(page,name);
    const buttons=await page.locator('.detail-record-actions>button,.detail-record-actions>.button,.detail-record-actions>*>button,.detail-record-actions>*>.button').evaluateAll(list=>list.map(e=>{const r=e.getBoundingClientRect();return {w:Math.round(r.width),top:Math.round(r.top)};}));
    if(phone){assert.equal(new Set(buttons.map(b=>b.w)).size,1,name+': record actions share one width');assert.equal((await page.locator('.reader-layout-controls>summary').textContent()).trim(),L('阅读布局','Reading layout'),'icon-only control keeps its name');}
    const toc=page.locator('.document-toc');if(await toc.count()&&!await toc.evaluate(e=>e.open)){await toc.locator(':scope>summary').click();await check(page,name+'-toc');await toc.locator(':scope>summary').click();}
   }
   // Sign-in and registration.
   for(const name of ['login','register']){await page.goto(origin+'/'+name);await page.locator('.auth-card').waitFor();await checkHeader(page,name);await check(page,name);}
   assert.deepEqual(errors,[]);await context.close();
   // Signed-in reader: favorites and account settings.
   ({context,page,errors}=await open(signedIn));
   await page.goto(origin+'/favorites');await page.locator('.favorite-row').first().waitFor();
   // Signed-in pages follow the account's synced language; switch it to this profile's language through the header.
   if(!await page.evaluate(lang=>document.documentElement.lang.startsWith(lang),language)){if(phone)await page.locator('.header-more-trigger').click();await page.locator('.app-header .language-switch').getByRole('button',{name:zh?'中文':'English',exact:true}).click();await page.waitForFunction(lang=>document.documentElement.lang.startsWith(lang),language);}
   await checkHeader(page,'favorites');await check(page,'favorites');
   await page.locator('.paper-selection-toolbar .select-loaded input').check();await check(page,'favorites-selected');
   await page.locator('.paper-selection-actions button').filter({hasText:L('下载 PDF','Download PDFs')}).click();await page.locator('dialog.favorite-archive-dialog[open]').waitFor();
   await check(page,'favorite-archive');await page.keyboard.press('Escape');
   await page.goto(origin+'/account');await page.locator('.account-sections').waitFor();await checkHeader(page,'account');await check(page,'account');
   if(phone){await page.locator('.header-menu-trigger').click();await page.locator('.header-menu-panel').waitFor();const box=await page.locator('.header-menu-panel').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1);await page.keyboard.press('Escape');}
   assert.deepEqual(errors,[]);await context.close();
   // Administrator workspace over the demo's isolated adapter.
   ({context,page,errors}=await open());
   await page.goto(adminOrigin+'/admin/');
   await page.getByLabel(L('用户名','Username'),{exact:true}).fill('demo-admin');await page.getByLabel(L('密码','Password'),{exact:true}).fill(password);
   await page.getByRole('button',{name:L('登录','Sign in'),exact:true}).click();await page.locator('.admin-summaries').waitFor();
   await checkHeader(page,'admin');
   for(const section of ['overview','jobs','index','resources','accounts','audit']){await page.locator(`.admin-nav a[href="#${section}"]`).click();await page.waitForFunction(s=>location.hash==='#'+s,section);await page.waitForTimeout(300);await check(page,'admin-'+section);}
   assert.deepEqual(errors,[]);await context.close();
   reports.push(report);
  }
  console.log(JSON.stringify(reports));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
