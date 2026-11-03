import assert from 'node:assert/strict';
import {test} from 'node:test';
import {titleParts} from '../src/titleMath.ts';
import {abstractParts,abstractPrefix,abstractUnits} from '../src/abstractMath.ts';

test('collapsed summaries keep formulas whole while shortening adjacent text',()=>{
 const parts=titleParts('Gain $\\frac{g_m}{2\\pi C}$ stays stable.',true);
 assert.deepEqual(abstractPrefix(parts,5),[{type:'text',value:'Gain '}]);
 assert.deepEqual(abstractPrefix(parts,6),parts.slice(0,2));
 assert.deepEqual(abstractPrefix(parts,9),[...parts.slice(0,2),{type:'text',value:' st'}]);
 assert.deepEqual(abstractPrefix(parts,abstractUnits(parts)),parts);
});

test('abstracts reuse explicit TeX while retaining HTML superscripts and subscripts',()=>{
 const parts=abstractParts('Area 0.43mm<sup xmlns:mml="http://www.w3.org/1998/Math/MathML">2</sup>; V<sub>out</sub>; <inline-formula><tex-math>$\\text {DR}_{\\text {speech}}$</tex-math></inline-formula>, $14.4~\\mu $W.');
 assert.deepEqual(parts.filter(part=>part.script),[{type:'text',value:'2',script:'sup'},{type:'text',value:'out',script:'sub'}]);
 assert.deepEqual(parts.filter(part=>part.type==='math').map(part=>part.value),['\\text {DR}_{\\text {speech}}','14.4~\\mu ']);
 assert.deepEqual(abstractPrefix(abstractParts('mm<sup>23</sup>'),3),[{type:'text',value:'mm'},{type:'text',value:'2',script:'sup'}]);
});

test('script markup encloses formulas without parsing HTML tags inside TeX',()=>{
 const parts=abstractParts('A<sup>$x_1$+2</sup> and $a<b>c$ then <sub>n</sub>.');
 assert.deepEqual(parts.filter(part=>part.script),[{type:'math',value:'x_1',raw:'$x_1$',script:'sup'},{type:'text',value:'+2',script:'sup'},{type:'text',value:'n',script:'sub'}]);
 assert(parts.some(part=>part.type==='math'&&part.value==='a<b>c'));
 assert(!abstractParts('<sup onclick="bad()">2</sup>').some(part=>part.value.includes('onclick')));
 assert.deepEqual(abstractParts('Cost \\$5 and incomplete $x'),[{type:'text',value:'Cost $5 and incomplete $x'}]);
});
test('summary fragments preserve source line breaks, unicode and XML math',()=>{
 const parts=titleParts('First line\n第二行😀 <tex-math><![CDATA[x_1]]></tex-math> &amp; text',true);
 assert.equal(parts[0].value,'First line\n第二行😀 ');
 assert.deepEqual(parts.find(p=>p.type==='math'),{type:'math',value:'x_1',raw:'\\(x_1\\)'});
 assert.equal(titleParts('A\n B')[0].value,'A B');
 const emoji=titleParts('😀 $x$');assert.equal(abstractUnits(emoji),3);
 assert.deepEqual(abstractPrefix(emoji,1),[{type:'text',value:'😀'}]);
});
