import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {agentExamples} from '../src/agentAccess.ts';

test('connection examples use direct remote URLs without local installation',()=>{
 const examples=agentExamples('https://papers.example.org');
 const config=JSON.parse(examples.mcp).mcpServers['cirdc-research'];
 assert.equal(config.url,'https://papers.example.org/api/agent/v1/mcp');
 assert.equal(config.type,'http');
 assert.equal(config.command,undefined);
 assert.equal(examples.mcpUrl,config.url);
 assert.equal(examples.skillUrl,'https://papers.example.org/api/agent/v1/skills/cirdc-research/SKILL.md');
 assert.match(examples.http,/\/api\/agent\/v1\/requests\/REQUEST_ID/);
 assert.match(examples.python,/wait_seconds/);
 assert.doesNotMatch(examples.http,/\n\+/);
});


test('native installers use the current site and valid shell commands for each host',()=>{
 const examples=agentExamples('https://papers.example.org');
 assert.equal(examples.sourceInstall,'sh tools/install-skill --agent all');
 assert.equal(examples.installUrl,examples.base+'/skills/cirdc-research/scripts/install_skill.py');
 for(const [command,agent] of [[examples.installCodex,'codex'],[examples.installClaudeCode,'claude-code']]){
  assert(command.includes(examples.installUrl));
  assert(command.includes("--base-url 'https://papers.example.org' --agent "+agent));
  assert.equal(spawnSync('sh',['-n'],{input:command}).status,0);
  assert(command.includes('&&\npython3'));
 }
});
