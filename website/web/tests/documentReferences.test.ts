import assert from 'node:assert/strict';
import {test} from 'node:test';
import {documentReferenceKey,contextualDocumentReferenceKey} from '../src/documentReferences.ts';

test('figure aliases keep full hierarchical numbers distinct',()=>{
 assert.equal(documentReferenceKey('Fig. 32.4.2'),'figure:32.4.2');
 assert.equal(documentReferenceKey('Figure 32.4.20'),'figure:32.4.20');
 assert.equal(documentReferenceKey('figure\u00a032.4.2'),'figure:32.4.2');
 assert.equal(documentReferenceKey('Figure 2 (a)'),'figure:2');
});
test('table labels include Roman numerals and supplementary identifiers',()=>{
 assert.equal(documentReferenceKey('TABLE IV'),'table:iv');
 assert.equal(documentReferenceKey('Tab. S2'),'table:s2');
 assert.equal(documentReferenceKey('Table A.1'),'table:a.1');
 assert.equal(documentReferenceKey('表 ２'),'table:2');
});
test('caption prefixes identify targets without turning prose or ranges into links',()=>{
 assert.equal(documentReferenceKey('Figure 2: Operating principle.',true),'figure:2');
 assert.equal(documentReferenceKey('Table I. Comparison with earlier designs.',true),'table:i');
 for(const text of ['Figure 2 shows the circuit','Figures 1 and 2','Table 1–3','Figure 2 and Table I','[7]','Not a figure'])assert.equal(documentReferenceKey(text),undefined,text);
});
test('number-only source links require an immediately adjacent figure or table prefix',()=>{
 assert.equal(contextualDocumentReferenceKey('1','As shown in Fig. '),'figure:1');
 assert.equal(contextualDocumentReferenceKey('2(a)','Figs. '),'figure:2');
 assert.equal(contextualDocumentReferenceKey('IV','Tables '),'table:iv');
 assert.equal(contextualDocumentReferenceKey('２','图 '),'figure:2');
 for(const prefix of ['Figure 1 has ','Figure of merit ','configuration ','Fig. 1 and unrelated ','[',''])assert.equal(contextualDocumentReferenceKey('2',prefix),undefined,prefix);
});
test('only explicit adjacent groups can inherit a figure number or reference kind',()=>{
 const part={key:'figure:5',subfigure:true};
 for(const connector of ['–\u200b',' and ',', and ',' to '])assert.equal(contextualDocumentReferenceKey('(c)',connector,part),'figure:5');
 assert.equal(contextualDocumentReferenceKey('6(b)',', ',part),'figure:6');
 assert.equal(contextualDocumentReferenceKey('II',' and ',{key:'table:i',subfigure:false}),'table:ii');
 assert.equal(contextualDocumentReferenceKey('(b)','–',{key:'figure:1',subfigure:false}),undefined);
 for(const connector of ['; ','\nSee also ',' and equation ',' shows '])assert.equal(contextualDocumentReferenceKey('(c)',connector,part),undefined,connector);
 assert.equal(contextualDocumentReferenceKey('7',' and ',part),'figure:7');
});
