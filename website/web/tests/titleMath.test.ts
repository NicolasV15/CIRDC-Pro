import assert from 'node:assert/strict';
import {test} from 'node:test';
import {titleParts} from '../src/titleMath.ts';

test('IEEE scientific titles retain text and adjacent superscripts',()=>{
 const title='A 0.4 mm$^{3}$ Neural-Recording System With $H_{\\infty}$ Control';
 assert.deepEqual(titleParts(title),[{type:'text',value:'A 0.4 mm'},{type:'math',value:'^{3}',raw:'$^{3}$'},{type:'text',value:' Neural-Recording System With '},{type:'math',value:'H_{\\infty}',raw:'$H_{\\infty}$'},{type:'text',value:' Control'}]);
});
test('explicit inline, display and XML math labels all remain title fragments',()=>{
 assert.deepEqual(titleParts('Gain \\(g_m\\) and \\[x^2\\] and $$f_T$$').filter(p=>p.type==='math').map(p=>p.value),['g_m','x^2','f_T']);
 assert.deepEqual(titleParts('<inline-formula><tex-math><![CDATA[x_1]]></tex-math></inline-formula>'),[{type:'math',value:'x_1',raw:'\\(x_1\\)'}]);
 assert.deepEqual(titleParts('<tex-math>$x$</tex-math>'),[{type:'math',value:'x',raw:'$x$'}]);
});
test('math comparisons and entity decoding do not strip mathematical content',()=>{
 assert.deepEqual(titleParts('RF &amp; $a<b>c$ &amp; $x &lt; y$'),[{type:'text',value:'RF & '},{type:'math',value:'a<b>c',raw:'$a<b>c$'},{type:'text',value:' & '},{type:'math',value:'x < y',raw:'$x < y$'}]);
 assert.deepEqual(titleParts('<b>Gain</b>&nbsp;$g_m$&#32;Converter'),[{type:'text',value:'Gain '},{type:'math',value:'g_m',raw:'$g_m$'},{type:'text',value:' Converter'}]);
});
test('escaped dollars and dollars inside braces cannot prematurely close math',()=>{
 assert.deepEqual(titleParts('Cost \\$5 and $\\text{\\$2}+x$').filter(p=>p.type==='math').map(p=>p.value),['\\text{\\$2}+x']);
 assert.equal(titleParts('Cost \\$5')[0].value,'Cost $5');
 assert.deepEqual(titleParts('$\\text{a$b}+x$'),[{type:'math',value:'\\text{a$b}+x',raw:'$\\text{a$b}+x$'}]);
});
test('currency, incomplete delimiters and plain titles remain readable',()=>{
 for(const title of ['Cost $5 and $10','A $broken title','A \\(broken title','Plain RF & AI','A <0.1% Converter With >95-dB SFDR'])assert.deepEqual(titleParts(title),[{type:'text',value:title}]);
 assert.deepEqual(titleParts(undefined),[]);assert.deepEqual(titleParts({title:'$x$'}),[]);assert.deepEqual(titleParts('  '),[]);
});
test('source markup is rendered as text while unsupported math is retained for fallback',()=>{
 assert.deepEqual(titleParts('<img src=x onerror=alert(1)>An $\\unknown{a}$ Circuit'),[{type:'text',value:'An '},{type:'math',value:'\\unknown{a}',raw:'$\\unknown{a}$'},{type:'text',value:' Circuit'}]);
});
