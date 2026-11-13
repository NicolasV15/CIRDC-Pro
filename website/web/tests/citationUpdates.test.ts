import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createCitationUpdates} from '../src/citationUpdates.ts';

test('both mounted citation categories share one ensure and one explicit update',async()=>{
 const calls:any[]=[];const base='/api/papers/123';
 const updates=createCitationUpdates('123',async(path,method,data)=>{
  calls.push({path,method,data});if(method==='GET')return {state:'complete'};
  return {papers:{state:'queued',group:'ieee'},patents:{state:'queued',group:'patent'}};
 });
 await Promise.all([updates.fetcher(base+'/citations?group=ieee'),updates.fetcher(base+'/patent-citations')]);
 const values=await Promise.all([updates.fetcher(base+'/citations/ensure','POST',{}),updates.fetcher(base+'/patent-citations/ensure','POST',{})]);
 assert.equal(values[0].group,'ieee');assert.equal(values[1].group,'patent');
 assert.equal(calls.filter(c=>c.method==='POST').length,1);assert.deepEqual(calls[2].data,{refresh:false,include_patents:true});
 updates.beginUpdate();await Promise.all([updates.fetcher(base+'/citations/ensure','POST',{refresh:true}),updates.fetcher(base+'/patent-citations/ensure','POST',{refresh:true})]);
 assert.equal(calls.filter(c=>c.method==='POST').length,2);
 updates.beginUpdate();await updates.fetcher(base+'/citations/ensure','POST',{refresh:true});assert.equal(calls.filter(c=>c.method==='POST').length,3);
});

test('a disabled category keeps the enabled category usable without joint work',async()=>{
 const calls:any[]=[];const base='/api/papers/123';const updates=createCitationUpdates('123',async(path,method)=>{
  calls.push({path,method});return path.startsWith(base+'/citations')?{state:'disabled',group:path.includes('nonIeee')?'nonIeee':'ieee'}:{state:method==='POST'?'queued':'complete'};
 });
 await Promise.all([updates.fetcher(base+'/citations?group=ieee'),updates.fetcher(base+'/patent-citations')]);
 await updates.fetcher(base+'/citations?group=nonIeee');
 assert.equal((await updates.fetcher(base+'/patent-citations/ensure','POST',{})).state,'queued');
 assert.equal((await updates.fetcher(base+'/citations/ensure','POST',{})).group,'ieee');
 assert.equal(calls.filter(c=>c.method==='POST')[0].path,base+'/patent-citations/ensure');
});
