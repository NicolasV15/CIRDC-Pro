import {test} from 'node:test';
import assert from 'node:assert/strict';
import {agentPrompts,CIRDC_REPOSITORY} from '../src/agentAccess.ts';

test('online installation binds to the visited site and its own installer',()=>{
 const {remote}=agentPrompts('https://papers.example.org:8443');
 assert(remote.includes('https://papers.example.org:8443/api/agent/v1/skills/cirdc-research/SKILL.md'));
 assert(remote.includes('https://papers.example.org:8443/api/agent/v1/skills/cirdc-research/scripts/install_skill.py'));
 assert(remote.includes('--base-url https://papers.example.org:8443'));
});

test('self hosting uses the conversation directory and never inherits the remote service address',()=>{
 const first=agentPrompts('https://first.example.org');
 const second=agentPrompts('https://second.example.org');
 assert.equal(first.local,second.local);
 assert.notEqual(first.remote,second.remote);
 assert(first.local.includes('当前对话的工作目录'));
 assert(first.local.includes('pwd'));
 assert(first.local.includes(CIRDC_REPOSITORY));
 assert(!first.local.includes('https://first.example.org'));
 assert(first.local.includes('--base-url'));
 assert.doesNotMatch(first.local,/【请填写|ENTER WORKING DIRECTORY/);
});

test('language changes preserve the site and automatic working-directory workflow',()=>{
 const zh=agentPrompts('https://papers.example.org','zh');
 const en=agentPrompts('https://papers.example.org','en');
 assert.notEqual(zh.remote,en.remote);assert.notEqual(zh.local,en.local);
 assert(en.local.includes("conversation's current working directory"));
 for(const value of [zh,en]){
  assert.deepEqual(Object.keys(value).sort(),['local','remote']);
  assert(value.remote.includes('--base-url https://papers.example.org'));
  assert(value.local.includes('pwd'));
  assert(value.local.includes(CIRDC_REPOSITORY));
  assert(value.local.includes('/api/agent/v1/capabilities'));
 }
});
