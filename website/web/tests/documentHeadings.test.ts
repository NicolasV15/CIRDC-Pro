import assert from 'node:assert/strict';
import {test} from 'node:test';
import {documentHeadingTitle,documentSectionNumber} from '../src/documentHeadings.ts';

test('publisher section labels preserve Roman and decimal numbering',()=>{
 for(const number of ['I','II','IV','IX','XXVII','XL','XC','C','399'])assert.equal(documentSectionNumber('SECTION '+number+'.'),number);
 assert.equal(documentSectionNumber('\n Section\u00a0ii. '),'II');
 assert.equal(documentSectionNumber('SECTION Ⅱ.'),'II');
 assert.equal(documentSectionNumber('SECTION IV'),'IV');
});
test('ordinary prose, subsection labels and anchor IDs never supply section numbers',()=>{
 for(const label of ['sec2','section-2','Section II discusses the system.','A. Applications','1) Radar:','ACKNOWLEDGMENT','SECTION III. Overview','SECTION IIII.','SECTION IC.','SECTION 0.','SECTION -1.',''])assert.equal(documentSectionNumber(label),undefined,label);
});
test('outline titles use the publisher number and preserve the source heading',()=>{
 assert.equal(documentHeadingTitle('SECTION II.','Transmit Signal and Receive Processing in 4-D Imaging Radars'),'II. Transmit Signal and Receive Processing in 4-D Imaging Radars');
 assert.equal(documentHeadingTitle('SECTION IV.','Challenges in Massive MIMO Radars'),'IV. Challenges in Massive MIMO Radars');
 assert.equal(documentHeadingTitle('SECTION 3.','A & B: α/β'),'3. A & B: α/β');
 assert.equal(documentHeadingTitle('SECTION III.','Δθ and x²'),'III. Δθ and x²');
});
test('existing numbers are not duplicated and incomplete labels remain unmodified',()=>{
 assert.equal(documentHeadingTitle('SECTION II.','II. Signal Processing'),'II. Signal Processing');
 assert.equal(documentHeadingTitle('SECTION II.','SECTION II. Signal Processing'),'II. Signal Processing');
 assert.equal(documentHeadingTitle('SECTION II.','III. Signal Processing'),undefined);
 assert.equal(documentHeadingTitle('SECTION II.',''),undefined);
 assert.equal(documentHeadingTitle('SECTION II.','SECTION II.'),undefined);
 assert.equal(documentHeadingTitle('Introduction','Radar'),undefined);
});
