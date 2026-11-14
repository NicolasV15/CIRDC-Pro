import assert from 'node:assert/strict';
import {test} from 'node:test';
const {acquisitionAction}=await import('../src/arxivResourceState.ts');
const {licenseLabel}=await import('../src/arxivLicense.ts');
const {arxivCategories,arxivCategoryName,isArxivArchive,circuitCategories}=await import('../src/arxivTaxonomy.ts');
const resources=(html:string,pdf:string,source:string)=>({html:{state:html},pdf:{state:pdf},source:{state:source}});
test('only an unrequested version or retryable branches offer an upstream action',()=>{
 assert.equal(acquisitionAction(null),null);
 assert.equal(acquisitionAction({state:'not_requested'}),'ensure');
 assert.equal(acquisitionAction({state:'queued',resources:resources('queued','queued','queued')}),null);
 assert.equal(acquisitionAction({state:'complete',resources:resources('ready','ready','ready')}),null);
 assert.equal(acquisitionAction({state:'partial',resources:resources('unavailable','ready','failed')}),'retry');
 assert.equal(acquisitionAction({state:'partial',resources:resources('unavailable','blocked','unavailable')}),'retry');
 assert.equal(acquisitionAction({state:'partial',resources:resources('ready','ready','unavailable'),reading_state:'failed'}),'retry');
 // Confirmed absence is final: retrying cannot produce a file arXiv does not offer.
 assert.equal(acquisitionAction({state:'partial',resources:resources('unavailable','unavailable','unavailable'),reading_state:'unavailable'}),null);
 assert.equal(acquisitionAction({state:'unexpected_state'}),null);
});
test('arXiv license URLs get short names and other values stay unchanged',()=>{
 assert.deepEqual(licenseLabel('http://creativecommons.org/licenses/by/4.0/'),{label:'CC BY 4.0',href:'http://creativecommons.org/licenses/by/4.0/'});
 assert.equal(licenseLabel('http://creativecommons.org/licenses/by-nc-nd/4.0/')?.label,'CC BY-NC-ND 4.0');
 assert.equal(licenseLabel('http://creativecommons.org/publicdomain/zero/1.0/')?.label,'CC0 1.0');
 assert.deepEqual(licenseLabel('http://arxiv.org/licenses/nonexclusive-distrib/1.0/'),{label:'arXiv 非独占分发许可 {v}',values:{v:'1.0'},href:'http://arxiv.org/licenses/nonexclusive-distrib/1.0/'});
 assert.deepEqual(licenseLabel('Custom terms'),{label:'Custom terms',href:undefined});
 assert.equal(licenseLabel(''),null);assert.equal(licenseLabel(undefined),null);
});
test('taxonomy codes are unique and quick categories have official names',()=>{
 const codes=arxivCategories.map(c=>c.code);
 assert.equal(new Set(codes).size,codes.length);
 for(const code of circuitCategories)assert.ok(arxivCategoryName(code),code);
 assert.equal(arxivCategoryName('EESS.sp'),'Signal Processing');
 assert.equal(arxivCategoryName('cmp-lg'),undefined);
 assert.ok(isArxivArchive('eess')&&isArxivArchive('cond-mat'));
 assert.ok(!isArxivArchive('eess.SP')&&!isArxivArchive('hep-th')&&!isArxivArchive('math-ph'));
 assert.ok(codes.includes('quant-ph')&&codes.includes('cs.AR')&&codes.includes('physics.app-ph'));
});
