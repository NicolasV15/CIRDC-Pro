import assert from 'node:assert/strict';
import {test} from 'node:test';
import {citationOrder,uniqueCitationOrder,mergeReferenceItems,mergeReferencePage,referenceLabel,referenceLink,referencesPending,shouldEnsureReferences,referenceCountKnown,type PaperReference,type ReferencesPage} from '../src/paperReferenceData.ts';

const item=(order:number,extra:Partial<PaperReference>={}):PaperReference=>({order,label:String(order),source_id:'ref'+order,text:'Full citation',title:'A paper',target_number:null,doi:null,target_kind:'scholar',target_url:'https://scholar.google.com/scholar?q=example',...extra});
const page=(version:string,items:PaperReference[],next_offset:number|null=50):ReferencesPage=>({number:'123',state:'complete',version,total:350,expected_total:350,checked_at:null,error:null,offset:0,limit:50,next_offset,items});

test('authoritative IEEE identifiers always link locally without converting them to numbers',()=>{
 const id='9007199254740995';
 assert.deepEqual(referenceLink(item(1,{target_number:id,target_url:'https://ieeexplore.ieee.org/document/'+id})),{href:'/papers/'+id,kind:'paper'});
 assert.deepEqual(referenceLink(item(1,{target_number:'99999999'})),{href:'/papers/99999999',kind:'paper'});
 assert.equal(referenceLabel(item(7,{label:'[7]'})),'[7]');
 assert.equal(referenceLabel(item(7,{label:''})),'[7]');
});
test('external entries use only the supplied Scholar search link',()=>{
 const href='https://scholar.google.com/scholar?q=10.1234%2Fexample';
 assert.deepEqual(referenceLink(item(1,{target_url:href})),{href,kind:'scholar'});
 const userInfo=new URL('https://scholar.google.com/scholar?q=x');userInfo.username='example';userInfo.password='example';
 for(const target_url of ['javascript:alert(1)','https://ieeexplore.ieee.org/document/1','https://scholar.google.com.evil.invalid/scholar?q=x','http://scholar.google.com/scholar?q=x','https://scholar.google.com/search?q=x',userInfo.href])assert.equal(referenceLink(item(1,{target_url})),undefined);
});
test('citation markers are explicit, positive and unambiguous',()=>{
 assert.equal(citationOrder('context_ref_7_1'),7);assert.equal(citationOrder('context_ref_301_2'),301);
 assert.equal(citationOrder('context_ref_1_'),1);assert.equal(citationOrder('context_ref_7_'),7);
 assert.equal(citationOrder('context_ref_56_1a1'),56);assert.equal(citationOrder('context_ref_25_2b'),25);assert.equal(citationOrder('context_ref_1_2a'),1);
 assert.equal(uniqueCitationOrder(['context_ref_7_1','context_ref_7_2']),7);
 assert.equal(uniqueCitationOrder(['context_ref_7_1','context_ref_8_1']),undefined);
 for(const marker of ['7','[7]','(7)','ref7','Figure 7','eq7','context_ref_0_1','context_ref_7_extra','context_ref_7_1_extra','context_ref_7_0a','context_ref_9007199254740995_1'])assert.equal(citationOrder(marker),undefined,marker);
});
test('ordered snapshots preserve repeated citations and merge only by source order',()=>{
 const repeated=item(1,{target_number:'456'}),second={...repeated,order:2,label:'2'};
 assert.equal(mergeReferenceItems([repeated],[second]).length,2);
 const first=page('v1',[repeated]),later={...page('v1',[second,item(301)]),offset:50,next_offset:100};
 const merged=mergeReferencePage(first,later,true);
 assert.deepEqual(merged.items.map(row=>row.order),[1,2,301]);assert.equal(merged.next_offset,100);
 const polled=mergeReferencePage(merged,{...page('v1',[repeated]),state:'fetching'});
 assert.equal(polled.items.length,3);assert.equal(polled.next_offset,100);assert.equal(polled.state,'fetching');
});
test('pagination refuses to mix versions and a new snapshot replaces old entries',()=>{
 const old=page('v1',[item(1)]);
 assert.throws(()=>mergeReferencePage(old,page('v2',[item(2)]),true),/snapshot/);
 assert.throws(()=>mergeReferencePage(old,{...page('v1',[item(2)]),total:351},true),/snapshot/);
 assert.deepEqual(mergeReferencePage(old,page('v2',[item(2)])).items.map(row=>row.order),[2]);
});
test('only queued and fetching reference jobs poll; terminal attempts are stable',()=>{
 for(const state of ['queued','fetching'])assert.equal(referencesPending(state),true);
 for(const state of ['complete','no_data','unavailable','partial','blocked','failed','disabled','missing'])assert.equal(referencesPending(state),false);
});
test('only the explicit legacy-availability flag permits a new unavailable reference check',()=>{
 const p={...page('v1',[]),state:'unavailable'};
 assert.equal(shouldEnsureReferences(p),false);
 assert.equal(shouldEnsureReferences({...p,needs_availability_check:false}),false);
 assert.equal(shouldEnsureReferences({...p,needs_availability_check:true}),true);
 for(const state of ['blocked','failed','no_data','complete'])assert.equal(shouldEnsureReferences({...p,state,needs_availability_check:true}),false,state);
 assert.equal(shouldEnsureReferences({...p,state:'missing'}),true);
});
test('unknown and absent reference sections do not show a false zero',()=>{
 for(const state of ['missing','queued','fetching','blocked','failed','unavailable'])assert.equal(referenceCountKnown({...page('',[]),state,total:0,version:null}),false,state);
 assert.equal(referenceCountKnown({...page('v1',[]),state:'complete',total:0}),true);
 assert.equal(referenceCountKnown({...page('v1',[]),state:'unavailable',source_presence:'absent',total:0}),false);
});
