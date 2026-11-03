import assert from 'node:assert/strict';
import {test} from 'node:test';
import {citationCount,citationGroupState,citationItemKey,citationsPending,initialCitationGroup,showCitationGroups,mergeCitationItems,mergeCitationPage,validateCitationPage,type CitationGroup,type CitationsPage,type PaperCitation} from '../src/paperCitationData.ts';
import {referenceLink} from '../src/paperReferenceData.ts';
const item=(group:CitationGroup,order:number):PaperCitation=>({group,order,label:String(order),source_id:'',text:'A citation',title:'Title',target_number:'9007199254740995',doi:null,target_kind:'paper',target_url:null});
const page=(group:CitationGroup='ieee',extra:Partial<CitationsPage>={}):CitationsPage=>({number:'123',state:'complete',version:'v1',group,total:350,expected_total:350,counts:{ieee:350,nonIeee:350,total:700},stored_counts:{ieee:350,nonIeee:350,total:700},group_states:{ieee:'complete',nonIeee:'complete'},source_presence:'present',empty_reason:null,checked_at:'2026-10-20T00:00:00Z',last_attempt_at:'2026-10-20T00:00:00Z',next_check_at:'2026-10-27T00:00:00Z',stale:true,error:null,offset:0,limit:50,next_offset:50,items:[item(group,1)],...extra});
test('citation identities preserve independent group order spaces',()=>{
 assert.notEqual(citationItemKey(item('ieee',1)),citationItemKey(item('nonIeee',1)));
 const combined=mergeCitationItems([item('ieee',1)],[item('nonIeee',1),item('ieee',2)]);
 assert.deepEqual(combined.map(citationItemKey),['ieee:1','ieee:2','nonIeee:1']);
 assert.equal(referenceLink(combined[0])?.href,'/papers/9007199254740995');
});
test('counts stay independent and unknown or failed attempts never become zero',()=>{
 const split=page('ieee',{state:'partial',counts:{ieee:0,nonIeee:null,total:null},group_states:{ieee:'complete',nonIeee:'failed'},version:null,checked_at:null});
 assert.equal(citationCount(split,'ieee'),0);assert.equal(citationCount(split,'nonIeee'),undefined);assert.equal(citationGroupState(split,'nonIeee'),'failed');
 for(const state of ['missing','queued','fetching','failed','blocked'])assert.equal(citationCount(page('ieee',{state,group_states:{ieee:state,nonIeee:state},counts:{ieee:0,nonIeee:0,total:0},version:null,checked_at:null}),'ieee'),undefined,state);
 assert.equal(citationCount(page('ieee',{source_presence:'absent',counts:{ieee:0,nonIeee:0,total:0}}),'ieee'),undefined);
});
test('paging pins group, paper, version and immutable snapshot totals',()=>{
 const first=page(),second=page('ieee',{items:[item('ieee',51)],offset:50,next_offset:100});
 const merged=mergeCitationPage(first,second,true);assert.equal(merged.next_offset,100);assert.deepEqual(merged.items.map(x=>x.order),[1,51]);
 const polled=mergeCitationPage(merged,page('ieee',{state:'fetching'}));assert.equal(polled.next_offset,100);assert.equal(polled.items.length,2);
 for(const change of [{group:'nonIeee' as const},{version:'v2'},{number:'456'},{total:351}])assert.throws(()=>mergeCitationPage(first,{...second,...change},true),/snapshot/);
 assert.deepEqual(mergeCitationPage(first,page('ieee',{version:'v2',items:[]})).items,[]);
});
test('a failed refresh preserves old rows, source counts and their original check time',()=>{
 const first=page();
 const failed=mergeCitationPage(first,page('ieee',{state:'failed',version:null,items:[],total:0,counts:{ieee:null,nonIeee:null,total:null},checked_at:null,last_attempt_at:'2026-11-01T00:00:00Z',error:'access_restricted'}));
 assert.equal(failed.version,'v1');assert.equal(failed.items.length,1);assert.equal(failed.checked_at,first.checked_at);assert.equal(failed.counts.ieee,350);assert.equal(failed.error,'access_restricted');assert.equal(failed.last_attempt_at,'2026-11-01T00:00:00Z');
});
test('a newly successful version replaces confirmed empty results without keeping old pagination',()=>{
 const empty=page('nonIeee',{version:'v0',total:0,counts:{ieee:0,nonIeee:0,total:0},items:[],next_offset:null,empty_reason:'zero_count'});
 const next=mergeCitationPage(empty,page('nonIeee',{version:'v1'}));assert.equal(next.items.length,1);assert.equal(next.next_offset,50);assert.equal(next.version,'v1');
});
test('pages cannot mix group rows or accept unversioned items',()=>{
 validateCitationPage(page(),'123','ieee');
 for(const bad of [page('nonIeee'),page('ieee',{items:[item('nonIeee',1)]}),page('ieee',{version:null}),page('ieee',{items:[item('ieee',0)]})])assert.throws(()=>validateCitationPage(bad,'123','ieee'),/snapshot/);
});
test('polling includes pending groups and stops on all terminal states',()=>{
 assert.equal(citationsPending(page('ieee',{state:'partial',group_states:{ieee:'complete',nonIeee:'fetching'}})),true);
 for(const state of ['queued','fetching'])assert.equal(citationsPending(page('ieee',{state})),true);
 for(const state of ['complete','failed','blocked','no_data','unavailable'])assert.equal(citationsPending(page('ieee',{state})),false,state);
});
test('the initial group prefers readable saved IEEE rows, otherwise saved non-IEEE rows',()=>{
 const nonIeee=page('nonIeee');
 assert.equal(initialCitationGroup({ieee:page(),nonIeee}),'ieee');
 assert.equal(initialCitationGroup({ieee:page('ieee',{items:[],total:0,counts:{ieee:0,nonIeee:350,total:350}}),nonIeee}),'nonIeee');
 assert.equal(initialCitationGroup({ieee:page('ieee',{items:[],total:0,state:'partial',group_states:{ieee:'failed',nonIeee:'complete'}}),nonIeee}),'nonIeee');
});
test('the initial group uses confirmed source counts only when neither group has rows',()=>{
 const ieee=page('ieee',{items:[],counts:{ieee:0,nonIeee:10,total:10}}),nonIeee=page('nonIeee',{items:[],counts:ieee.counts});
 assert.equal(initialCitationGroup({ieee,nonIeee}),'nonIeee');
 assert.equal(initialCitationGroup({ieee:{...ieee,counts:{ieee:3,nonIeee:10,total:13}},nonIeee}),'ieee');
 const unknown=page('ieee',{version:null,checked_at:null,items:[],state:'queued',counts:{ieee:null,nonIeee:null,total:null},group_states:{ieee:'queued',nonIeee:'queued'}});
 assert.equal(initialCitationGroup({ieee:unknown,nonIeee:{...unknown,group:'nonIeee'}}),undefined);
});
test('group controls appear only when both groups have citations',()=>{
 const empty=(group:CitationGroup)=>page(group,{items:[],total:0,counts:{ieee:0,nonIeee:0,total:0}});
 assert.equal(showCitationGroups({ieee:page(),nonIeee:page('nonIeee')}),true);
 assert.equal(showCitationGroups({ieee:page(),nonIeee:empty('nonIeee')}),false);
 assert.equal(showCitationGroups({ieee:empty('ieee'),nonIeee:page('nonIeee')}),false);
 assert.equal(showCitationGroups({ieee:empty('ieee'),nonIeee:empty('nonIeee')}),false);
 assert.equal(showCitationGroups({ieee:null,nonIeee:null}),false);
 const source={ieee:3,nonIeee:4,total:7};
 assert.equal(showCitationGroups({ieee:page('ieee',{items:[],counts:source}),nonIeee:page('nonIeee',{items:[],counts:source})}),true);
});
