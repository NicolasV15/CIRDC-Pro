import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildCitations} from '../src/citations.ts';
import {downloadFilenames} from '../src/downloadNames.ts';
test('arXiv citations preserve source and selected version without IEEE identity',()=>{
 const result=buildCitations({source:'arxiv',sourceId:'hep-th/9901001',sourceVersion:2,articleTitle:'A preprint',articleContentType:'Preprint',publicationTitle:'arXiv:hep-th/9901001v2',publicationYear:2000,authors:[{preferredName:'A. Author'}]},'42');
 assert.match(result.values.bibtex,/@misc\{arxivhep_th_9901001v2/);assert.match(result.values.bibtex,/archivePrefix = \{arXiv\}/);assert.ok(Object.values(result.values).every(text=>!text.includes('ieeexplore')&&!text.includes('ieee42')));assert.match(result.values.gbt2025,/\[EB\/OL\]/);assert.match(result.values.ieee,/https:\/\/arxiv.org\/abs\/hep-th\/9901001v2/);
 assert.throws(()=>buildCitations({source:'arxiv',sourceId:'../bad',sourceVersion:1},'42'));
});
test('download filenames display arXiv identity while internal IDs remain queue keys',()=>{const files=downloadFilenames('{id}_{title}',[{number:'42',display_number:'hep-th/9901001v2',title:'A preprint'}]);assert.equal(files[0].number,'42');assert.match(files[0].filename,/hep-th-9901001v2_A preprint\.pdf/);});

test('detail and list citation metadata keep the selected version and preprint source',async()=>{
 const {arxivCitationRecord}=await import('../src/arxivCitations.ts');
 const paper={arxiv_id:'0704.0001',title:'A preprint',authors_raw:'Original Author',metadata:{doi:'10.1109/formal-publication'},versions:[{version:1,version_date:'2007-04-01'},{version:2,version_date:'2008-05-01'}]};
 const first=arxivCitationRecord(paper,1),second=arxivCitationRecord(paper,2);
 assert.equal(first.sourceVersion,1);assert.equal(first.publicationYear,2007);assert.equal(second.sourceVersion,2);assert.equal(second.publicationYear,2008);assert.equal(first.doi,undefined);assert.match(buildCitations(first,'1').values.bibtex,/0704\.0001v1/);assert.match(buildCitations(second,'1').values.bibtex,/0704\.0001v2/);assert.throws(()=>arxivCitationRecord(paper,3));
});
test('arXiv citations decode TeX text accents but keep title math unchanged',async()=>{
 const {arxivCitationRecord}=await import('../src/arxivCitations.ts');
 const paper={arxiv_id:'2611.14067',title:"Hall crystals in moir\\'e graphene with $\\'{x}$ scaling",authors_raw:"C. Bal\\'azs and J. Mart\\'{\\i}n",versions:[{version:1,version_date:'2026-11-10'}]};
 const record=arxivCitationRecord(paper,1);
 assert.equal(record.articleTitle,"Hall crystals in moiré graphene with $\\'{x}$ scaling");
 assert.deepEqual(record.authors,[{preferredName:'C. Balázs and J. Martín'}]);
 const bibtex=buildCitations(record,'1').values.bibtex;
 assert.match(bibtex,/moiré graphene/);assert.ok(!bibtex.includes("moir\\textbackslash"));
});
