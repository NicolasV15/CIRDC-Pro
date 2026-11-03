/* Fixture-only acceptance. Set PLAYWRIGHT_MODULE, optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE, CIRDC_ABSTRACT_FIXTURE and CIRDC_BROWSER_OUTPUT.
 * A supplied local paper fixture is read without contacting its source. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://abstract-rendering.test',aid='83000802';
const xml=tex=>'<inline-formula xmlns:mml="http://www.w3.org/1998/Math/MathML"><tex-math>$'+tex+'$</tex-math></inline-formula>';
const synthetic={articleTitle:'Cached abstract fixture',abstract:'A '+xml('\\text {DR}_{\\text {speech}}')+' example occupies 0.43mm<sup>2</sup> and 2.28 mm<sup>2</sup>. '+xml('x_1')+' and '+xml('y^2')+' use '+xml('14.4~\\mu ')+'W. Results '+xml('a<b>c')+' and '+xml('\\mu ')+' remain source expressions. 中文 &amp; text.'};
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
async function main(){
 const record=process.env.CIRDC_ABSTRACT_FIXTURE?JSON.parse(await fs.readFile(process.env.CIRDC_ABSTRACT_FIXTURE,'utf8')).paper.record:synthetic;
 const formulas=[...record.abstract.matchAll(/<tex-math\b[^>]*>\s*(?:<!\[CDATA\[)?\$([\s\S]*?)\$(?:\]\]>)?\s*<\/tex-math>/gi)].map(match=>match[1].trim());assert.equal(formulas.length,6);
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const profile of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844,touch:true},{name:'narrow-dark',width:320,height:760,touch:true,dark:true}]){
  const context=await browser.newContext({viewport:{width:profile.width,height:profile.height},locale:'zh-CN',isMobile:!!profile.touch,hasTouch:!!profile.touch,colorScheme:profile.dark?'dark':'light'}),blocked=[],posts=[],errors=[];
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;if(url.origin!==origin){blocked.push(req.url());return route.abort();}
   if(req.method()!=='GET'){posts.push(p);return route.abort();}
   if(p==='/'||p.startsWith('/papers/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:'fixture'}});
   if(p==='/api/overview')return route.fulfill({json:{index:{phase:'ready',year_range:{min:1884,max:2027},overview:{papers:1,venues:[],field_states:[]}}}});
   if(p==='/api/venues')return route.fulfill({json:{items:[]}});
   if(p==='/api/papers')return route.fulfill({json:{items:[{number:aid,title:record.articleTitle,authors:'',author_refs:[],publication:'Fixture',venue:'4',kind:'Journals',year:2026,doi:'',snippet:record.abstract,abstract_state:'complete',keywords_state:'complete',resources:[]}],total:1,next_cursor:null,partial:false}});
   if(p==='/api/papers/'+aid)return route.fulfill({json:{paper:{number:aid,record:{...record,authors:[],keywords:{}},resources:[]}}});
   if(p.endsWith('/metadata/status'))return route.fulfill({json:{state:'disabled'}});
   if(p.endsWith('/references')||p.endsWith('/citations')||p.endsWith('/patent-citations'))return route.fulfill({json:{number:aid,state:'disabled',version:null,total:0,items:[],next_offset:null,source_presence:'unknown',counts:{ieee:null,nonIeee:null,total:null},stored_counts:{ieee:0,nonIeee:0,total:0}}});
   blocked.push(p);return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));await page.goto(origin+'/',{waitUntil:'networkidle'});await page.getByRole('button',{name:'中文',exact:true}).click();
  await page.getByRole('button',{name:'展开摘要',exact:true}).click();await page.locator('.snippet.expanded .katex').first().waitFor();
  const list=page.locator('.snippet.expanded');assert.equal(await list.locator('.katex').count(),6);assert.equal(await list.locator('sup').count(),2);assert.equal(await list.locator('.scientific-title-fallback').count(),0);
  assert.deepEqual(await list.locator('annotation[encoding="application/x-tex"]').allTextContents().then(values=>values.map(v=>v.trim())),formulas);
  await page.locator('.paper-title').click();const abstract=page.locator('.abstract-panel .abstract');await abstract.locator('.katex').first().waitFor();assert.equal(await abstract.locator('.katex').count(),6);assert.equal(await abstract.locator('.scientific-title-fallback').count(),0);
  assert.deepEqual(await abstract.locator('annotation[encoding="application/x-tex"]').allTextContents().then(values=>values.map(v=>v.trim())),formulas);assert.deepEqual(await abstract.locator('sup').allTextContents(),['2','2']);
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  if(process.env.CIRDC_BROWSER_OUTPUT)await page.locator('.abstract-panel').screenshot({path:path.join(process.env.CIRDC_BROWSER_OUTPUT,'abstract-'+profile.name+'.png')});
  await page.getByRole('button',{name:'收起摘要',exact:true}).click();assert(!await abstract.isVisible());await page.getByRole('button',{name:'展开摘要',exact:true}).click();assert.equal(await abstract.locator('.katex').count(),6);
  await abstract.evaluate(el=>{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r);document.dispatchEvent(new Event('selectionchange'));});
  await page.getByRole('toolbar',{name:'选区复制',exact:true}).getByRole('button',{name:'复制 Markdown',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.waitFor();const output=page.getByRole('textbox',{name:'格式源码',exact:true});
  const markdown=await output.inputValue();for(const tex of formulas)assert(markdown.includes('$'+tex),'Markdown must retain '+tex);assert.equal((markdown.match(/<sup>2<\/sup>/g)||[]).length,2);assert(!(await dialog.innerText()).includes('部分原始格式无法'));
  await page.getByRole('button',{name:'复制 LaTeX',exact:true}).click();assert.equal(((await output.inputValue()).match(/\\textsuperscript\{2\}/g)||[]).length,2);
  await page.getByRole('button',{name:'复制纯文本',exact:true}).click();assert.equal(((await output.inputValue()).match(/\^\{2\}/g)||[]).length,2);
  await page.getByRole('button',{name:'关闭复制预览',exact:true}).click();await page.getByRole('button',{name:'English',exact:true}).click();assert.equal(await abstract.locator('.katex').count(),6);
  assert.deepEqual(blocked,[]);assert.deepEqual(posts,[]);assert.deepEqual(errors,[]);
  reports.push({profile:profile.name,formulas:6,superscripts:2,listExpanded:true,detail:true,copyAllFormats:true,sourceTeXUnchanged:true,disclosurePreserved:true,bilingual:true,sourceRequests:0,pdfConversions:0});console.log(JSON.stringify(reports.at(-1)));await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'abstract-result.json'),JSON.stringify({reports,fixture:process.env.CIRDC_ABSTRACT_FIXTURE?'supplied-local-paper':'synthetic'},null,2)+'\n');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
