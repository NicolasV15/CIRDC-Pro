import assert from 'node:assert/strict';
import {test} from 'node:test';
import {resultSelection,type ResultSelection} from '../src/resultSelection.ts';
const rows=(count:number,offset=0)=>Array.from({length:count},(_,i)=>({number:String(offset+i+1),title:'Paper '+(offset+i+1)}));
const blank:ResultSelection<{number:string;title:string}>={rows:[],selected:[]};
test('100 selected -> 25 results resets atomically, select all and cancel remain symmetric',()=>{
 let state=resultSelection(blank,{type:'replace',rows:rows(100)});
 for(const count of [100,25,50,100,25,1,37]){
  state=resultSelection(state,{type:'replace',rows:rows(count)});assert.equal(state.selected.length,0);
  for(let n=0;n<5;n++){state=resultSelection(state,{type:'all',checked:true});assert.equal(state.selected.length,count);state=resultSelection(state,{type:'all',checked:false});assert.equal(state.selected.length,0);}
 }
});
test('append does not auto-check, duplicates retain checks, all >100 can be cancelled',()=>{
 let state=resultSelection(blank,{type:'replace',rows:rows(100)});state=resultSelection(state,{type:'all',checked:true});
 state=resultSelection(state,{type:'append',rows:rows(100,100)});assert.equal(state.rows.length,200);assert.equal(state.selected.length,100);
 state=resultSelection(state,{type:'all',checked:true});assert.equal(state.selected.length,200);
 state=resultSelection(state,{type:'select',numbers:['150'],checked:false});assert.equal(state.selected.length,199);
 state=resultSelection(state,{type:'all',checked:false});assert.equal(state.selected.length,0);
 state=resultSelection(state,{type:'select',numbers:['200','1','offscreen'],checked:true});assert.deepEqual(state.selected,['1','200']);
 state=resultSelection(state,{type:'append',rows:rows(1,199)});assert.equal(state.rows.length,200);assert.deepEqual(state.selected,['1','200']);
 assert.deepEqual(resultSelection(state,{type:'reset'}),blank);
});
test('randomized operation sequences never retain off-screen IDs or fail a full clear',()=>{
 let seed=12345,state=blank;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed;};
 for(let i=0;i<2000;i++){
  const op=rand()%5;
  if(op===0)state=resultSelection(state,{type:'replace',rows:rows(rand()%220,rand()%20)});
  if(op===1)state=resultSelection(state,{type:'append',rows:rows(rand()%60,rand()%300)});
  if(op===2)state=resultSelection(state,{type:'select',numbers:[String(rand()%360)],checked:!!(rand()%2)});
  if(op===3)state=resultSelection(state,{type:'all',checked:!!(rand()%2)});
  if(op===4)state=resultSelection(state,{type:'reset'});
  const visible=new Set(state.rows.map(row=>row.number));assert.equal(visible.size,state.rows.length);assert.equal(new Set(state.selected).size,state.selected.length);assert(state.selected.every(id=>visible.has(id)));
  assert.equal(resultSelection(state,{type:'all',checked:false}).selected.length,0);
 }
});
