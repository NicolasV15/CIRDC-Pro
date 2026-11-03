import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {publicationAbbreviation,publicationLookupKey} from '../src/publicationAbbreviations.ts';
const table=JSON.parse(fs.readFileSync(new URL('../src/data/publication-venues.json',import.meta.url),'utf8')).map;
test('the supplied full mapping is preserved and matches edition normalization',()=>{
 assert.equal(Object.keys(table).length,15236);
 assert.equal(publicationLookupKey('2026 IEEE 39th International Conference on VLSI Design'),'international conference on vlsi design');
 assert.equal(publicationAbbreviation('2026 IEEE 39th International Conference on VLSI Design',table),'VLSID');
 assert.equal(publicationAbbreviation('2024 IEEE 67th International Midwest Symposium on Circuits and Systems (MWSCAS)',table),'MWSCAS');
 assert.equal(publicationAbbreviation('2026 IEEE International Conference on Communications',table),'ICC');
});
test('exact map entries precede light acronym and display fallbacks',()=>{
 assert.equal(publicationAbbreviation('Some Conference (ABC)',{'some conference (abc)':'MAPPED'}),'MAPPED');
 assert.equal(publicationAbbreviation('Some Conference (ABC)'),'ABC');
 assert.equal(publicationAbbreviation('IEEE Transactions on Circuits and Systems II: Express Briefs'),'IEEE TCAS-II');
 assert.equal(publicationAbbreviation('IEEE Transactions on Circuits and Systems I: Regular Papers'),'IEEE TCAS-I');
 assert.equal(publicationAbbreviation('Midwest Symposium on Circuits and Systems'),'MWSCAS');
 assert.equal(publicationAbbreviation('<b>IEEE Journal of Solid-State Circuits</b>'),'IEEE JSSC');
});
test('unknown and missing titles do not invent a badge or mutate the source',()=>{
 const title='A Completely Unmapped Publication';assert.equal(publicationAbbreviation(title,table),undefined);assert.equal(title,'A Completely Unmapped Publication');
 assert.equal(publicationAbbreviation(undefined,table),undefined);assert.equal(publicationAbbreviation('',table),undefined);
});
