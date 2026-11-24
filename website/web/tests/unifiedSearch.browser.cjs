/* Unified IEEE + arXiv search on the home page, against the offline demo (`sh tools/web demo`, 3 IEEE + 43 arXiv papers).
 * Covers the default mixed list, source checks, linked filters and fields, single-source field notes, a source that
 * fails while the other answers, cursor pages without duplicates, mixed citations and downloads, and both detail pages,
 * at 1440/390/320 in Chinese and English. Set CIRDC_DEMO_ORIGIN and PLAYWRIGHT_MODULE, optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE and CIRDC_SCREENSHOTS (a directory for page screenshots). */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const origin=process.env.CIRDC_DEMO_ORIGIN,shots=process.env.CIRDC_SCREENSHOTS;
const profiles=[['zh',1440],['en',1440],['zh',390],['en',390],['zh',320],['en',320]];
/** Runs in the page: overflow, buttons whose own text breaks onto a second line, and controls outside the viewport. */
function layout(){
 const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden';};
 const lines=node=>{const r=document.createRange();r.selectNodeContents(node);return new Set([...r.getClientRects()].filter(x=>x.width>1).map(x=>Math.round(x.top+x.height/2))).size;};
 const issues=[];
 for(const el of document.querySelectorAll('button,a.button,summary,label.search-source,.search-choice,.filter-chip,.source-badge')){
  if(!visible(el)||el.closest('details:not([open])>:not(summary),dialog:not([open])'))continue;
  const r=el.getBoundingClientRect(),name=(el.innerText||el.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ').slice(0,40);
  const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode()))if(node.textContent.trim()&&lines(node)>1){issues.push('wrapped: '+name);break;}
  if(r.right>innerWidth+1||r.left<-1)issues.push('outside: '+name);
 }
 const header=document.querySelector('.app-header-inner').getBoundingClientRect().height;
 return {overflow:document.documentElement.scrollWidth-innerWidth,issues,header,switches:document.querySelectorAll('.header-source-switch').length};
}
const rows=page=>page.locator('.paper-row').evaluateAll(list=>list.map(row=>row.dataset.source+':'+row.querySelector('.paper-number').textContent));
const params=page=>new URL(page.url()).searchParams;
async function settled(page){await page.locator('.paper-row').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.paper-list.is-loading')&&!!document.querySelector('.result-count'));}
async function check(page,label){const value=await page.evaluate(layout);assert.ok(value.overflow<=1,label+' overflow '+value.overflow);assert.deepEqual(value.issues,[],label);assert.ok(value.header<=60,label+' header '+value.header);assert.equal(value.switches,0,label);}
async function shot(page,name){if(shots)await page.screenshot({path:path.join(shots,name+'.png'),fullPage:false});}
async function openFilters(page,width){if(width<1024&&await page.locator('.filter-disclosure').getAttribute('open')===null)await page.locator('.filter-disclosure > summary').click();}
async function openOptions(page){const toggle=page.locator('.search-options-toggle');if(await toggle.isVisible()&&await toggle.getAttribute('aria-expanded')!=='true')await toggle.click();}
async function setSource(page,index,checked){const box=page.locator('.search-sources input').nth(index);const before=page.url();if(checked)await box.check();else await box.uncheck();await page.waitForFunction(url=>location.href!==url,before);await settled(page);}

(async()=>{
 if(!origin)throw Error('Set CIRDC_DEMO_ORIGIN');
 assert.equal((await fetch(origin+'/api/demo').then(r=>r.json())).offline,true);
 const all=await fetch(origin+'/api/search/unified?totals=only').then(r=>r.json());
 const ieeeTotal=all.sources.ieee.total,arxivTotal=all.sources.arxiv.total;assert.ok(ieeeTotal>0&&arxivTotal>25);
 if(shots)fs.mkdirSync(shots,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const [lang,width] of profiles){
  const tag=lang+'-'+width,context=await browser.newContext({viewport:{width,height:900},locale:lang==='zh'?'zh-CN':'en-US'});
  await context.addInitScript(l=>{localStorage.setItem('cirdc.ui.language',l);localStorage.setItem('cirdc.results.limit.v1','25');},lang);
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));

  // Default: both sources checked, one mixed list with a badge per row and counts per source.
  await page.goto(origin+'/');await settled(page);
  assert.equal(params(page).get('sources'),'ieee,arxiv');
  assert.deepEqual(await page.locator('.search-sources input').evaluateAll(list=>list.map(i=>i.checked)),[true,true]);
  await page.locator('.result-sources').waitFor();
  const counts=await page.locator('.result-sources').innerText();assert.ok(counts.includes('IEEE '+ieeeTotal)&&counts.includes('arXiv '+arxivTotal),counts);
  assert.ok((await page.locator('.result-total').innerText()).includes(String(ieeeTotal+arxivTotal)));
  const first=await rows(page);assert.ok(first.some(k=>k.startsWith('ieee:'))&&first.some(k=>k.startsWith('arxiv:')),'mixed rows');
  assert.equal(await page.locator('.paper-row .source-badge').count(),first.length);
  assert.equal(await page.locator('.venue-family-filter').count(),2);
  await check(page,tag+' home');await shot(page,'unified-home-'+tag);

  // Cursor pages: every match once, none skipped.
  while(await page.locator('.load-more').count()){const n=await page.locator('.paper-row').count();await page.locator('.load-more').click();await page.waitForFunction(n=>document.querySelectorAll('.paper-row').length>n,n);}
  const keys=await rows(page);assert.equal(new Set(keys).size,keys.length);assert.equal(keys.length,ieeeTotal+arxivTotal);
  await page.goto(origin+'/');await settled(page);

  // Mixed selection: one IEEE and one arXiv paper cite and download with their own identities.
  await page.locator('.paper-row[data-source=ieee] .paper-selection-control input').first().check();
  await page.locator('.paper-row[data-source=arxiv] .paper-selection-control input').first().check();
  await page.locator('.paper-selection-actions button').nth(0).click();
  const text=page.locator('.citation-dialog textarea');await text.waitFor();await page.waitForFunction(()=>document.querySelector('.citation-dialog textarea')?.value.includes('@'));
  const cite=await text.inputValue();assert.ok(cite.includes('arxiv.org/abs/')&&/ieeexplore\.ieee\.org|doi\.org/.test(cite)&&!/(ieee|arxiv):\d/.test(cite),cite);
  await page.locator('.citation-dialog .citation-close').click();await page.locator('.citation-dialog').waitFor({state:'detached'});
  await page.locator('.paper-selection-actions button').nth(1).click();
  await page.locator('.download-preview-list li').nth(1).waitFor();
  const ids=await page.locator('.download-preview-list li code').allTextContents();assert.equal(ids.length,2);assert.ok(ids.every(id=>!/^(ieee|arxiv):/.test(id)),ids.join());
  await page.locator('.batch-download-dialog .citation-close').click();await page.locator('.batch-download-dialog').waitFor({state:'detached'});
  await check(page,tag+' selection');

  // Only IEEE: IEEE filters and fields; the last checked source cannot be unchecked.
  await setSource(page,1,false);
  assert.equal(params(page).get('sources'),'ieee');assert.ok((await rows(page)).every(k=>k.startsWith('ieee:')));
  assert.equal(await page.locator('.search-sources input').nth(0).getAttribute('aria-disabled'),'true');await page.locator('.search-sources input').nth(0).click({force:true});await page.waitForTimeout(150);
  assert.equal(await page.locator('.search-sources input').nth(0).isChecked(),true);assert.equal(params(page).get('sources'),'ieee');
  await openOptions(page);assert.equal(await page.locator('.field-choices .search-choice').count(),6);
  await openFilters(page,width);assert.equal(await page.locator('.venue-family-filter').count(),1);assert.equal(await page.locator('.arxiv-category-filter').count(),0);
  await check(page,tag+' ieee');await shot(page,'unified-ieee-'+tag);

  // Only arXiv: category filters and fields.
  await setSource(page,1,true);await setSource(page,0,false);
  assert.equal(params(page).get('sources'),'arxiv');assert.ok((await rows(page)).every(k=>k.startsWith('arxiv:')));
  await openOptions(page);assert.equal(await page.locator('.field-choices .search-choice').count(),5);
  await openFilters(page,width);assert.equal(await page.locator('.arxiv-category-filter').count(),1);assert.equal(await page.locator('.venue-family-filter:not(.arxiv-category-filter)').count(),0);
  await check(page,tag+' arxiv');await shot(page,'unified-arxiv-'+tag);
  await setSource(page,0,true);

  // Both: each source's filter only narrows that source, and unchecking a source keeps its conditions for later.
  await openFilters(page,width);
  await page.locator('input[name=kind][value=Journals]').check();
  await page.locator('input[list=arxiv-categories]').fill('eess.SY');
  await page.locator('.filter-actions .primary').click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('category')==='eess.SY'&&new URLSearchParams(location.search).get('kind')==='Journals');await settled(page);
  assert.equal(await page.locator('.active-filters .filter-chip .source-badge').count(),2);
  const filtered=await page.locator('.paper-row').evaluateAll(list=>list.map(row=>({source:row.dataset.source,tags:[...row.querySelectorAll('.arxiv-category-tag')].map(x=>x.textContent)})));
  assert.ok(filtered.some(r=>r.source==='ieee')&&filtered.some(r=>r.source==='arxiv'));
  assert.ok(filtered.filter(r=>r.source==='arxiv').every(r=>r.tags.includes('eess.SY')));
  await setSource(page,0,false);assert.equal(params(page).has('kind'),false);assert.equal(params(page).get('category'),'eess.SY');
  await setSource(page,0,true);assert.equal(params(page).get('kind'),'Journals');assert.equal(params(page).get('category'),'eess.SY');
  await check(page,tag+' filters');await shot(page,'unified-filters-'+tag);
  await page.locator('.active-filters .text-button').click();await page.waitForFunction(()=>!new URLSearchParams(location.search).has('category'));await settled(page);

  // A field only one source supports: a one-line note, and only that source's papers.
  await openOptions(page);await page.locator('.search-main input:not([type])').fill('adc');
  await page.locator('.field-choices .search-choice').nth(3).click();
  await page.locator('.source-note').waitFor();assert.equal(params(page).get('field'),'keywords');
  assert.ok((await page.locator('.source-note').innerText()).includes('IEEE'));assert.ok((await rows(page)).every(k=>k.startsWith('ieee:')));
  if(lang==='en')assert.ok(!/[㐀-鿿]/.test(await page.locator('.source-note').innerText()));
  await check(page,tag+' field note');await shot(page,'unified-field-note-'+tag);
  await page.locator('.search-main input:not([type])').fill('eess');await page.locator('.field-choices .search-choice').nth(6).click();await page.waitForFunction(()=>new URLSearchParams(location.search).get('field')==='categories');await settled(page);
  assert.ok((await page.locator('.source-note').innerText()).includes('arXiv'));assert.ok((await rows(page)).every(k=>k.startsWith('arxiv:')));

  // One source failing: say which, show the other source's papers, and retry.
  await page.route('**/api/search/unified?**',async route=>{const response=await route.fetch(),body=await response.json();
   body.sources.arxiv={...body.sources.arxiv,status:'error',error:'search_busy',total:null,total_exact:false};body.partial=true;body.total=null;body.total_exact=false;
   body.items=body.items.filter(item=>item.source==='ieee');body.next_cursor=null;await route.fulfill({response,json:body});});
  await page.goto(origin+'/');await page.locator('.source-alert').waitFor();await settled(page);
  assert.ok((await page.locator('.source-alert').innerText()).includes('arXiv'));assert.ok((await rows(page)).every(k=>k.startsWith('ieee:')));
  await page.locator('.result-sources').waitFor();assert.ok((await page.locator('.result-sources').innerText()).includes('IEEE '+ieeeTotal));
  assert.equal(await page.locator('.result-total').count(),0);
  await check(page,tag+' partial');await shot(page,'unified-partial-'+tag);
  await page.unroute('**/api/search/unified?**');await page.locator('.source-alert button').click();
  await page.locator('.source-alert').waitFor({state:'detached'});await page.locator('.paper-row[data-source=arxiv]').first().waitFor();

  // Details: IEEE opens in place, arXiv returns to the same list.
  await page.locator('.paper-row[data-source=ieee] .paper-title').first().click();await page.locator('.detail-record-actions').waitFor();
  await page.locator('.detail-toolbar .back').click();await settled(page);assert.equal(new URL(page.url()).pathname,'/');
  const before=await rows(page);await page.locator('.paper-row[data-source=arxiv] .paper-title').nth(1).click();
  await page.locator('.arxiv-page .detail-header').waitFor();assert.equal(params(page).get('sources'),'ieee,arxiv');
  await page.locator('.detail-toolbar .back').click();await page.waitForURL(u=>new URL(u).pathname==='/'&&!new URL(u).searchParams.has('restore'));await settled(page);
  assert.deepEqual(await rows(page),before);
  assert.deepEqual(errors,[]);reports.push({profile:tag,mixed:true,pages:keys.length,citations:true,downloads:true,sources:true,filters:true,fieldNotes:true,partial:true,details:true});
  await context.close();
 }
 console.log(JSON.stringify(reports));}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
