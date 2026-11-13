import assert from 'node:assert/strict';
import {test} from 'node:test';
import katex from 'katex';
import {documentMathForDisplay} from '../src/documentMath.ts';
test('repeated equation numbers from PDF exports do not break KaTeX',()=>{
 assert.equal(documentMathForDisplay(String.raw`R_e(t)=x \tag {9}\tag{9}`),String.raw`R_e(t)=x \tag {9}`);
 assert.equal(documentMathForDisplay(String.raw`x \tag{1} \tag{1} \tag{1}`),String.raw`x \tag{1}`);
});
test('equation content and conflicting or distinct tags are preserved',()=>{
 for(const tex of [String.raw`x^2+\lambda \tag{9}`,String.raw`x \tag{9}\tag{10}`,String.raw`x \tag{a} + y \tag{a}`])assert.equal(documentMathForDisplay(tex),tex);
});
test('unbraced IEEE sum operators render with their original limits and equation environment',()=>{
 const tex=String.raw`\begin{equation*}\phi(x,y)=\mathop \sum \limits_{k_x=-N_x}^{N_x}\mathop \sum \limits_{k_y=-N_y}^{N_y}\psi_{k_x,k_y}e^{i(k_xr_x+k_yr_y)}\end{equation*}`;
 const expected=String.raw`\begin{equation*}\phi(x,y)=\mathop {\sum} \limits_{k_x=-N_x}^{N_x}\mathop {\sum} \limits_{k_y=-N_y}^{N_y}\psi_{k_x,k_y}e^{i(k_xr_x+k_yr_y)}\end{equation*}`;
 assert.throws(()=>katex.renderToString(tex,{displayMode:true,throwOnError:true}),/mathop/);
 const normalized=documentMathForDisplay(tex);assert.equal(normalized,expected);
 const rendered=katex.renderToString(normalized,{displayMode:true,throwOnError:true,output:'mathml'});
 assert.equal((rendered.match(/<munderover>/g)||[]).length,2);assert.equal((rendered.match(/∑/g)||[]).length,2);
 assert.equal(documentMathForDisplay(normalized),normalized);
});
test('inline sums keep explicit side-script placement and token boundaries',()=>{
 const tex=String.raw`R(s^t)=\mathop\sum\nolimits_{k=0}^T\gamma^k r(s^{t+k})`,expected=String.raw`R(s^t)=\mathop{\sum}\nolimits_{k=0}^T\gamma^k r(s^{t+k})`;
 assert.equal(documentMathForDisplay(tex),expected);
 const rendered=katex.renderToString(documentMathForDisplay(tex),{throwOnError:true,output:'mathml'});
 assert(rendered.includes('<msubsup>'));assert(!rendered.includes('<munderover>'));
 for(const unchanged of [String.raw`\mathop{\sum}_{k=0}^n`,String.raw`\mathop \summation`,String.raw`\mathoperator \sum`,String.raw`\\mathop \sum`,String.raw`\mathop \prod`])assert.equal(documentMathForDisplay(unchanged),unchanged);
});
test('comments, text arguments, verbatim and macro definitions retain their original source',()=>{
 for(const unchanged of [String.raw`\text{literal \mathop \sum}`,String.raw`\text{nested {literal \mathop \sum}}`,String.raw`\operatorname{\mathop \sum}`,String.raw`\verb|\mathop \sum|`,String.raw`\newcommand{\foo}{\mathop \sum}`,String.raw`a % \mathop \sum`])assert.equal(documentMathForDisplay(unchanged),unchanged);
 const tex='% \\mathop \\sum\n\\mathop \n\\sum_{k=0}^n';
 assert.equal(documentMathForDisplay(tex),'% \\mathop \\sum\n\\mathop \n{\\sum}_{k=0}^n');
});
test('11741266 slanted fractions retain box shifts and render without unknown commands',()=>{
 const tex=String.raw`\begin{equation*}
 N{{u}_d} = \frac{{\left( {{\raise0.7ex\hbox{$f$} \!\mathord{\left/ {\vphantom {f 8}}\right.} \!\lower0.7ex\hbox{$8$}}} \right)R{{e}_d}Pr}}{{1.07 + 12.7{{{\left( {{\raise0.7ex\hbox{$f$} \!\mathord{\left/ {\vphantom {f 8}}\right.} \!\lower0.7ex\hbox{$8$}}} \right)}}^{0.5}}\left( {P{{r}^{0.66}} - 1} \right)}}\ {{\left( {\frac{{{{\mu }_b}}}{{{{\mu }_w}}}} \right)}^n}
\end{equation*}`;
 assert.throws(()=>katex.renderToString(tex,{displayMode:true,throwOnError:true}),/Undefined control sequence: \\raise/);
 const normalized=documentMathForDisplay(tex);
 assert.equal(normalized,tex.replaceAll(String.raw`\raise0.7ex\hbox`,String.raw`\raisebox{0.7ex}`).replaceAll(String.raw`\lower0.7ex\hbox`,String.raw`\raisebox{-0.7ex}`));
 const rendered=katex.renderToString(normalized,{displayMode:true,throwOnError:true,output:'mathml'});
 assert.equal((rendered.match(/voffset="0.7ex"/g)||[]).length,2);
 assert.equal((rendered.match(/voffset="-0.7ex"/g)||[]).length,2);
 assert(!rendered.includes('mathcolor'));
 assert.equal(documentMathForDisplay(normalized),normalized);
});
test('box shifts preserve nested math, signs, spacing and surrounding display adaptations',()=>{
 const tex=String.raw`\mathop\sum_i \raise -.5 ex \hbox{$x_{i}$} + \lower -2pt\hbox{a {b}} + \raise+1.2em\hbox{$\mu$}`;
 const expected=String.raw`\mathop{\sum}_i \raisebox{-.5ex}{$x_{i}$} + \raisebox{2pt}{a {b}} + \raisebox{1.2em}{$\mu$}`;
 assert.equal(documentMathForDisplay(tex),expected);
 assert.doesNotThrow(()=>katex.renderToString(expected,{throwOnError:true}));
});
test('box adaptation leaves comments, text, macros, incomplete boxes and unsupported syntax alone',()=>{
 for(const tex of [String.raw`% \raise0.7ex\hbox{$f$}`,String.raw`\text{\lower0.7ex\hbox{$8$}}`,String.raw`\\raise0.7ex\hbox{$f$}`,String.raw`\def\foo{\raise0.7ex\hbox{$f$}}`,String.raw`\raise\height\hbox{$f$}`,String.raw`\raise0.7ex\vbox{$f$}`,String.raw`\raise0.7ex\hbox to 2em {$f$}`,String.raw`\raise0.7ex\hbox{$f$`,String.raw`\raise0.7ex\hbox{{$f$}`,String.raw`\raisebox{0.7ex}{$f$}`])assert.equal(documentMathForDisplay(tex),tex);
});
