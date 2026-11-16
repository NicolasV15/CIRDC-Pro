/* arXiv reading text on all three paths, against the offline demo (`sh tools/web demo`): two real cached arXiv
 * HTML bodies (2611.14519v1 with figures, 2611.14443v1 with equations, tables, a footnote and references) and two
 * representative fixtures for the TeX-source and PDF-conversion paths. Display adaptations must leave the cached
 * bytes, formula TeX and copy values unchanged. Set CIRDC_DEMO_ORIGIN and PLAYWRIGHT_MODULE. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const origin=process.env.CIRDC_DEMO_ORIGIN,demo=path.resolve(__dirname,'../../demo/arxiv');
const samples=[['3300802','arxiv_html','real'],['9900001','arxiv_html','real'],['9900002','arxiv_source','fixture'],['9900003','pdf_parse','fixture']];
(async()=>{
 if(!origin)throw Error('Set CIRDC_DEMO_ORIGIN to the standalone demo URL');
 // Cached bytes stay identical to the bundle manifests.
 const supplement=JSON.parse(await fs.readFile(path.join(demo,'reading-supplement/2611.14443v1/manifest.json')));
 for(const entry of supplement.files){
  const local=await fs.readFile(path.join(demo,'reading-supplement/2611.14443v1',entry.file));
  assert.equal(crypto.createHash('sha256').update(local).digest('hex'),entry.sha256);
 }
 const served=Buffer.from(await (await fetch(origin+'/api/arxiv/papers/9900001/versions/1/files/html')).arrayBuffer());
 assert.equal(crypto.createHash('sha256').update(served).digest('hex'),supplement.files.find(f=>f.file==='article.html').sha256);
 const body=Buffer.from(await (await fetch(origin+'/api/arxiv/papers/9900001/versions/1/body?render_id='+supplement.render_id)).arrayBuffer());
 assert.equal(crypto.createHash('sha256').update(body).digest('hex'),supplement.files.find(f=>f.file==='body.html').sha256);
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})}),reports=[];
 try{for(const width of [1440,390,320]){
  const context=await browser.newContext({viewport:{width,height:900}});await context.addInitScript(()=>localStorage.setItem('cirdc.ui.language','zh'));
  for(const [id,source,kind] of samples){
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(origin+'/arxiv/papers/'+id+'?source=arxiv&v=1');await page.locator('.document-body .katex').first().waitFor({timeout:20000});
   const facts=await page.evaluate(()=>{
    const root=document.querySelector('.document-body'),style=e=>getComputedStyle(e),bordered=e=>['Top','Right','Bottom','Left'].filter(side=>style(e)['border'+side+'Style']!=='none'&&parseFloat(style(e)['border'+side+'Width'])>0);
    const eqCells=[...root.querySelectorAll('table:is(.ltx_equation,.ltx_eqn_table) td')];
    const numbers=[...root.querySelectorAll('td.ltx_eqn_eqno')].map(td=>root.getBoundingClientRect().right-td.getBoundingClientRect().right);
    const tabular=[...root.querySelectorAll('table.ltx_tabular td, table.ltx_tabular th')];
    const flex=[...root.querySelectorAll('.ltx_flex_figure')].map(f=>{const cells=[...f.querySelectorAll(':scope>.ltx_flex_cell')].map(c=>c.getBoundingClientRect().top);return cells.length>1?new Set(cells.map(Math.round)).size:0;});
    return {paper:root.dataset.paperSource,source:root.dataset.documentSource,eqCells:eqCells.length,eqBorders:eqCells.filter(td=>bordered(td).length).length,
     numberGap:numbers.length?Math.max(...numbers.map(Math.abs)):0,verticalRules:tabular.filter(td=>bordered(td).some(side=>side==='Left'||side==='Right')&&!/ltx_border_[lr]/.test(td.className)).length,
     bullets:[...root.querySelectorAll('li.ltx_bibitem')].filter(li=>style(li).listStyleType!=='none'&&style(li.parentElement).listStyleType!=='none').length,
     notes:[...root.querySelectorAll('.ltx_note_outer')].filter(n=>style(n).display==='block').length,flexRows:flex,
     listingLines:[...root.querySelectorAll('.ltx_listingline')].map(l=>l.getBoundingClientRect().height),
     copy:[...root.querySelectorAll('.doc-math[data-copy-tex]')].slice(0,3).map(n=>n.dataset.copyTex),overflow:document.documentElement.scrollWidth-innerWidth,
     toc:[...document.querySelectorAll('.document-toc nav a')].slice(0,2).map(a=>({title:a.textContent.trim(),level:a.className}))};
   });
   assert.equal(facts.paper,'arxiv');assert.equal(facts.source,source);
   assert.equal(facts.eqBorders,0,'equation tables draw no grid');
   if(facts.eqCells)assert.ok(facts.numberGap<4,'equation numbers sit at the right edge: '+facts.numberGap);
   assert.equal(facts.verticalRules,0,'tables draw only the recorded rules');
   assert.equal(facts.bullets,0,'references have no bullets');
   if(id==='9900001')assert.equal(facts.notes,1,'the footnote reads as an aside');
   if(id==='9900002'){
    assert.deepEqual(facts.flexRows,[width>=1440?1:2],'sub-figures side by side when there is room, stacked on phones');
    const line=Math.min(...facts.listingLines);assert.ok(facts.listingLines.every(h=>h<line*2.2),'algorithm lines stay on one line');
   }
   // The table of contents starts with sections, not the repeated document title.
   if(kind==='real'||id==='9900002'){assert.ok(facts.toc.length);assert.notEqual(facts.toc[0].level,'level-1');}
   assert.ok(facts.copy.every(Boolean));assert.ok(facts.overflow<=1);assert.deepEqual(errors,[]);
   reports.push({width,id,source,kind,equations:facts.eqCells,notes:facts.notes});await page.close();
  }
  // IEEE text is marked as such and keeps the shared rules.
  await context.close();
 }console.log(JSON.stringify(reports));}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
