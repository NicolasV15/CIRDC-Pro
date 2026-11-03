import assert from 'node:assert/strict';
import {test} from 'node:test';
import {findPassage,fingerprintOf,matchRanges,textTokens} from '../src/passageLocate.ts';

test('tokens follow the index: NFKC, case and Latin diacritics folded, punctuation ignored',()=>{
 assert.deepEqual(textTokens('ﬁlter ΔΣ Naïve, SAR-ADC (2.5 GS/s)'),['filter','δσ','naive','sar','adc','2','5','gs','s']);
 assert.equal(fingerprintOf('Because the amplifier operates open loop, its gain depends on the transconductance ⋯ and the integration time.'),
  'because the amplifier operates open loop its gain depends on the transconductance');
});
test('match ranges cover whole token sequences across case, punctuation and line breaks',()=>{
 const text='The SAR-ADC uses a successive\napproximation ADC loop; sar adcs differ.';
 const ranges=matchRanges(text,[['sar','adc'],['successive','approximation','adc']]);
 assert.deepEqual(ranges.map(([a,b])=>text.slice(a,b)),['SAR-ADC','successive\napproximation ADC']);
 assert.deepEqual(matchRanges('adcs',[['adc']]),[]);
});
test('a passage is relocated by its leading words when ordinals shift, never guessed',()=>{
 const texts=['Introduction','Alpha beta gamma.','The converter partitions the conversion.','Results'];
 assert.equal(findPassage(texts,2,fingerprintOf(texts[2])),2);
 assert.equal(findPassage(['Extra label',...texts],2,fingerprintOf(texts[2])),3);
 assert.equal(findPassage(texts,1,fingerprintOf('A paragraph that is not in this version.')),-1);
});
