import assert from 'node:assert/strict';
import {test} from 'node:test';
import {loadReaderLayout,normalizeReaderLayout,readerLayoutDefaults,readerLayoutPreference} from '../src/readerLayout.ts';

test('reader layout defaults include a narrower visible publication sidebar',()=>{
 assert.deepEqual(normalizeReaderLayout(undefined),{pageWidth:2000,tocWidth:200,infoWidth:220,infoOpen:true,fontScale:100});
 for(const value of [null,[],false,'bad'])assert.deepEqual(normalizeReaderLayout(value),readerLayoutDefaults);
});
test('layout widths stay within supported bounds and follow slider steps',()=>{
 assert.deepEqual(normalizeReaderLayout({pageWidth:9999,tocWidth:-2,infoWidth:195,infoOpen:false}),{pageWidth:2200,tocWidth:180,infoWidth:200,infoOpen:false,fontScale:100});
 assert.deepEqual(normalizeReaderLayout({pageWidth:1941,tocWidth:999,infoWidth:-1}),{pageWidth:1960,tocWidth:280,infoWidth:180,infoOpen:true,fontScale:100});
});
test('corrupt or injected preference values cannot enter layout styles',()=>{
 assert.deepEqual(normalizeReaderLayout({pageWidth:'2000px;display:none',tocWidth:NaN,infoWidth:Infinity,infoOpen:'false',extra:'ignored'}),readerLayoutDefaults);
 assert.deepEqual(normalizeReaderLayout({infoOpen:false}),{...readerLayoutDefaults,infoOpen:false});
});
test('stored layouts restore and inaccessible or invalid browser storage uses defaults',()=>{
 Object.assign(globalThis,{localStorage:{getItem:(key:string)=>{assert.equal(key,readerLayoutPreference);return JSON.stringify({pageWidth:1800,tocWidth:240,infoWidth:200,infoOpen:false});}}});
 assert.deepEqual(loadReaderLayout(),{pageWidth:1800,tocWidth:240,infoWidth:200,infoOpen:false,fontScale:100});
 Object.assign(globalThis,{localStorage:{getItem:()=>'{invalid'}});assert.deepEqual(loadReaderLayout(),readerLayoutDefaults);
 Object.assign(globalThis,{localStorage:{getItem:()=>{throw Error('blocked');}}});assert.deepEqual(loadReaderLayout(),readerLayoutDefaults);
});
test('font scaling upgrades old preferences and validates persisted values',()=>{
 assert.equal(normalizeReaderLayout({fontScale:999}).fontScale,150);
 assert.equal(normalizeReaderLayout({fontScale:0}).fontScale,80);
 assert.equal(normalizeReaderLayout({fontScale:123}).fontScale,125);
 for(const fontScale of ['150%;display:none',NaN,Infinity,null])assert.equal(normalizeReaderLayout({fontScale}).fontScale,100);
 Object.assign(globalThis,{localStorage:{getItem:()=>JSON.stringify({pageWidth:1800,fontScale:130})}});
 assert.deepEqual(loadReaderLayout(),{...readerLayoutDefaults,pageWidth:1800,fontScale:130});
});
