/* Fixture-only acceptance. Set PLAYWRIGHT_MODULE, optionally
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE and CIRDC_BROWSER_OUTPUT. All requests are mocked. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),ts=require('typescript');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../src');
async function moduleURL(name,imports={}){let js=ts.transpileModule(await fs.readFile(path.join(root,name),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;for(const [key,url] of Object.entries(imports))js=js.replaceAll("'"+key+"'",JSON.stringify(url));return 'data:text/javascript;base64,'+Buffer.from(js).toString('base64');}
async function main(){
 const citations=await moduleURL('citations.ts'),titles=await moduleURL('titleMath.ts',{'./citations.ts':citations}),formats=await moduleURL('selectionFormats.ts'),content=await moduleURL('selectionContent.ts',{'./titleMath':titles,'./selectionFormats':formats});
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage();let requests=0;await page.route('**/*',route=>{requests++;return route.abort();});
  const reports=await page.evaluate(async(url)=>{
   const {captureSelection}=await import(url),scope=document.createElement('main');scope.dataset.copyScope='';document.body.append(scope);const reports=[];
   function set(html){scope.innerHTML=html;}
   function capture(start,from,end=start,to=from){const range=document.createRange();range.setStart(start,from);range.setEnd(end,to);return captureSelection(range,scope,'https://example.test/papers/123');}
   function whole(node){const range=document.createRange();range.selectNodeContents(node);return captureSelection(range,scope,'https://example.test/papers/123');}
   function eq(actual,expected,name){if(actual!==expected)throw Error(name+': '+JSON.stringify(actual)+' != '+JSON.stringify(expected));reports.push(name);}
   set('<p id="p">prefix selected suffix</p>');eq(capture(scope.firstChild.firstChild,7,scope.firstChild.firstChild,15).values.text,'selected','partial paragraph');
   set('<p>A <strong>boldword</strong> Z</p>');const strong=scope.querySelector('strong').firstChild;eq(capture(strong,3,strong,7).values.markdown,'**dwor**','partial bold retains emphasis');
   set('<p>Alpha one</p><p>Beta two</p>');eq(capture(scope.firstChild.firstChild,6,scope.lastChild.firstChild,4).values.text,'one\n\nBeta','cross paragraphs do not expand');
   set('<h2>Heading word</h2>');eq(capture(scope.firstChild.firstChild,0,scope.firstChild.firstChild,7).values.markdown,'## Heading','partial heading level');
   set('<p>before <span data-copy-tex="\\frac{x_1}{y^2}" data-copy-raw="$\\frac{x_1}{y^2}$"><span class="katex"><span class="katex-mathml"><annotation encoding="application/x-tex">WRONG_SOURCE</annotation></span><span class="katex-html" aria-hidden="true"><span id="visual">VISUAL</span></span></span></span> after</p>');
   eq(whole(scope.firstChild).values.markdown,'before $\\frac{x_1}{y^2}$ after','source TeX precedes annotation');const visual=scope.querySelector('#visual').firstChild;eq(capture(visual,1,visual,3).values.markdown,'$\\frac{x_1}{y^2}$','formula interior expands formula only');
   eq(capture(scope.firstChild.firstChild,0,scope.querySelector('[data-copy-tex]'),0).values.text,'before ','formula at zero end offset excluded');
   set('<p><span class="katex"><span class="katex-mathml"><annotation encoding="application/x-tex">x_1^2</annotation></span><span class="katex-html" aria-hidden="true">DUPLICATE</span></span></p>');eq(whole(scope.firstChild).values.text,'x_1^2','annotation fallback deduplicates');
   set('<div><p class="abstract-measure" aria-hidden="true">DUPLICATE</p><p>visible <b>selected</b><button>Copy</button><span class="abstract-tail">… expand</span></p><nav>CONTENTS</nav><p hidden>HIDDEN</p></div>');eq(whole(scope.firstChild).values.text,'visible selected','hidden copies controls and TOC excluded');
   set('<p>V<sub>out</sub><sup>2</sup></p>');eq(whole(scope.firstChild).values.text,'V_{out}^{2}','HTML scripts retained');
   set('<ol start="4"><li>first</li><li>second</li></ol>');const li=scope.querySelectorAll('li')[1].firstChild;eq(capture(li,0,li,6).values.markdown,'5. second','partial ordered list ordinal');
   set('<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>');eq(whole(scope.firstChild).values.markdown,'| A | B |\n| --- | --- |\n| 1 | 2 |','simple complete table');
   const cell=scope.querySelector('td').firstChild,result=capture(cell,0,cell,1);eq(result.values.text,'1','partial table copies selected cell only');if(!result.warnings.text.includes('table-simplified'))throw Error('partial table warning missing');
   set('<table><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table>');const merged=whole(scope.firstChild);eq(merged.values.text,'A\tB\nC','merged cells conservative rows');if(!merged.warnings.markdown.includes('table-simplified'))throw Error('merged warning missing');
   set('<p data-copy-source-mode="literal">Bold and italic</p>');let p=scope.firstChild;p.dataset.copySourceHtml='<b>Bold</b> and <i>italic</i><img src="https://must-not-load.test/a.png">';eq(capture(p.firstChild,0,p.firstChild,4).values.markdown,'**Bold**','plain detail recovers matched source formatting');
   set('<p data-copy-source-mode="literal">A &amp;amp; B</p>');p=scope.firstChild;p.dataset.copySourceHtml='<b>A &amp; B</b>';const mismatch=whole(p);eq(mismatch.values.text,'A &amp; B','unmatched source preserves displayed text');if(!mismatch.warnings.text.includes('source-unmapped'))throw Error('mapping warning missing');
   set('<p data-copy-source-mode="normalized">Selection bold <span data-copy-tex="x_1" data-copy-raw="$x_1$">visual</span></p>');p=scope.firstChild;p.dataset.copySourceHtml='Selection <b>bold</b> $x_1$';eq(capture(p.firstChild,10,p.firstChild,14).values.markdown,'**bold**','source math keeps whitespace next to formatting tags');
   set('<p data-copy-source-mode="literal">Value <span data-copy-tex="x_1" data-copy-raw="$x_1$">visual</span> mm<sup>2</sup></p>');p=scope.firstChild;p.dataset.copySourceHtml='Value <inline-formula><tex-math><![CDATA[$x_1$]]></tex-math></inline-formula> mm<sup>2</sup>';eq(whole(p).values.markdown,'Value $x_1$ mm<sup>2</sup>','XML TeX source maps rendered abstract math and scripts');if(whole(p).warnings.markdown.includes('source-unmapped'))throw Error('XML TeX mapping mismatch');
   set('<p data-copy-source-mode="literal">$x^2$</p>');p=scope.firstChild;p.dataset.copySourceHtml='$x^2$';eq(capture(p.firstChild,1,p.firstChild,2).values.markdown,'$x^2$','plain detail source formula atomic');
   set('<p><span data-copy-source-mode="prefix">Visible <b>prefix</b></span><span class="abstract-tail">… expand</span></p>');const prefix=scope.querySelector('span');prefix.dataset.copySourceHtml='Visible <b>prefix</b> UNSELECTED REST';eq(whole(scope.firstChild).values.markdown,'Visible **prefix**','collapsed preview maps only displayed prefix');
   set('<p><a href="javascript:bad()">safe text</a></p>');const link=whole(scope.firstChild);eq(link.values.markdown,'safe text','unsafe URL omitted');if(!link.warnings.text.includes('link-omitted'))throw Error('link warning missing');
   set('<p><span class="katex"><span class="katex-html">UNKNOWN</span></span></p>');const unknown=whole(scope.firstChild);eq(unknown.values.text,'','formula without TeX is not reconstructed');if(!unknown.warnings.text.includes('math-unavailable'))throw Error('math warning missing');
   return reports;
  },content);
  assert.equal(requests,0);if(process.env.CIRDC_BROWSER_OUTPUT)await fs.writeFile(path.join(process.env.CIRDC_BROWSER_OUTPUT,'dom-result.json'),JSON.stringify({passed:reports.length,reports,networkRequests:requests},null,2)+'\n');console.log(JSON.stringify({passed:reports.length,networkRequests:requests}));
 }finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1});
