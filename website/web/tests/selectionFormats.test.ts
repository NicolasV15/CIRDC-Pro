import assert from 'node:assert/strict';
import {test} from 'node:test';
import katex from 'katex';
import {escapeLatex,formatSelection,unwrappedMath,compactMathSource,type CopyNode} from '../src/selectionFormats.ts';
const text=(value:string):CopyNode=>({kind:'text',value});
const el=(tag:string,children:CopyNode[],extra:Record<string,unknown>={}):CopyNode=>({kind:'element',tag,children,...extra});
const math=(tex:string,display=false):CopyNode=>({kind:'math',tex,display});
test('plain copy converts all standard Greek commands and variants while preserving source formats',()=>{
 const names='alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega varepsilon vartheta varkappa varpi varrho varsigma varphi Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega'.split(' ');
 const symbols=[...'αβγδϵζηθικλμνξοπρστυϕχψωεϑϰϖϱςφΓΔΘΛΞΠΣΥΦΨΩ'];
 assert.equal(names.length,symbols.length);
 for(const [index,name] of names.entries()){
  const tex='\\'+name,result=formatSelection([math(tex)]),symbol=symbols[index];
  assert.equal(result.values.text,symbol,tex);
  assert.equal(result.values.markdown,'$'+tex+'$');
  assert.equal(result.values.latex,'\\('+tex+'\\)');
  // Match the installed renderer's semantic letter, including epsilon/phi variants.
  assert.match(katex.renderToString(tex,{output:'mathml',throwOnError:true}),new RegExp('<mi(?:\\s[^>]*)?>'+symbol+'</mi>'),tex);
 }
 assert.equal(formatSelection([math(String.raw`\mu`)]).values.text.codePointAt(0),0x03bc);
});
test('simple Greek expressions retain operators, unit spacing and paragraph boundaries',()=>{
 const result=formatSelection([el('p',[text('电容 '),math(String.raw`\mu\mathrm{F}`),text('；μ and '),math(String.raw`\alpha+\beta=2\pi`)]),math(String.raw`\Omega`,true)]);
 assert.equal(result.values.text,'电容 μF；μ and α+β=2π\n\nΩ');
 assert.equal(formatSelection([math(String.raw`{\mathrm{\mu}}\,m`)]).values.text,'μ m');
 assert.equal(formatSelection([math(String.raw`\mu m`)]).values.text,'μm');
 assert.equal(formatSelection([math(String.raw`\mu\quad\sigma`)]).values.text,'μ σ');
 assert.equal(formatSelection([math(String.raw`\mathrm{x}`)]).values.text,String.raw`\mathrm{x}`);
});
test('unsupported Greek formula structure falls back as a whole without losing scientific meaning',()=>{
 for(const tex of [String.raw`\frac{\mu}{\sigma}`,String.raw`\mu_0`,String.raw`\mu^{2}`,String.raw`\hat{\mu}`,String.raw`\mathbf{\mu}`,String.raw`\begin{equation*}\mu\end{equation*}`,String.raw`\mu+\unknown`,String.raw`\mug`,String.raw`\constructor`,String.raw`\text{\mu}`,String.raw`{\mu`,String.raw`\mu}`,String.raw`\mu%comment`,String.raw`\def\mu{x}\mu`]){
  assert.equal(formatSelection([math(tex)]).values.text,tex,tex);
 }
});
test('code examples and explicitly selected formula source remain literal TeX',()=>{
 const tex=String.raw`\mu`,source=formatSelection([{kind:'math',tex,display:false,preserveWhitespace:true}]);
 assert.equal(source.values.text,tex);
 assert.equal(formatSelection([text(tex)]).values.text,tex);
 assert.equal(formatSelection([el('code',[text(tex)])]).values.text,tex);
 assert.equal(formatSelection([el('pre',[math(tex)])]).values.text,tex);
});
test('formatted fragments retain paragraph boundaries, heading level, emphasis and links',()=>{
 const result=formatSelection([el('h2',[text('Heading')]),el('p',[text('A '),el('strong',[text('bold')]),text(' and '),el('em',[text('italic')]),text(' '),el('a',[text('link')],{href:'https://example.test/a'})])]);
 assert.equal(result.values.markdown,'## Heading\n\nA **bold** and *italic* [link](https://example.test/a)');
 assert.equal(result.values.latex,'\\subsection*{Heading}\n\nA \\textbf{bold} and \\emph{italic} \\href{https://example.test/a}{link}');
 assert.equal(result.values.text,'Heading\n\nA bold and italic link (https://example.test/a)');
});
test('original inline and block TeX is preserved without inferring visible glyphs',()=>{
 const tex=String.raw`\frac{x_1}{y^2}+\alpha`,result=formatSelection([el('p',[text('Value '),math(tex),text('.')]),math(tex,true)]);
 assert.equal(result.values.markdown,'Value $'+tex+'$.\n\n$$\n'+tex+'\n$$');
 assert.equal(result.values.latex,'Value \\('+tex+'\\).\n\n\\[\n'+tex+'\n\\]');
 assert.equal(result.values.text,'Value '+tex+'.\n\n'+tex);
 assert.equal(unwrappedMath(String.raw`\(x_1\)`),'x_1');
});
test('existing standalone math environments are not nested in another math environment',()=>{
 for(const env of ['equation*','align','align*','flalign*','alignat','gather','multline']){
  const tex='\\begin{'+env+'}\nx_1&=y^2\n\\end{'+env+'}',result=formatSelection([math(tex,true)]);
  assert.equal(result.values.latex,tex);assert(result.values.markdown.startsWith('$$\n'));
 }
 const inner=String.raw`\begin{aligned}x&=1\end{aligned}`;assert.equal(formatSelection([math(inner,true)]).values.latex,'\\[\n'+inner+'\n\\]');
});
test('ordinary text escapes LaTeX control characters and Markdown punctuation',()=>{
 const source='50% & # _ $ \\ { } ~ ^ < >';
 assert.equal(escapeLatex(source),String.raw`50\% \& \# \_ \$ \textbackslash{} \{ \} \textasciitilde{} \textasciicircum{} \textless{} \textgreater{}`);
 assert.equal(formatSelection([text(source)]).values.text,source);
 assert(formatSelection([text('$5 and x_y')]).values.markdown.includes('\\$5 and x\\_y'));
});
test('normal HTML subscripts and superscripts do not silently flatten into base text',()=>{
 const result=formatSelection([el('p',[text('H'),el('sub',[text('2')]),text('O and x'),el('sup',[text('2')])])]);
 assert.equal(result.values.markdown,'H<sub>2</sub>O and x<sup>2</sup>');
 assert.equal(result.values.latex,'H\\textsubscript{2}O and x\\textsuperscript{2}');
 assert.equal(result.values.text,'H_{2}O and x^{2}');
});
test('selected ordered list entries keep their source numbering and nested lists',()=>{
 const result=formatSelection([el('ol',[el('li',[text('selected')]),el('li',[text('next'),el('ul',[el('li',[text('nested')])])])],{start:4})]);
 assert(result.values.markdown.startsWith('4. selected\n5. next'));assert(result.values.markdown.includes('- nested'));
 assert(result.values.latex.includes('\\setcounter{enumi}{3}'));assert(result.values.latex.includes('\\begin{itemize}'));
});
test('complete simple tables retain columns without inventing an extra selected header row',()=>{
 const result=formatSelection([el('table',[el('tr',[el('th',[text('A')]),el('th',[text('B')])]),el('tr',[el('td',[text('1')]),el('td',[math('x_1')])])],{complete:true,simple:true})]);
 assert.equal(result.values.markdown,'| A | B |\n| --- | --- |\n| 1 | $x_1$ |');
 assert(result.values.latex.includes('\\begin{tabular}{ll}'));assert(result.values.latex.includes('1 & \\(x_1\\)'));
 assert.equal(result.values.text,'A\tB\n1\tx_1');assert.deepEqual(result.warnings.markdown,[]);
});
test('incomplete or merged tables degrade explicitly without manufacturing cells',()=>{
 const table=el('table',[el('tr',[el('td',[text('partial')])])],{complete:false,simple:false}),result=formatSelection([table]);
 assert.equal(result.values.markdown,'partial');assert(!result.values.latex.includes('tabular'));assert.deepEqual(result.warnings.text,['table-simplified']);
 const pipe=el('table',[el('tr',[el('td',[math(String.raw`\left|x\right|`)])])],{complete:true,simple:true});
 const downgraded=formatSelection([pipe]);assert(downgraded.values.markdown.includes(String.raw`\left|x\right|`));assert(downgraded.warnings.markdown.includes('table-simplified'));
});
test('images use descriptions and links and report that the image content was not copied',()=>{
 const result=formatSelection([{kind:'image',alt:'Figure 1',href:'https://example.test/a.png'}]);
 assert.equal(result.values.markdown,'[Figure 1](https://example.test/a.png)');assert.deepEqual(result.warnings.text,['image-link']);
});
test('code and multi-line TeX retain their line structure',()=>{
 const source='line 1\n\nline 2',result=formatSelection([el('pre',[text(source)])]);
 assert(result.values.markdown.includes(source));assert(result.values.latex.includes(source));assert.equal(result.values.text,source);
 const tex=String.raw`x_1+
y^2`,table=el('table',[el('tr',[el('th',[math(tex)])])],{complete:true,simple:true}),resultTable=formatSelection([table]);
 assert(resultTable.values.markdown.includes(tex));assert(resultTable.warnings.markdown.includes('table-simplified'));
});

test('copied math removes ignored source padding in all three formats',()=>{
 const source=String.raw`\(\mathrm { g _ { m 2 } ^ { \mathrm { ~ R ~ } } }\)`,expected=String.raw`\mathrm{g_{m2}^{\mathrm{~R~}}}`;
 const result=formatSelection([math(source)]);
 assert.equal(result.values.markdown,'$'+expected+'$');assert.equal(result.values.latex,'\\('+expected+'\\)');assert.equal(result.values.text,expected);
});
test('text arguments, explicit spacing and command boundaries retain their meaning',()=>{
 assert.equal(compactMathSource(String.raw`\text { signal gain } + \frac { 1 } { 2 }`),String.raw`\text{ signal gain }+\frac{1}{2}`);
 assert.equal(compactMathSource(String.raw`\operatorname { arg max } _ { x } f ( x )`),String.raw`\operatorname{ arg max }_{x}f(x)`);
 assert.equal(compactMathSource(String.raw`\alpha x + \sin \theta`),String.raw`\alpha x+\sin\theta`);
 assert.equal(compactMathSource(String.raw`a \, b \quad c \ d ~ e`),String.raw`a\,b\quad c\ d~e`);
});
test('opaque or stateful TeX and unsupported commands keep their original source',()=>{
 for(const source of [String.raw`\newcommand {\foo} { a b } \foo`,String.raw`\verb|a b|`,String.raw`\unrecognized { a b } + x _ { 1 }`,'a % keep comment\n b'])assert.equal(compactMathSource(source),source);
 const text=String.raw`\text {two  words \{kept\}} + x _ { 1 }`;
 assert.equal(compactMathSource(text),String.raw`\text{two  words \{kept\}}+x_{1}`);
});
test('display environments retain row breaks without adding nested environments',()=>{
 const source=String.raw`\begin {align*}
x _ { 1 } &= \frac { a } { b } \\
y &= z
\end {align*}`,expected=String.raw`\begin{align*}
x_{1}&=\frac{a}{b}\\
y&=z
\end{align*}`;
 assert.equal(formatSelection([math(source,true)]).values.latex,expected);
});

test('an explicitly selected original-source viewer keeps source whitespace',()=>{
 const source=String.raw`\begin{equation*} a _ { 1 } = b ^ { 2 } \end{equation*}`;
 const result=formatSelection([{kind:'math',tex:source,display:true,preserveWhitespace:true}]);
 assert.equal(result.values.latex,source);assert.equal(result.values.text,source);assert.equal(result.values.markdown,'$$\n'+source+'\n$$');
});
