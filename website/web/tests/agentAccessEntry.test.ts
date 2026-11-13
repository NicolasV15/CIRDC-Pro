import assert from 'node:assert/strict';
import {test} from 'node:test';
import {agentAccessEntry} from '../src/agentAccessEntry.ts';

const site='https://papers.example.org';
test('normal author and search entries do not open or rewrite an AI route',()=>{
 for(const path of ['/authors/ieee/9007199254740995','/?q=test','/papers/123'])assert.deepEqual(agentAccessEntry(site+path,site+'/developers/ai'),{open:false});
});
test('legacy AI links retain a same-origin author ID, query and section',()=>{
 assert.deepEqual(agentAccessEntry(site+'/developers/ai',site+'/authors/ieee/9007199254740995?lang=en#topics'),{open:true,returnPath:'/authors/ieee/9007199254740995?lang=en#topics'});
 assert.deepEqual(agentAccessEntry(site+'/developers/ai',site+'/authors/ieee/42/'),{open:true,returnPath:'/authors/ieee/42'});
});
test('external, administrative and malformed referrers cannot choose a background route',()=>{
 for(const referrer of ['', 'not a URL','https://other.example.org/authors/ieee/42',site+':8443/authors/ieee/42',site+'/admin/',site+'/api/authors/ieee/42',site+'/authors/other/42',site+'/authors/ieee/42/extra',site+'/authors/ieee/not-an-id',site+'/authors/ieee/'+('1'.repeat(65)),site+'/developers/ai'])assert.deepEqual(agentAccessEntry(site+'/developers/ai',referrer),{open:true});
});
