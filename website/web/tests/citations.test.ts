import assert from 'node:assert/strict';
import {test} from 'node:test';
import {buildCitations,citationText,type CitationRecord} from '../src/citations.ts';

const journal: CitationRecord={articleTitle:'An RF & AI Converter',articleContentType:'Journals',publicationTitle:'IEEE Journal of Solid-State Circuits',publicationYear:'2025',publicationDate:'Feb. 2025',volume:'60',issue:'2',startPage:'443',endPage:'455',doi:'10.1109/JSSC.2024.3408468',authors:[{firstName:'Yuefeng',lastName:'Cao',preferredName:'Yuefeng Cao'},{firstName:'Rui P.',lastName:'Martins',preferredName:'Rui P. Martins'}]};

test('journal exports preserve author order and canonical publication fields',()=>{
 const original=structuredClone(journal),result=buildCitations(journal,'10555121','2026-10-29');
 assert.equal(result.values.ieee,'Y. Cao and R. P. Martins, “An RF & AI Converter,” IEEE Journal of Solid-State Circuits, vol. 60, no. 2, pp. 443–455, Feb. 2025, doi: 10.1109/JSSC.2024.3408468.');
 assert.equal(result.values.gbt2025,'CAO Y, MARTINS R P. An RF & AI Converter[J]. IEEE Journal of Solid-State Circuits, 2025, 60(2): 443–455. DOI: 10.1109/JSSC.2024.3408468.');
 assert(result.values.bibtex.startsWith('@article{ieee10555121,'));assert(result.values.bibtex.includes('Cao, Yuefeng and Martins, Rui P.'));assert(result.values.bibtex.includes('pages = {443--455}'));assert(result.values.bibtex.includes('RF \\& AI'));assert.deepEqual(result.missing,[]);assert.deepEqual(journal,original);
});
test('conference references use proceedings fields and retain hyphenated initials',()=>{
 const result=buildCitations({...journal,articleContentType:'Conferences',authors:[{firstName:'Wing-Hung',lastName:'Ki'}],publicationTitle:'2024 IEEE International Symposium on Circuits and Systems (ISCAS)',publicationYear:'2024',volume:'',issue:'',startPage:'1',endPage:'4'},'10558705');
 assert(result.values.bibtex.startsWith('@inproceedings{'));assert(result.values.bibtex.includes('booktitle = {2024 IEEE'));assert(!result.values.bibtex.includes('journal ='));
 assert(result.values.ieee.startsWith('W.-H. Ki, '));assert(result.values.ieee.includes('in 2024 IEEE'));assert(result.values.gbt2025.includes('[C]//2024 IEEE'));assert(result.values.ieee.includes('pp. 1–4'));
});
test('Early Access excludes provisional volume, issue and page numbers in every export',()=>{
 const result=buildCitations({...journal,articleContentType:'Early Access Articles',volume:'PP',issue:'99',startPage:'1',endPage:'11',publicationDate:'2026-10-28',publicationYear:'2026'},'11725301','2026-10-29');
 assert(result.earlyAccess);assert(result.values.bibtex.includes('note = {Early Access}'));assert(!/\n  (volume|number|pages) =/.test(result.values.bibtex));assert(!result.values.ieee.includes('vol.'));assert(!result.values.ieee.includes('pp.'));assert(result.values.ieee.includes('early access, Oct. 28, 2026'));assert(result.values.gbt2025.includes('[J/OL]'));assert(result.values.gbt2025.includes('2026[2026-10-29]'));
 const missingDate=buildCitations({...journal,articleContentType:'Early Access Articles',publicationDate:undefined},'11725301');assert(missingDate.missing.includes('online_date'));
});
test('empty DOI and long document IDs remain valid without fabricated article numbers',()=>{
 const number='123456789012345678901234567890';const result=buildCitations({...journal,doi:'',startPage:undefined,endPage:undefined},number);
 assert(result.values.bibtex.includes('ieee'+number));assert(result.values.bibtex.includes('https://ieeexplore.ieee.org/document/'+number));assert(!result.values.bibtex.includes('doi ='));assert(!result.values.ieee.includes('Art. no.'));assert(!result.values.ieee.includes('pp.'));assert(!result.values.ieee.includes('undefined'));
});
test('markup and TeX-sensitive scientific titles cannot break a BibTeX field',()=>{
 const title='<b>RF</b> &amp; AI {5G}_#1: 0.5%/V, 35 &#956;s at 25&deg;C';
 const result=buildCitations({...journal,articleTitle:title},'123');
 assert.equal(citationText(title),'RF & AI {5G}_#1: 0.5%/V, 35 μs at 25°C');assert(result.values.bibtex.includes('\\{5G\\}\\_\\#1'));assert(result.values.bibtex.includes('0.5\\%/V'));assert(result.values.bibtex.includes('\\ensuremath{\\mu}'));assert(result.values.bibtex.includes('\\ensuremath{^{\\circ}}'));assert(!result.values.bibtex.includes('<b>'));assert(result.values.ieee.includes('35 μs'));
 assert.equal(citationText('A <0.1% Converter With >95-dB SFDR'),'A <0.1% Converter With >95-dB SFDR');
});
test('author-list limits affect plain citations but never truncate the BibTeX export',()=>{
 const authors=Array.from({length:7},(_,i)=>({firstName:'Research',lastName:'Author'+i}));const result=buildCitations({...journal,authors},'123');
 assert(result.values.ieee.startsWith('R. Author0 et al.,'));assert(!result.values.ieee.includes('Author1'));assert(result.values.gbt2025.startsWith('AUTHOR0 R, AUTHOR1 R, AUTHOR2 R, et al.'));assert(result.values.bibtex.includes('Author6, Research'));
 const full=buildCitations({...journal,authors:[{preferredName:'Research and Design Group'}]},'124');assert(full.unstructuredAuthors);assert(full.values.bibtex.includes('author = {{Research and Design Group}}'));
});
test('missing source fields are reported, and arbitrary strings cannot become citation keys',()=>{
 const result=buildCitations({},'123');assert.deepEqual(result.missing,['title','authors','publication','year']);assert(!/undefined|null|Unknown Author/.test(Object.values(result.values).join(' ')));
 assert.throws(()=>buildCitations(journal,'../123'));assert.equal(citationText('&#xD800;'),'&#xD800;');
});
