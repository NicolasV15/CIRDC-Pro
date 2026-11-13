import assert from 'node:assert/strict';
import {test} from 'node:test';
import {algorithmIndentation,type AlgorithmControl} from '../src/documentAlgorithms.ts';

test('numbered topology steps retain three balanced loop levels',()=>{
 const controls:AlgorithmControl[]=['line','for','line','line','line','line','for','line','line','for','line','line','line','end for','end for','line','end for'];
 assert.deepEqual(algorithmIndentation(controls),[0,0,1,1,1,1,1,2,2,2,3,3,3,2,1,1,0]);
});
test('role sections reset completed loops and repeat/until closes at its opening depth',()=>{
 assert.deepEqual(algorithmIndentation(['section','for','line','end for','section','repeat','line','for','line','end for','line','until']),[0,0,1,0,0,0,1,1,2,1,1,0]);
});
test('conditional branches and nested while loops retain their own levels',()=>{
 assert.deepEqual(algorithmIndentation(['if','while','line','end while','else','line','end if']),[0,1,2,1,0,1,0]);
});
test('uncertain and unbalanced controls do not produce partial guessed indentation',()=>{
 for(const controls of [['for','line'],['end for'],['for','end while'],['else'],['repeat','section','until'],['for','unknown','end for']] as AlgorithmControl[][])assert.equal(algorithmIndentation(controls),undefined);
 assert.deepEqual(algorithmIndentation(['line','section','line']),[0,0,0]);
});
