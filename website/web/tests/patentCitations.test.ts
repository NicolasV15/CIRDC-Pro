import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import ts from 'typescript';
import {mergePatentCitationPage,patentCitationCount,patentCitationLabel,patentCitationLink,patentCitationsPending,patentPublicationNumber,patentSourceAbsent,validatePatentCitationPage,type PatentCitation,type PatentCitationsPage} from '../src/patentCitationData.ts';
const fixture:PatentCitationsPage=JSON.parse(fs.readFileSync(new URL('./fixtures/patentCitations.json',import.meta.url),'utf8'));
const page=(extra:Partial<PatentCitationsPage>={}):PatentCitationsPage=>({...fixture,items:[...fixture.items],...extra});
const item=(extra:Partial<PatentCitation>={}):PatentCitation=>({...fixture.items[0],...extra});
test('fixed patent fixture keeps source and stored counts separate',()=>{
 validatePatentCitationPage(fixture,fixture.number);assert.equal(fixture.total,2);assert.equal(patentCitationCount(fixture),3);
 assert.equal(patentCitationLink(fixture.items[0])?.href,'https://patents.google.com/patent/US1234567B2/en');
 assert.equal(patentCitationLink(fixture.items[1])?.href,'https://patents.google.com/?q=Synthetic+patent+citation');
 assert.equal(patentCitationLabel(item()),'[1]');assert.equal(patentCitationLabel(item({label:'(A)'})),'(A)');
});
test('patent links only use Google Patents and never use local IEEE identities',()=>{
 for(const target_url of ['/papers/1234567','javascript:alert(1)','https://patents.google.com.evil.test/patent/US1234567B2','https://evil.test/']){
  assert.equal(patentCitationLink(item({target_url}))?.href,'https://patents.google.com/patent/US1234567B2/en');
  const search=patentCitationLink(item({target_url,publication_number:'1234567',title:'A & B / C'}));
  assert.equal(search?.kind,'patent_search');assert.equal(search?.href,'https://patents.google.com/?q=A+%26+B+%2F+C');
 }
 assert.equal(patentPublicationNumber('us 1,234,567-b2'),'US1234567B2');
 for(const invalid of ['1234567','US1','US1234/../../papers/1','US1234B222','https://patents.google.com/patent/US1234567B2'])assert.equal(patentPublicationNumber(invalid),undefined);
 assert.equal(patentCitationLink(item({publication_number:null,title:null,text:'Fallback citation'}))?.href,'https://patents.google.com/?q=Fallback+citation');
 assert.equal(patentCitationLink(item({publication_number:null,title:null,text:''})),undefined);
});
test('unknown, publisher absence and explicit zero remain distinct',()=>{
 for(const state of ['missing','queued','fetching','failed','blocked','unavailable','no_data']){
  assert.equal(patentCitationCount(page({state,version:null,total:0,expected_total:null,source_presence:'unknown',checked_at:null,items:[]})),undefined,state);
  assert.equal(patentCitationCount(page({state,version:null,total:0,expected_total:0,source_presence:'unknown',checked_at:null,items:[]})),undefined,state);
 }
 const absent=page({state:'unavailable',source_presence:'absent',empty_reason:'section_absent',total:0,expected_total:null,items:[]});
 assert.equal(patentSourceAbsent(absent),true);assert.equal(patentCitationCount(absent),undefined);
 assert.equal(patentCitationCount(page({state:'no_data',total:0,expected_total:0,empty_reason:'zero_count',items:[]})),0);
 assert.equal(patentCitationCount(page({state:'complete',total:0,expected_total:0,items:[]})),0);
 assert.equal(patentCitationCount(page({expected_total:null})),undefined);
});
test('only queued and fetching patent states request polling',()=>{
 for(const state of ['missing','partial','complete','no_data','unavailable','blocked','failed','disabled'])assert.equal(patentCitationsPending(page({state})),false,state);
 for(const state of ['queued','fetching'])assert.equal(patentCitationsPending(page({state})),true);
 assert.equal(patentCitationsPending(null),false);
});
test('pagination pins paper, version and immutable stored and source totals',()=>{
 const first=page({total:52,expected_total:55,next_offset:50}),next=page({total:52,expected_total:55,offset:50,next_offset:null,items:[item({order:51}),item({order:52})]});
 const merged=mergePatentCitationPage(first,next,true);assert.deepEqual(merged.items.map(i=>i.order),[1,2,51,52]);assert.equal(merged.next_offset,null);
 for(const changed of [{number:'999'},{version:'22222222222222222222222222222222'},{version:null},{total:53},{expected_total:56}])assert.throws(()=>mergePatentCitationPage(first,{...next,...changed},true),/snapshot_mismatch/);
 assert.throws(()=>mergePatentCitationPage(first,{...first,total:53}),/snapshot_mismatch/);
 assert.throws(()=>mergePatentCitationPage(null,next,true),/snapshot_mismatch/);
});
test('status refresh preserves loaded pages and failed updates keep readable snapshots',()=>{
 const first=page(),loaded=mergePatentCitationPage(first,page({items:[item({order:2,text:'Updated entry'})]}));
 assert.equal(loaded.items.length,2);assert.equal(loaded.items[1].text,'Updated entry');
 for(const state of ['queued','fetching','blocked','failed','partial']){
  const retained=mergePatentCitationPage(first,page({state,version:null,total:0,expected_total:null,items:[],checked_at:null,last_attempt_at:'2026-11-02T00:00:00Z',error:'unavailable'}));
  assert.equal(retained.version,first.version);assert.equal(retained.checked_at,first.checked_at);assert.equal(retained.total,2);assert.deepEqual(retained.items,first.items);assert.equal(retained.state,state);assert.equal(retained.last_attempt_at,'2026-11-02T00:00:00Z');
 }
 const failedVersion=mergePatentCitationPage(first,page({state:'failed',version:'22222222222222222222222222222222',total:0,expected_total:null,items:[]}));assert.equal(failedVersion.version,first.version);assert.deepEqual(failedVersion.items,first.items);
 const zero=mergePatentCitationPage(first,page({version:'22222222222222222222222222222222',state:'no_data',total:0,expected_total:0,empty_reason:'zero_count',items:[]}));
 assert.equal(zero.items.length,0);assert.equal(patentCitationCount(zero),0);
});
test('malformed and cross-paper pages cannot enter a patent snapshot',()=>{
 for(const changed of [{number:'999'},{version:null},{total:-1},{expected_total:-1},{offset:-1},{limit:101},{next_offset:2},{items:[item({order:0})]},{items:[item(),item()]}])assert.throws(()=>validatePatentCitationPage(page(changed),fixture.number),/snapshot_mismatch/);
});
test('patent panel labels and source-state notices have English translations',async()=>{
 Object.assign(globalThis,{document:{documentElement:{lang:''},title:''},window:{addEventListener:()=>{}}});
 const {setLanguage,t}=await import('../src/i18n.ts');setLanguage('en');assert.equal(t('专利被引'),'Patent Citations');assert.equal(t('官网当前记录 0 条专利被引'),'IEEE Xplore currently lists 0 patent citations');assert.equal(t('官网当前记录 0 条专利被引。'),'IEEE Xplore currently lists 0 patent citations.');
 const source=ts.createSourceFile('PaperPatentCitations.tsx',fs.readFileSync(new URL('../src/PaperPatentCitations.tsx',import.meta.url),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),missing:string[]=[];
 function walk(node:ts.Node){if(ts.isStringLiteral(node)&&/[\u3400-\u9fff]/.test(node.text)&&/[\u3400-\u9fff]/.test(t(node.text)))missing.push(node.text);if(ts.isJsxText(node)&&/[\u3400-\u9fff]/.test(node.text))missing.push(node.text);ts.forEachChild(node,walk)}
 walk(source);assert.deepEqual(missing,[]);setLanguage('zh');assert.equal(t('Patent Citations'),'专利被引');
});
