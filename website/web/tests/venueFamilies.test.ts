import test from 'node:test';
import assert from 'node:assert/strict';
import {venueFamilies,venueNumbers,paperVenueTags,matchingVenueFamilies} from '../src/venueFamilies.ts';

test('25 publication IDs form exactly 22 disjoint families',()=>{
 assert.equal(venueFamilies.length,22);assert.equal(venueFamilies.filter(f=>f.kind==='Journals').length,9);
 const ids=venueFamilies.flatMap(f=>f.seriesIds);assert.equal(ids.length,25);assert.equal(new Set(ids).size,25);
 assert.equal(venueNumbers(venueFamilies.map(f=>f.key).join(',')).length,25);
 assert.equal(matchingVenueFamilies('SSCL')[0].key,'lssc');assert.equal(matchingVenueFamilies('ASSCC')[0].key,'a-sscc');
});
const tag=(venue:string,kind:string,publication='')=>paperVenueTags({venue,kind,publication});
test('current and old journals stay in one family; similarly named TCAD journals remain separate',()=>{
 assert.deepEqual(tag('81','Journals').map(t=>[t.family.key,t.old]),[['tcas-i',true]]);
 assert.deepEqual(tag('8919','Journals').map(t=>[t.family.key,t.old]),[['tcas-i',false]]);
 assert.equal(tag('82','Journals')[0].old,true);assert.equal(tag('8920','Journals')[0].old,false);
 assert.equal(tag('43','Journals')[0].family.key,'tcad');assert.equal(tag('6414145','Journals')[0].family.key,'j-tcad');
 assert.equal(tag('6414145','Journals')[0].old,true);assert.equal(tag('31','Journals')[0].old,true);
 assert.equal(tag('4','Early Access Articles','1966 IEEE Journal of Solid-State Circuits')[0].old,false);
});
test('conference families resolve through source IDs and edition names, never title resemblance alone',()=>{
 assert.equal(paperVenueTags({kind:'Conferences',venue:'edition',venue_series:['1000708'],publication:'ISSCC'})[0].label,'ISSCC');
 assert.deepEqual(tag('unknown','Conferences','2026 Symposium on VLSI Circuits'),[]);
 assert.deepEqual(tag('4','Conferences'),[]);
 assert.equal(tag('1000709','Conferences','2026 ESSCIRC')[0].old,true);
 assert.equal(tag('1000709','Conferences','2024 IEEE European Solid-State Electronics Research Conference (ESSERC)')[0].old,false);
 assert.equal(tag('1000709','Conferences','')[0].old,false);
 assert.equal(tag('1000802','Conferences','2026 IEEE/JSAP Symposium on VLSI Technology and Circuits')[0].old,false);
 assert.equal(tag('1000802','Conferences','1987 Symposium on VLSI Technology')[0].label,'VLSI-T');
 assert.equal(tag('1000798','Conferences','2021 Symposium on VLSI Circuits')[0].label,'VLSI-C');
 assert.equal(tag('1000802','Conferences','')[0].old,false);
});
