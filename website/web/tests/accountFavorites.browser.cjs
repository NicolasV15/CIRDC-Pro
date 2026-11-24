/* Register → sign in → save favorites → select → download ZIP → settings → sign out, against the offline demo
 * (`sh tools/web demo`). Accounts are the demo's isolated store; PDFs are labelled test material except the
 * packaged real 2611.14519v1 file. Set CIRDC_DEMO_ORIGIN, PLAYWRIGHT_MODULE and optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE. One account is registered per run; registration allows five per address and hour,
 * so start the demo with a fresh `--state` folder when rerunning often. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path'),zlib=require('node:zlib');
const origin=process.env.CIRDC_DEMO_ORIGIN;
function entries(zip){ // Minimal reader for the stored (uncompressed) ZIP the server writes.
 const files={};let at=zip.lastIndexOf(Buffer.from([0x50,0x4b,0x05,0x06]));const count=zip.readUInt16LE(at+10);let pos=zip.readUInt32LE(at+16);
 for(let i=0;i<count;i++){const method=zip.readUInt16LE(pos+10),size=zip.readUInt32LE(pos+20),nameLength=zip.readUInt16LE(pos+28),extra=zip.readUInt16LE(pos+30),comment=zip.readUInt16LE(pos+32),local=zip.readUInt32LE(pos+42),name=zip.subarray(pos+46,pos+46+nameLength).toString();
  const start=local+30+zip.readUInt16LE(local+26)+zip.readUInt16LE(local+28),data=zip.subarray(start,start+size);files[name]=method===0?data:zlib.inflateRawSync(data);pos+=46+nameLength+extra+comment;}
 return files;
}
(async()=>{
 if(!origin)throw Error('Set CIRDC_DEMO_ORIGIN to the standalone demo URL');
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});
 const name='flow-'+crypto.randomBytes(3).toString('hex'),password='flow-password-'+crypto.randomBytes(4).toString('hex'),reports=[];
 const sources=[];
 try{for(const [index,width] of [1440,390,320].entries()){
  const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
  await context.addInitScript(()=>{if(!localStorage.getItem('cirdc.ui.language'))localStorage.setItem('cirdc.ui.language','zh');});
  const page=await context.newPage(),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  context.on('request',r=>{if(r.method()!=='GET'&&r.method()!=='HEAD')writes.push(r.method()+' '+new URL(r.url()).pathname);});
  // Anonymous browsing sets no cookie; saving a paper leads to sign-in and back.
  await page.goto(origin+'/?sources=arxiv');await page.locator('.paper-row').first().waitFor();
  assert.deepEqual(await context.cookies(),[]);
  await page.locator('.paper-row').first().locator('.favorite-trigger').click();
  await page.waitForURL(u=>new URL(u).pathname==='/login');
  assert.equal(new URLSearchParams(new URL(page.url()).searchParams.get('next').split('?')[1]).get('sources'),'arxiv');
  if(index===0){
   await page.getByRole('link',{name:'注册'}).click();await page.waitForURL(u=>new URL(u).pathname==='/register');
   await page.getByLabel('用户名',{exact:true}).fill(name);
   await page.getByLabel('密码 · 至少 8 个字符',{exact:true}).fill(password);await page.getByLabel('再次输入密码',{exact:true}).fill(password);
   const registered=page.waitForResponse(r=>r.url().endsWith('/api/auth/register'));
   await page.getByRole('button',{name:'创建并登录'}).click();
   assert.notEqual((await registered).status(),429,'registration limit reached: restart the demo with a fresh --state folder');
  }else{
   await page.getByLabel('用户名',{exact:true}).fill(name);await page.getByLabel('密码',{exact:true}).fill(password);
   await page.getByRole('button',{name:'登录',exact:true}).click();
  }
  await page.waitForURL(u=>new URL(u).pathname==='/'&&new URL(u).searchParams.get('sources')==='arxiv');
  await page.locator('.header-menu-trigger').waitFor();
  // From the second browser on, the account's saved theme and language are restored at sign-in.
  const L=index===0?{all:'全部',checked:'已勾选 {n}',download:'下载 PDF',dialog:'下载收藏的 PDF',prepare:'准备 ZIP',zip:'下载 ZIP',packed:'已打包 {n} 个 PDF',skipped:'未包含 {n} 篇',done:'关闭'}
   :{all:'All',checked:'{n} checked',download:'Download PDFs',dialog:'Download favorite PDFs',prepare:'Prepare ZIP',zip:'Download ZIP',packed:'{n} PDFs packaged',skipped:'{n} not included',done:'Close'};
  const fill=(text,n)=>text.replace('{n}',String(n));
  if(index>0){await page.waitForFunction(()=>document.documentElement.dataset.theme==='midnight'&&document.documentElement.lang==='en');}
  if(index===0){
   // Save from lists (newest arXiv version pinned), the detail page (selected version) and IEEE.
   const first=page.locator('.paper-row').first();await first.locator('.favorite-trigger').click();
   await first.locator('.favorite-trigger.is-saved').waitFor();
   await page.goto(origin+'/arxiv/papers/1?source=arxiv&v=1');await page.locator('.detail-favorite-trigger').click();
   await page.locator('.detail-favorite-trigger.is-saved').waitFor();
   await page.locator('.arxiv-version-switch button').filter({hasText:'v2'}).click();
   assert.equal(await page.locator('.detail-favorite-trigger.is-saved').count(),0);
   await page.locator('.detail-favorite-trigger').click();await page.locator('.detail-favorite-trigger.is-saved').waitFor();
   // The list saved 3300802 at its newest version; its detail page shows that version as saved.
   await page.goto(origin+'/arxiv/papers/3300802?source=arxiv&v=1');await page.locator('.detail-favorite-trigger.is-saved').waitFor();
   await page.goto(origin+'/arxiv/papers/3112709?source=arxiv&v=2');await page.locator('.detail-favorite-trigger').click();await page.locator('.detail-favorite-trigger.is-saved').waitFor();
   await page.goto(origin+'/?sources=ieee');await page.locator('.paper-row').first().waitFor();
   for(const row of await page.locator('.paper-row').all()){await row.locator('.favorite-trigger').click();await row.locator('.favorite-trigger.is-saved').waitFor();}
  }
  // Favorites: counts, filter clears selection, select all, ZIP with exact real bytes and labelled test material.
  await page.goto(origin+'/favorites');await page.locator('.favorite-row').first().waitFor();
  assert.match(await page.locator('.favorite-filters').innerText(),new RegExp(L.all+'\\s*7[\\s\\S]*IEEE\\s*3[\\s\\S]*arXiv\\s*4'));
  await page.locator('.select-loaded input').check();
  assert.ok((await page.locator('.paper-selection-count').innerText()).includes(fill(L.checked,7)));
  await page.locator('.favorite-filters button').filter({hasText:'arXiv'}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.favorite-row').length===4);
  assert.ok((await page.locator('.paper-selection-count').innerText()).includes(fill(L.checked,0)));
  assert.equal(new URL(page.url()).searchParams.get('source'),'arxiv');
  await page.locator('.favorite-filters button').filter({hasText:L.all}).click();await page.waitForFunction(()=>document.querySelectorAll('.favorite-row').length===7);
  await page.locator('.select-loaded input').check();
  await page.getByRole('button',{name:L.download}).click();
  const dialog=page.getByRole('dialog',{name:L.dialog});await dialog.getByRole('button',{name:L.prepare}).click();
  await dialog.getByRole('link',{name:L.zip}).waitFor();
  assert.ok((await dialog.innerText()).includes(fill(L.packed,6)));
  assert.ok((await dialog.innerText()).includes(fill(L.skipped,1)));
  const href=await dialog.getByRole('link',{name:L.zip}).getAttribute('href');
  const pending=page.waitForEvent('download');await dialog.getByRole('link',{name:L.zip}).click();const file=await (await pending).path();
  const files=entries(await fs.readFile(file)),real=await fs.readFile(path.resolve(__dirname,'../../demo/arxiv/files/2611.14519v1-paper.pdf'));
  const sha=buffer=>crypto.createHash('sha256').update(buffer).digest('hex');
  assert.equal(Object.keys(files).length,6);
  assert.ok(Object.values(files).some(value=>sha(value)===sha(real)),'real PDF bytes unchanged');
  assert.equal(Object.values(files).filter(value=>value.includes('TEST MATERIAL - not the paper')).length,5);
  await dialog.locator('.favorite-archive-result .actions').getByRole('button',{name:L.done,exact:true}).click();
  if(index===2){
   // Batch removal asks for confirmation and removes only the selected source's favorites.
   await page.locator('.favorite-filters button').filter({hasText:'IEEE'}).click();await page.waitForFunction(()=>document.querySelectorAll('.favorite-row').length===3);
   await page.locator('.select-loaded input').check();
   await page.locator('.paper-selection-actions button').first().click();
   await page.locator('.paper-selection-actions button.danger').click();
   await page.locator('.favorite-notice').waitFor();
   await page.locator('.favorite-filters button').filter({hasText:L.all}).click();
   await page.waitForFunction(()=>document.querySelectorAll('.favorite-row').length===4);
   assert.match(await page.locator('.favorite-filters').innerText(),/IEEE\s*0[\s\S]*arXiv\s*4/);
  }
  // Settings sync: the first browser saves, later browsers restore; sign-out restores the anonymous choice.
  await page.goto(origin+'/account');await page.locator('.account-page').waitFor();
  if(index===0){
   await page.locator('[data-theme-choice="midnight"]').first().click();
   await page.waitForFunction(()=>document.documentElement.dataset.theme==='midnight');
   await page.getByRole('group',{name:'界面语言'}).last().getByRole('button',{name:'English'}).click();
   await page.waitForTimeout(400);
  }
  await page.reload();await page.locator('.account-page').waitFor();await page.waitForFunction(()=>document.documentElement.dataset.theme==='midnight');
  assert.equal(await page.evaluate(()=>document.documentElement.lang),'en');
  assert.equal(await page.evaluate(()=>localStorage.getItem('cirdc.ui.theme.v1')),null);
  await page.getByRole('button',{name:'Sign out'}).click();await page.waitForURL(u=>new URL(u).pathname==='/');
  await page.waitForFunction(()=>document.documentElement.dataset.theme!=='midnight');
  assert.equal(await page.evaluate(()=>document.documentElement.lang),'zh-CN');
  // A signed-out browser cannot fetch the archive.
  assert.equal((await page.request.get(origin+href)).status(),401);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.ok(writes.every(w=>/\/api\/(auth|me)\//.test(w)),'only account writes: '+writes.join(', '));
  assert.deepEqual(errors,[]);
  sources.push(...writes);reports.push({width,registered:index===0,favorites:7,zip:6,skipped:1,settingsSynced:true,writes:writes.length});
  await context.close();
 }console.log(JSON.stringify(reports));}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
