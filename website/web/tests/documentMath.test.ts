import assert from 'node:assert/strict';
import {test} from 'node:test';
import {documentMathForDisplay} from '../src/documentMath.ts';
test('repeated equation numbers from PDF exports do not break KaTeX',()=>{
 assert.equal(documentMathForDisplay(String.raw`R_e(t)=x \tag {9}\tag{9}`),String.raw`R_e(t)=x \tag {9}`);
 assert.equal(documentMathForDisplay(String.raw`x \tag{1} \tag{1} \tag{1}`),String.raw`x \tag{1}`);
});
test('equation content and conflicting or distinct tags are preserved',()=>{
 for(const tex of [String.raw`x^2+\lambda \tag{9}`,String.raw`x \tag{9}\tag{10}`,String.raw`x \tag{a} + y \tag{a}`])assert.equal(documentMathForDisplay(tex),tex);
});
