/* Recovery compatibility against the built reader. All requests use fixtures. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../../src/cirdc/web/static'),origin='http://recovery.test';
const message='后台服务繁忙，请求高峰期，请重新尝试获取';
const translated='Backend services are busy during peak demand. Please try retrieving the resource again.';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'};
async function main(){
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const width of [1440,390,320])for(const lang of ['zh','en']){
  const context=await browser.newContext({viewport:{width,height:950}}),page=await context.newPage();
  await context.addInitScript(lang=>localStorage.setItem('cirdc.ui.language',lang),lang);
  const posts=[],unexpected=[],errors=[],reads={body:0,pdf:0};let phase='wait';
  page.on('pageerror',error=>errors.push(error.message));
  await context.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url()),p=url.pathname;
   if(request.method()!=='GET'){posts.push(p);return route.abort();}
   if(url.origin!==origin){unexpected.push(request.url());return route.abort();}
   if(p==='/papers/100')return route.fulfill({contentType:'text/html',body:await fs.readFile(root+'/index.html')});
   if(p.startsWith('/assets/'))return route.fulfill({contentType:types[path.extname(p)]||'application/octet-stream',body:await fs.readFile(root+p)});
   if(p==='/api/auth/session')return route.fulfill({json:{interface:'reader',authentication_required:false,user:null,csrf:''}});
   if(p==='/api/overview')return route.fulfill({json:{index:{phase:'ready',overview:{papers:1}}}});
   if(p==='/api/papers/100')return route.fulfill({json:{paper:{number:'100',record:{articleTitle:'Recovery fixture',authors:[],abstract:'Cached abstract.',keywords:{}},resources:[{kind:'document',href:'/api/content/100/body'},{kind:'pdf-acquisition',href:'/api/content/100/pdf'}]}}});
   if(p==='/api/content/100/html')return route.fulfill({contentType:'text/html',body:'<p>Cached body remains readable.</p>'});
   if(p==='/api/content/100/body'||p==='/api/content/100/pdf'){
    const body=p.endsWith('/body');reads[body?'body':'pdf']++;
    const document={version:'v1',source:'ieee_html',body_url:'/api/content/100/html',toc:[],assets_ready:0,assets_total:1};
    if(phase==='ready')return route.fulfill({json:body?{state:'ready',document}:{state:'ready',reader_url:'/api/resources/100/pdf'}});
    return route.fulfill({json:{state:body?'partial':'failed',next_action:phase,message,retry_attempts:phase==='wait'?1:10,max_retry_attempts:10,
     job:{kind:body?'ieee_html':'ieee_pdf',state:'failed',error:'internal_failure'},...(body?{document}:{})}});
   }
   if(p.endsWith('/metadata/status'))return route.fulfill({json:{state:'disabled'}});
   if(p.endsWith('/references')||p.endsWith('/citations')||p.endsWith('/patent-citations'))return route.fulfill({json:{state:'disabled',items:[],total:0,counts:{ieee:null,nonIeee:null,total:null},source_presence:'unknown'}});
   unexpected.push(p);return route.abort();
  });
  const pdf=page.locator('.pdf-acquisition'),body=page.locator('.document-body');
  await page.goto(origin+'/papers/100',{waitUntil:'networkidle'});
  await body.getByText('Cached body remains readable.',{exact:true}).waitFor();
  await pdf.getByText(lang==='zh'?message:translated,{exact:true}).waitFor();
  assert(await pdf.locator('button').isDisabled());
  await page.waitForTimeout(2200);assert(reads.pdf>=2&&reads.body>=2,'Both resources must keep polling');
  phase='contact_administrator';
  await pdf.locator('button').waitFor({state:'detached'});
  await page.locator('.document-reader .error').waitFor();
  const stopped={...reads};await page.waitForTimeout(2200);assert.deepEqual(reads,stopped,'Exhaustion must stop polling');
  assert(await body.isVisible());assert.equal(await page.locator('.document-reader button').filter({hasText:/重试|Retry/}).count(),0);
  assert(!(await page.locator('body').innerText()).includes('internal_failure'));
  const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,elements:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(el=>({tag:el.tagName,class:el.className,text:el.textContent.slice(0,100),right:el.getBoundingClientRect().right}))}));
  assert(overflow.scroll<=width,JSON.stringify({lang,...overflow}));
  phase='ready';await page.reload({waitUntil:'networkidle'});await page.locator('a.detail-pdf-trigger').waitFor();
  assert(await body.isVisible());assert.deepEqual(posts,[]);assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
  reports.push({width,lang,waitingPolled:true,exhaustionStopped:true,partialReadable:true,readyPdfReadable:true,posts:0});
  await context.close();
 }}finally{await browser.close();}
 if(process.env.CIRDC_BROWSER_OUTPUT){await fs.mkdir(process.env.CIRDC_BROWSER_OUTPUT,{recursive:true});await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'recovery-result.json'),JSON.stringify(reports,null,2)+'\n');}
 console.log(JSON.stringify(reports));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
