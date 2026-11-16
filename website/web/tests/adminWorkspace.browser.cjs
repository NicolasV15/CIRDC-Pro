/* Administrator workspace over the demo's isolated test adapter (`sh tools/web demo --admin-port PORT`).
 * Every original operation stays reachable; job actions ask for confirmation and reach only the adapter.
 * Set CIRDC_DEMO_ADMIN_ORIGIN (use localhost), CIRDC_DEMO_ADMIN_CREDENTIALS (the printed credentials file),
 * PLAYWRIGHT_MODULE and optionally PLAYWRIGHT_CHROMIUM_EXECUTABLE. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const origin=process.env.CIRDC_DEMO_ADMIN_ORIGIN,credentials=process.env.CIRDC_DEMO_ADMIN_CREDENTIALS;
(async()=>{
 if(!origin||!credentials)throw Error('Set CIRDC_DEMO_ADMIN_ORIGIN and CIRDC_DEMO_ADMIN_CREDENTIALS');
 const password=fs.readFileSync(credentials,'utf8').split('password: ')[1].trim();
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const [language,width] of [['zh',1440],['en',390],['zh',320]]){
  const context=await browser.newContext({viewport:{width,height:900}});await context.addInitScript(lang=>localStorage.setItem('cirdc.ui.language',lang),language);
  const page=await context.newPage(),errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
  context.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
  const zh=language==='zh',L=(a,b)=>zh?a:b;
  await page.goto(origin+'/admin/');
  await page.getByLabel(L('用户名','Username'),{exact:true}).fill('demo-admin');await page.getByLabel(L('密码','Password'),{exact:true}).fill(password);
  await page.getByRole('button',{name:L('登录','Sign in'),exact:true}).click();
  await page.locator('.admin-summaries').waitFor();
  assert.equal(await page.locator('.admin-summary').count(),5);
  // Section navigation is in the address, so back/forward work.
  const nav=page.getByRole('navigation',{name:L('工作台分区','Workspace sections')});
  await nav.locator('a[href="#jobs"]').click();await page.locator('.job-detail').waitFor();
  await nav.locator('a[href="#audit"]').click();await page.waitForFunction(()=>location.hash==='#audit');
  await page.goBack();await page.locator('.job-detail').waitFor();
  // A failed job lists its failed and restricted records; resuming asks first and reaches only the adapter.
  await page.locator('.job-option').nth(1).click();await page.locator('.job-detail table').waitFor();
  assert.match(await page.locator('.job-detail table').innerText(),/demo-task-41[\s\S]*demo-task-57/);
  const before=writes.length;
  await page.getByRole('button',{name:L('恢复待办任务','Resume pending tasks')}).click();
  assert.equal(writes.length,before,'no request before confirmation');
  await page.getByRole('button',{name:L('确认恢复待办任务','Confirm resuming pending tasks')}).click();
  await page.locator('.notice').waitFor();
  await page.getByRole('button',{name:L('预览更新范围','Preview update scope')}).click();await page.locator('.preview').waitFor();
  await page.getByRole('button',{name:L('按此范围启动后台作业','Start background job for this scope')}).click();
  await page.getByRole('button',{name:L('取消','Cancel'),exact:true}).click();
  assert.equal(writes.filter(w=>w.endsWith('/update')).length,0,'cancelled start sends nothing');
  // Preflight and resources remain reachable.
  await nav.locator('a[href="#index"]').click();await page.getByRole('button',{name:L('执行预检','Run diagnostics')}).click();await page.locator('pre').first().waitFor();
  await nav.locator('a[href="#resources"]').click();await page.locator('.maintenance-status').waitFor();await page.locator('.resource-settings').waitFor();
  // Accounts: create a reader, disable with confirmation, enable again; the audit lists the changes.
  await nav.locator('a[href="#accounts"]').click();await page.locator('.admin-column table').waitFor();
  const reader='admin-made-'+crypto.randomBytes(2).toString('hex');
  await page.locator('.admin-aside input').first().fill(reader);await page.locator('.admin-aside input[type=password]').fill('admin-made-pass-1');
  await page.getByRole('button',{name:L('新增读者','Add reader')}).click();await page.locator('.notice').waitFor();
  await page.getByRole('searchbox',{name:L('按用户名筛选账户','Filter accounts by username')}).fill(reader);
  const row=page.locator('.admin-column tbody tr');await page.waitForFunction(()=>document.querySelectorAll('.admin-column tbody tr').length===1);
  assert.match(await row.innerText(),new RegExp(L('管理员开通','Created by administrator')));
  await row.getByRole('button',{name:L('禁用','Disable'),exact:true}).click();
  await row.getByRole('button',{name:L('确认禁用','Confirm disabling')}).click();
  await row.getByRole('button',{name:L('启用','Enable'),exact:true}).waitFor();
  await row.getByRole('button',{name:L('启用','Enable'),exact:true}).click();
  await row.getByRole('button',{name:L('禁用','Disable'),exact:true}).waitFor();
  await page.getByRole('searchbox',{name:L('按用户名筛选账户','Filter accounts by username')}).fill('demo-admin');
  assert.equal(await page.locator('.admin-column tbody tr button').count(),1,'own account cannot be disabled here');
  await nav.locator('a[href="#audit"]').click();await page.locator('table').waitFor();
  assert.match(await page.locator('table').innerText(),new RegExp(reader));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.ok(writes.every(w=>/^\/api\/(auth|admin)\//.test(w)));assert.deepEqual(errors,[]);
  reports.push({language,width,sections:6,confirmations:true,accountActions:true,writes:writes.length});
  await context.close();
 }console.log(JSON.stringify(reports));}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
