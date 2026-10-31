import assert from 'node:assert/strict';
import {test} from 'node:test';
import {venueFamilies,orderVenueFamilies,venueNumbers} from '../src/venueFamilies.ts';
import {venueRanking} from '../src/venueRanking.ts';
import {venueProfiles,venueSources} from '../src/venueGuideData.ts';

test('every selected family has one profile, a research field and valid source references',()=>{
 const keys=venueFamilies.map(f=>f.key).sort();
 assert.deepEqual(Object.keys(venueRanking).sort(),keys);assert.deepEqual(Object.keys(venueProfiles).sort(),keys);
 for(const profile of Object.values(venueProfiles)){
  assert(profile.sources.length>0);
  for(const key of profile.sources)assert(new URL(venueSources[key].url).protocol==='https:');
  for(const field of ['position','focus','reading','boundary'] as const){assert(profile[field].zh.trim());assert(profile[field].en.trim());}
 }
});
test('historical titles stay within the matching display tier and follow current titles in that tier',()=>{
 const keys=venueFamilies.filter(f=>f.kind==='Journals').map(f=>f.key),before=[...keys];
 const sorted=orderVenueFamilies(venueFamilies.filter(f=>f.kind==='Journals')).map(f=>f.key);
 assert(sorted.indexOf('tcad')<sorted.indexOf('lssc'));assert(sorted.indexOf('proc-ieee')<sorted.indexOf('tcas-i'));
 assert.equal(venueRanking.tcas.tier,venueRanking['tcas-i'].tier);assert.equal(venueRanking['j-tcad'].tier,venueRanking.tcad.tier);
 assert.equal(sorted.at(-1),'tcas');assert(sorted.indexOf('tcad')<sorted.indexOf('j-tcad'));assert(sorted.indexOf('j-tcad')<sorted.indexOf('tcas-i'));
 assert.deepEqual(keys,before);
 const conferences=orderVenueFamilies(venueFamilies.filter(f=>f.kind==='Conferences')).map(f=>f.key);
 assert(conferences.indexOf('isscc')<conferences.indexOf('a-sscc'));assert(conferences.indexOf('isca')<conferences.indexOf('date'));
});
test('presentation order never changes the 25 source IDs or family selection semantics',()=>{
 const all=venueFamilies.map(f=>f.key).join(','),sorted=orderVenueFamilies(venueFamilies).map(f=>f.key).join(',');
 assert.deepEqual(venueNumbers(all).sort(),venueNumbers(sorted).sort());assert.equal(venueNumbers(all).length,25);
 assert.deepEqual(venueNumbers('tcad'),['43']);assert.deepEqual(venueNumbers('j-tcad'),['6414145']);
 assert.deepEqual(venueNumbers('tcas-i'),['8919','81']);assert.deepEqual(venueNumbers('vlsi'),['1000798','1000802']);
});
