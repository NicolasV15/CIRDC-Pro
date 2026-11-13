import {test} from 'node:test';
import assert from 'node:assert/strict';
import {coverageDisplay,institutionalCoverage,type ResourceCoverage} from '../src/resourceCoverage.ts';
const metric=(numerator:number|null,status='ready'):ResourceCoverage=>({id:'documents',numerator,status});
test('coverage is a ratio of registered records to the whole database, not a raw file count',()=>{
 assert.equal(coverageDisplay(metric(188068),6625313,'en-US').rate,'2.84%');
 assert.equal(coverageDisplay(metric(188068),6625313,'zh-CN').count,188068);
 assert.equal(coverageDisplay(metric(0),100,'en-US').rate,'0.00%');
});
test('missing, partial or inconsistent counts remain unknown rather than becoming zero coverage',()=>{
 for(const value of [undefined,metric(null),metric(-1),metric(101),metric(50,'updating')])assert.equal(coverageDisplay(value,100,'en-US').rate,'—');
 assert.equal(coverageDisplay(metric(0),0,'en-US').rate,'—');
});

test('a provider scope overrides the whole-database denominator without falling back when unknown',()=>{
 const scoped={...metric(188068),denominator:190667};
 assert.equal(coverageDisplay(scoped,6630810,'en-US').rate,'98.64%');
 assert.equal(coverageDisplay(scoped,6630810,'en-US').denominator,190667);
 assert.equal(coverageDisplay({...scoped,denominator:null},6630810,'en-US').rate,'—');
 assert.equal(coverageDisplay({...scoped,denominator:100},6630810,'en-US').rate,'—');
});
test('confirmed institutional denials use the full denominator and retain small nonzero percentages',()=>{
 const all={...metric(199234),denominator:7350374,institution_not_licensed:225};
 assert.equal(coverageDisplay(all,1,'en-US').rate,'2.71%');
 assert.deepEqual(institutionalCoverage(all,1,'en-US'),{count:225,rate:'0.0031%'});
 assert.deepEqual(institutionalCoverage({...all,institution_not_licensed:0},1,'zh-CN'),{count:0,rate:'0.00%'});
 for(const value of [undefined,null,-1,1.5,7350374])assert.equal(institutionalCoverage({...all,institution_not_licensed:value},1,'en-US'),null);
 assert.equal(institutionalCoverage({...all,status:'unavailable'},1,'en-US'),null);
});
