import assert from 'node:assert/strict';
import {test} from 'node:test';
import {documentReferenceKey} from '../src/documentReferences.ts';

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
