import assert from 'node:assert/strict';
import {test} from 'node:test';
import katex from 'katex';

// GHSA-238p-pmpm-9mq7: inherited options must not enable trusted HTML.
const unsafeLink = String.raw`\href{javascript:alert(1)}{x}`;

test('formula rendering ignores trust inherited from an options prototype', () => {
 const options = Object.create({trust: true});
 const html = katex.renderToString(unsafeLink, options);
 assert.doesNotMatch(html, /<a\b/);
});

test('prototype pollution cannot override an explicit trust restriction', () => {
 const previous = Object.getOwnPropertyDescriptor(Object.prototype, 'processor');
 try {
  Object.defineProperty(Object.prototype, 'processor', {value: () => true, configurable: true});
  const html = katex.renderToString(unsafeLink, {trust: false, strict: 'ignore'});
  assert.doesNotMatch(html, /<a\b/);
 } finally {
  if (previous) Object.defineProperty(Object.prototype, 'processor', previous);
  else Reflect.deleteProperty(Object.prototype, 'processor');
 }
});

test('untrusted scientific formulas still render HTML and MathML', () => {
 const html = katex.renderToString(String.raw`\frac{g_m}{2\pi C_L}`, {
  trust: false, throwOnError: true, output: 'htmlAndMathml',
 });
 assert.match(html, /class="katex"/);
 assert.match(html, /<math\b/);
 assert.match(html, /class="mfrac"/);
});
