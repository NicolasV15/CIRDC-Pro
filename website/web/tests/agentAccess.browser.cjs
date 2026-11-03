/* Isolated fixtures only. The guide must never submit a resource request. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://agent-fixture.test';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff'};
async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const width of [1440,390,320]){
  const context=await browser.newContext({viewport:{width,height:950},acceptDownloads:true}),requests=[],errors=[];
  await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  await context.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());requests.push({method:req.method(),path:u.pathname});
   assert.equal(req.method(),'GET');assert.equal(u.origin,origin);
   if(u.pathname==='/developers/ai')return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'index.html'))});
   if(u.pathname.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(u.pathname)]||'application/octet-stream',body:await fs.readFile(root+u.pathname)});
   if(u.pathname==='/api/agent/v1/capabilities')return route.fulfill({json:{authentication:'none',resources:{content:{enabled:true},pdf:{enabled:false}}}});
   if(u.pathname==='/api/agent/v1/skills/cirdc-research/SKILL.md')return route.fulfill({contentType:'text/markdown',body:await fs.readFile(path.resolve(__dirname,'../../.agents/skills/cirdc-research/SKILL.md'))});
   throw Error('Unexpected guide request '+u.pathname);
  });
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin+'/developers/ai',{waitUntil:'networkidle'});
  await page.getByRole('heading',{name:'AI 接入',exact:true}).waitFor();
  assert.equal(await page.locator('.agent-capabilities').innerText(),'正文 · 可用\nPDF · 未配置');
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'horizontal overflow at '+width);
  assert.equal(await page.getByRole('textbox',{name:'从仓库源码安装',exact:true}).inputValue(),'sh tools/install-skill --agent all');
  const codex=await page.getByRole('textbox',{name:'安装到 Codex',exact:true}).inputValue();
  const claude=await page.getByRole('textbox',{name:'安装到 Claude Code',exact:true}).inputValue();
  assert(codex.includes("--base-url '"+origin+"' --agent codex"));
  assert(claude.includes('--agent claude-code'));
  assert.equal(await page.getByRole('link',{name:'软链接、源码安装与卸载说明'}).count(),1);
  const config=JSON.parse(await page.getByRole('textbox',{name:'MCP 配置'}).inputValue());
  assert.equal(config.mcpServers['cirdc-research'].url,origin+'/api/agent/v1/mcp');
  assert.equal(config.mcpServers['cirdc-research'].type,'http');
  assert.equal(await page.getByRole('textbox',{name:'MCP 服务地址',exact:true}).inputValue(),origin+'/api/agent/v1/mcp');
  const example=page.getByRole('textbox',{name:'MCP 配置',exact:true}).locator('..');
  await example.getByRole('button',{name:'复制',exact:true}).click();
  await page.getByText('已选中文本，请手动复制。',{exact:true}).waitFor();
  assert.equal(await example.locator('textarea').evaluate(el=>el.selectionEnd-el.selectionStart),JSON.stringify(config,null,2).length);
  const skillUrl=await page.getByRole('link',{name:'在线 Skill',exact:true}).getAttribute('href');
  assert.equal(skillUrl,origin+'/api/agent/v1/skills/cirdc-research/SKILL.md');
  assert((await page.evaluate(url=>fetch(url).then(r=>r.text()),skillUrl)).includes('next_cursor'));
  assert.equal(await page.locator('a[download]').count(),0);
  if(process.env.CIRDC_BROWSER_OUTPUT)await page.screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,'agent-access-'+width+'.png'),fullPage:true});
  await page.getByRole('button',{name:'English',exact:true}).click();
  await page.getByRole('heading',{name:'AI access',exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'Online Skill',exact:true}).count(),1);
  assert.equal(await page.getByRole('textbox',{name:'Install from repository source',exact:true}).count(),1);
  assert.equal(await page.getByRole('textbox',{name:'Install in Codex',exact:true}).count(),1);
  assert.equal(await page.getByRole('textbox',{name:'Install in Claude Code',exact:true}).count(),1);
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  assert.equal(requests.filter(r=>r.path==='/api/agent/v1/capabilities').length,1);
  assert.equal(requests.filter(r=>r.path==='/api/auth/session'||r.path.endsWith('/ensure')).length,0);
  assert.deepEqual(errors,[]);
  reports.push({width,bilingual:true,copyFallback:true,remoteMCP:true,onlineSkill:true,sourceRequests:0});await context.close();
 }}finally{await browser.close();}
 console.log(JSON.stringify(reports,null,2));
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'agent-access-browser.json'),JSON.stringify(reports,null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
