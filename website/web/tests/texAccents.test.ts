import assert from 'node:assert/strict';
import {test} from 'node:test';
import {decodeTexAccents} from '../src/texAccents.ts';
test('TeX text accents in real arXiv metadata become Unicode letters',()=>{
 for(const [source,expected] of [
  ["C. Bal\\'azs, E. L. Berger","C. Balázs, E. L. Berger"],
  ["moir\\'e rhombohedral graphene","moiré rhombohedral graphene"],
  ["S. Catal\\'an-Gomez, M. Ib\\'a\\~nez","S. Catalán-Gomez, M. Ibáñez"],
  ["Mehmet Mercang\\\"oz","Mehmet Mercangöz"],
  ["Jok\\=ubas Dim\\v{s}a","Jokūbas Dimša"],
  ["J. Mart\\'{\\i}n-Albo","J. Martín-Albo"],
  ["{\\'E}cole and {\\\"u}ber","École and über"],
  ["S{\\o}ren, Stra\\ss e, \\l{}\\'od\\'z","Søren, Straße, łódź"],
  ["Fran\\c{c}ois and Fran\\c cois","François and François"],
 ] as const)assert.equal(decodeTexAccents(source),expected);
});
test('other backslash text is left unchanged',()=>{
 for(const value of ['\\cos x','100\\% yield','a\\_b','\\omega','plain text','\\v1'])assert.equal(decodeTexAccents(value),value);
});
