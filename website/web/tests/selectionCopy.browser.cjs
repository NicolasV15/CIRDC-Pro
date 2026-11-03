/* Fixture-only acceptance. Set PLAYWRIGHT_MODULE, optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE and CIRDC_BROWSER_OUTPUT. All requests are mocked. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=process.env.CIRDC_COPY_STATIC_ROOT||path.resolve(__dirname,'../../src/cirdc/web/static'),aid='83000801';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
const title='Selection <b>bold</b> $x_1$',abstract='<p>Detail <b>bold</b> and <i>italic</i> with $a_1$.</p><p>Second paragraph.</p>';
const body='<section id="sec1"><h2>SECTION I. Introduction</h2><p id="partial">prefix selected suffix</p><p id="rich">A <strong>bold</strong> and <em>italic</em> <a href="https://example.test/ref">link</a>.</p><p id="mixed">Value <span class="doc-math" id="inline-math">\\(\\frac{x_1}{y^2}\\)</span> end.</p><span class="doc-math" id="block-math">\\[\\begin{align*}a&=b\\\\c&=d\\end{align*}\\]</span><p id="scripts">H<sub>2</sub>O and x<sup>2</sup></p><ol id="list" start="3"><li>First</li><li>Second</li></ol><table id="simple"><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table><table id="merged"><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table><p id="special">50% &amp; # _ $ \\ { } ~ ^ &lt; &gt;</p><p id="citation">Source <a id="context_ref_1_2a">[1]</a>.</p></section><section id="sec2"><h2>SECTION II. Results</h2><p>Cached body text.</p></section>';
async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const profile of [{name:'http-desktop',width:1440,height:1000,secure:false},{name:'http-mobile',width:390,height:844,secure:false,touch:true},{name:'secure-desktop',width:1440,height:1000,secure:true},{name:'http-narrow-dark',width:320,height:760,secure:false,touch:true,dark:true}]){
  const origin=profile.secure?'http://localhost:19123':'http://selection-copy.test';const context=await browser.newContext({viewport:{width:profile.width,height:profile.height},locale:'zh-CN',timezoneId:'Asia/Shanghai',isMobile:!!profile.touch,hasTouch:!!profile.touch,colorScheme:profile.dark?'dark':'light'});
  if(profile.secure)await context.grantPermissions(['clipboard-read','clipboard-write'],{origin});
  const requests=[],blocked=[],posts=[],errors=[];let source='ieee_html';
  await context.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url()),p=u.pathname;if(u.origin!==origin){blocked.push(req.url());return route.abort();}requests.push(p);
   if(req.method()!=='GET'){posts.push(p);return route.abort();}
   if(p==='/'||p.startsWith('/papers/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:'fixture'}});
   if(p==='/api/overview')return route.fulfill({json:{index:{phase:'ready',year_range:{min:1884,max:2027},overview:{papers:1,venues:[],field_states:[]}}}});
   if(p==='/api/venues')return route.fulfill({json:{items:[]}});
   if(p==='/api/papers')return route.fulfill({json:{items:[{number:aid,title,authors:'',author_refs:[],publication:'Fixture',venue:'4',kind:'Journals',year:2025,doi:'',snippet:'Preview <b>bold</b> with $z_1$. '+('Visible preview text. '.repeat(25))+'UNSELECTED REST',abstract_state:'complete',keywords_state:'complete',resources:[]}],total:1,next_cursor:null,partial:false}});
   if(p.endsWith('/metadata/status'))return route.fulfill({json:{state:'disabled'}});
   if(p==='/api/papers/'+aid)return route.fulfill({json:{paper:{number:aid,record:{articleTitle:title,authors:[],abstract,keywords:{'Author Keywords':['RF']}},resources:[{kind:'document',href:'/api/fixture-content'}]}}});
   if(p==='/api/fixture-content')return route.fulfill({json:{state:'ready',document:{source,version:'v1',state:'ready',body_url:'/api/fixture-body',toc:[{id:'sec1',title:'Introduction',level:2},{id:'sec2',title:'Results',level:2}],assets_ready:0,assets_total:0}}});
   if(p==='/api/fixture-body')return route.fulfill({contentType:'text/html',body});
   if(p.endsWith('/references'))return route.fulfill({json:{number:aid,state:'complete',version:'r1',total:1,expected_total:1,checked_at:null,error:null,offset:0,limit:50,next_offset:null,items:[{order:1,label:'1',source_id:'ref1',text:'Reference one',title:'Reference one',target_number:'456',doi:null,target_kind:'paper',target_url:'/papers/456'}]}});
   if(p.endsWith('/citations'))return route.fulfill({json:{number:aid,state:'disabled',version:null,group:u.searchParams.get('group')||'ieee',total:0,expected_total:null,counts:{ieee:null,nonIeee:null,total:null},stored_counts:{ieee:0,nonIeee:0,total:0},group_states:{ieee:'disabled',nonIeee:'disabled'},source_presence:'unknown',empty_reason:null,checked_at:null,last_attempt_at:null,next_check_at:null,stale:false,error:null,offset:0,limit:50,next_offset:null,items:[]}});
   if(p.endsWith('/patent-citations'))return route.fulfill({json:{number:aid,state:'disabled',version:null,total:0,expected_total:null,source_presence:'unknown',empty_reason:null,checked_at:null,last_attempt_at:null,next_check_at:null,stale:false,error:null,offset:0,limit:50,next_offset:null,items:[]}});
   blocked.push(p);return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
  async function select(selector,start,end){await page.locator(selector).scrollIntoViewIfNeeded();return page.evaluate(({selector,start,end})=>{
   if(document.activeElement instanceof HTMLElement)document.activeElement.blur();const el=document.querySelector(selector),range=document.createRange();
   if(start===undefined)range.selectNodeContents(el);else{const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode())if(n.textContent.includes(start)){const a=n.textContent.indexOf(start);range.setStart(n,a);range.setEnd(n,a+(end??start.length));break;}}
   const s=getSelection();s.removeAllRanges();s.addRange(range);document.dispatchEvent(new Event('selectionchange'));window.__selectedText=s.toString();return s.toString();
  },{selector,start,end});}
  const toolbar=()=>page.getByRole('toolbar',{name:'选区复制',exact:true});
  async function copy(format){const button=toolbar().getByRole('button',{name:format,exact:true});await button.waitFor();if(profile.touch)await button.tap();else await button.click();}
  async function fallback(){await page.getByRole('dialog').waitFor();assert(!(await page.getByRole('dialog').innerText()).includes('已复制'));return page.getByRole('textbox',{name:'格式源码',exact:true});}
  async function close(){await page.getByRole('button',{name:'关闭复制预览',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.selection-copy-dialog'));await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
  await page.goto(origin+'/',{waitUntil:'networkidle'});await page.getByRole('button',{name:'中文',exact:true}).click();await page.locator('.paper-title .katex').waitFor();
  assert(!requests.some(p=>p.includes('SelectionCopyToolbar')),'Converter must not load before selection');
  const original=await select('.paper-title .scientific-title','bold',4);await toolbar().waitFor();assert(requests.some(p=>p.includes('SelectionCopyToolbar')));
  if(profile.secure){
   await page.evaluate(()=>{window.__nativeCopy=[];document.addEventListener('copy',e=>setTimeout(()=>window.__nativeCopy.push(e.defaultPrevented),0));});await page.keyboard.press('Control+c');assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),original);assert.deepEqual(await page.evaluate(()=>window.__nativeCopy),[false]);
   await copy('复制 Markdown');await toolbar().getByRole('status').waitFor();assert((await page.evaluate(()=>navigator.clipboard.readText())).includes('**bold**'));assert.equal(await page.evaluate(()=>getSelection().toString()),original);
  }else{
   await copy('复制 Markdown');let output=await fallback();assert((await output.inputValue()).includes('**bold**'),JSON.stringify({output:await output.inputValue(),dom:await page.locator('.paper-title').innerHTML(),preview:await page.getByRole('dialog').innerText()}));assert(!(await output.inputValue()).includes('Selection'));
   await page.getByRole('button',{name:'复制 LaTeX',exact:true}).click();assert((await output.inputValue()).includes('\\textbf{bold}'));await close();assert.equal(await page.evaluate(()=>getSelection().toString()),original);
  }
  // Selection spanning the visible preview and its hidden measuring copy exports the preview once.
  await select('.paper-row',undefined);await page.evaluate(()=>{const a=document.querySelector('.paper-title'),b=document.querySelector('.snippet:not(.abstract-measure)'),r=document.createRange();r.setStart(a,0);r.setEnd(b,b.childNodes.length);getSelection().removeAllRanges();getSelection().addRange(r);document.dispatchEvent(new Event('selectionchange'));});
  await toolbar().waitFor();if(!profile.secure){await copy('复制纯文本');const output=await fallback(),value=await output.inputValue();assert.equal(value.split('Preview').length-1,1);assert(!value.includes('UNSELECTED REST'));assert(!value.includes('展开摘要'));assert.equal(value.split('z_1').length-1,1);await close();}
  await page.locator('.paper-title').click();await page.locator('#partial').waitFor();await page.locator('#inline-math .katex').waitFor();
  const readCount=requests.filter(p=>p==='/api/fixture-body').length;
  if(!profile.touch){
   await page.locator('#partial').scrollIntoViewIfNeeded();const rect=await page.locator('#partial').evaluate(el=>{const r=document.createRange();r.selectNodeContents(el);const b=r.getBoundingClientRect();return {left:b.left,right:b.right,top:(b.top+b.bottom)/2};});
   await page.mouse.move(rect.left+1,rect.top);await page.mouse.down();await page.mouse.move(rect.right-1,rect.top,{steps:10});await page.mouse.up();await toolbar().waitFor();assert((await page.evaluate(()=>getSelection().toString())).includes('selected'));
  }

  const cases=[['#partial','selected',8,'selected'],['.abstract-panel .abstract','bold',4,'**bold**'],['#scripts',undefined,undefined,'H<sub>2</sub>O and x<sup>2</sup>'],['#simple',undefined,undefined,'| A | B |\n| --- | --- |\n| 1 | 2 |'],['#list',undefined,undefined,'3. First\n4. Second']];
  for(const [selector,start,end,expected] of cases){await select(selector,start,end);await copy('复制 Markdown');if(profile.secure){await toolbar().getByRole('status').waitFor();assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),expected);}else{const output=await fallback();assert.equal(await output.inputValue(),expected);await close();}}
  await page.locator('#inline-math').scrollIntoViewIfNeeded();await page.evaluate(()=>{const e=document.querySelector('#inline-math .katex-html .mord'),w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),n=w.nextNode(),r=document.createRange();r.setStart(n,0);r.setEnd(n,1);getSelection().removeAllRanges();getSelection().addRange(r);document.dispatchEvent(new Event('selectionchange'));});
  await copy('复制 LaTeX');if(profile.secure)assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),'\\(\\frac{x_1}{y^2}\\)');else{assert.equal(await (await fallback()).inputValue(),'\\(\\frac{x_1}{y^2}\\)');await close();}
  await select('#block-math');await copy('复制 LaTeX');const env='\\begin{align*}a&=b\\\\c&=d\\end{align*}';if(profile.secure)assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),env);else{assert.equal(await (await fallback()).inputValue(),env);await close();}
  await select('#merged');await copy('复制 Markdown');if(profile.secure){await toolbar().getByRole('status').waitFor();assert((await toolbar().innerText()).includes('部分结构已简化'));}else{await fallback();assert((await page.getByRole('dialog').innerText()).includes('合并单元格'));await close();}
  if(profile.secure){await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>Promise.reject(Error('denied'))}}));await select('#partial','selected',8);await copy('复制纯文本');assert.equal(await (await fallback()).inputValue(),'selected');await close();}
  await page.locator('.document-reader .reference-toggle').click();assert(!await page.locator('.document-body').isVisible());await page.locator('.document-reader .reference-toggle').click();assert.equal(requests.filter(p=>p==='/api/fixture-body').length,readCount);await page.locator('#context_ref_1_2a').click();await page.locator('.paper-references li.is-highlighted').waitFor();
  source='pdf_parse';await page.reload({waitUntil:'networkidle'});await page.locator('#inline-math .katex').waitFor();if(profile.secure)await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>Promise.reject(Error('denied'))}}));await select('#mixed');await copy('复制 Markdown');const expected='Value $\\frac{x_1}{y^2}$ end.';
  if(profile.secure){assert.equal(await (await fallback()).inputValue(),expected);await close();}else{assert.equal(await (await fallback()).inputValue(),expected);await page.getByRole('button',{name:'English',exact:true}).count();await close();}
  await page.getByRole('button',{name:'English',exact:true}).click();await select('#partial','selected',8);await page.getByRole('toolbar',{name:'Copy selection',exact:true}).getByRole('button',{name:'Copy Markdown',exact:true}).click();await page.getByRole('dialog').waitFor();assert.equal(await page.getByRole('textbox',{name:'Format source',exact:true}).inputValue(),'selected');await page.getByRole('button',{name:'Close copy preview',exact:true}).click();
  assert.deepEqual(posts,[]);assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  reports.push({profile:profile.name,lazyBeforeSelection:true,listTitle:true,listPreviewDeduplicated:true,detailAbstractMapped:true,bodyHTML:true,pdfHTML:true,partialParagraph:true,partialFormulaAtomic:true,sourceTeXPreserved:true,mathEnvironmentNotNested:true,htmlScriptsPreserved:true,lists:true,simpleTable:true,mergedTableExplicitFallback:true,modernClipboard:profile.secure,httpOrDeniedPreview:true,noFalseCopied:true,selectionPreserved:true,nativeCopyUnchanged:profile.secure,mobileTouch:!!profile.touch,bilingual:true,existingDisclosureAndReferenceJump:true,sourceRequests:0,realApiRequests:0});console.log(JSON.stringify(reports.at(-1)));await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'ui-result.json'),JSON.stringify({reports},null,2)+'\n');
}
main().catch(error=>{console.error(error);process.exitCode=1});
