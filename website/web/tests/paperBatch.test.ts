import assert from 'node:assert/strict';
import {test} from 'node:test';
import {loadPapers} from '../src/paperBatch.ts';
import {defaultFilenameTemplate,renderFilename,downloadFilenames,toggleFilenameField,filenameTemplateError} from '../src/downloadNames.ts';

test('metadata reads are bounded, ordered, partial-failure aware and never call content/download routes',async()=>{
 let active=0,maximum=0;const paths:string[]=[];const value=await loadPapers(['3','1','2','4','5'],async path=>{paths.push(path);active++;maximum=Math.max(maximum,active);await new Promise(r=>setTimeout(r,path.endsWith('3')?25:2));active--;if(path.endsWith('2'))throw Error('Unavailable');return {paper:{number:path.split('/').pop(),record:{articleTitle:'Title'}}};});
 assert(maximum<=3);assert.deepEqual(value.items.map(p=>p.number),['3','1','4','5']);assert.deepEqual(value.failures,[{number:'2',message:'Unavailable'}]);assert(paths.every(p=>/^\/api\/papers\/\d+$/.test(p)));
});
test('templates honor field order, optional curated abbreviations and exact venue identities',()=>{
 const jssc={number:'123',title:'A--B Converter',year:2025,kind:'Journals',venue:'4'};assert.equal(renderFilename(defaultFilenameTemplate,jssc),'2025_JSSC_123_A--B Converter.pdf');assert.equal(renderFilename('{title} - [{abbr}] - {year}',jssc),'A--B Converter - [JSSC] - 2025.pdf');
 assert.equal(renderFilename('{id}__{title}',jssc),'123__A--B Converter.pdf');
 const outside={...jssc,venue:'999',publication:'JSSC similar name'};assert.equal(renderFilename('{year}_{abbr}_{id}',outside),'2025_123.pdf');assert.equal(renderFilename('[{abbr}] {year} - {title}',outside),'2025 - A--B Converter.pdf');assert.equal(renderFilename('{abbr}',outside),'123.pdf');
 assert.equal(renderFilename('{abbr}_{id}',{...jssc,kind:'Conferences',venue:'edition',venue_series:['1000708']}),'ISSCC_123.pdf');assert.equal(renderFilename('{id}',{...jssc,number:'000123'}),'000123.pdf');assert(filenameTemplateError('{author}'));assert(filenameTemplateError('{id'));assert.equal(filenameTemplateError('{ID}_{title}'),'');assert.equal(toggleFilenameField('{year}_{abbr}_{id}','abbr',false),'{year}_{id}');
});
test('download names cannot escape a directory or collide after UTF-8 truncation and case folding',()=>{
 const rows=[{number:'1',title:'Same'},{number:'2',title:'same'},{number:'3',title:'中'.repeat(200)},{number:'4',title:'中'.repeat(200)}];const names=downloadFilenames('{title}',rows);assert.equal(new Set(names.map(p=>p.filename.toLowerCase())).size,4);assert(names[1].filename.includes('[2]'));assert(names[3].filename.includes('[4]'));assert(names.every(p=>new TextEncoder().encode(p.filename).length<=240));assert.equal(renderFilename('{title}',{number:'1',title:'CON'}),'_CON.pdf');assert(!/[\\/:*?"<>|]/.test(renderFilename('{title}',{number:'2',title:'../A/B:C?\\D\n'})));assert.equal(renderFilename('{id}.pdf',{number:'5',title:''}),'5.pdf');
});
