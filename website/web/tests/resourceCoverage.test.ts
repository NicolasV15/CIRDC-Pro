import {test} from 'node:test';
import assert from 'node:assert/strict';
import {coverageDisplay,type ResourceCoverage} from '../src/resourceCoverage.ts';
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
