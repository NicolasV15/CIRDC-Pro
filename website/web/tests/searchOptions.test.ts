import {test} from 'node:test';
import assert from 'node:assert/strict';
import {changedSearchOptions} from '../src/searchOptions.ts';
const fields:[string,string][]=[['all','全部'],['title','标题'],['body','正文']];
const base={q:'',field:'all',sort:'relevance',view:'',k:'',terms:''};
const sortLabel=(sort:string)=>sort==='year'?'最新投稿':'相关度';
// Chinese source strings with placeholders filled, as the interface shows them in Chinese.
const t=(text:string,values:Record<string,string>={})=>text.replace(/\{(\w+)\}/g,(_,key)=>values[key]);
test('defaults produce no summary on either page',()=>{
 assert.deepEqual(changedSearchOptions(base,fields,'relevance',sortLabel,t),[]);
 assert.deepEqual(changedSearchOptions({...base,sort:'year'},fields,'year',sortLabel,t),[]);
 assert.deepEqual(changedSearchOptions({...base,field:''},fields,'relevance',sortLabel,t),[]);
});
test('each non-default choice is named once, in display order',()=>{
 assert.deepEqual(changedSearchOptions({...base,field:'body',sort:'year',terms:'exact'},fields,'relevance',sortLabel,t),['正文','最新投稿','仅原写法']);
 assert.deepEqual(changedSearchOptions({...base,sort:'relevance'},fields,'year',sortLabel,t),['相关度']);
});
test('the most-relevant view replaces the sort and names its size',()=>{
 assert.deepEqual(changedSearchOptions({...base,view:'top',sort:'year'},fields,'relevance',sortLabel,t),['最相关 · 前 20 篇']);
 assert.deepEqual(changedSearchOptions({...base,view:'top',k:'50'},fields,'relevance',sortLabel,t),['最相关 · 前 50 篇']);
});
