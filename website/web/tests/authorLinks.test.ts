import assert from 'node:assert/strict';
import {test} from 'node:test';
import {authorSearchHref,ieeeAuthorHref,otherAuthorIdentities,type AuthorIdentity} from '../src/authorLinks.ts';
test('author links preserve opaque IDs and names without carrying unrelated filters',()=>{
 const id='9007199254740995';const url=new URL(authorSearchHref({source:'ieee',author_id:id,name:'Kim & Li / 李',ordinal:0})!,'http://test/');
 assert.equal(url.searchParams.get('author_id'),id);assert.equal(url.searchParams.get('q'),'Kim & Li / 李');assert.equal(url.searchParams.get('field'),'authors');assert.equal(url.searchParams.get('author_source'),'ieee');assert.equal([...url.searchParams].length,4);
});
test('missing IDs are never guessed and nameless identified authors remain searchable',()=>{
 assert.equal(authorSearchHref({source:'ieee',author_id:null,name:'Same Name',ordinal:0}),undefined);
 const url=new URL(authorSearchHref({source:'ieee',author_id:'11',name:'',ordinal:0})!,'http://test/');assert.equal(url.searchParams.get('q'),'11');
});
test('the pinned identity is excluded from candidate pages and repeated IDs are deduplicated by source',()=>{
 const row=(source:string,id:string)=>({identity_key:source+':'+id,source,author_id:id,display_name:'Same Name',papers:1,first_year:2020,last_year:2026,name_variants:[]}) satisfies AuthorIdentity;
 const selected=row('ieee','22'),other=row('ieee','11');assert.deepEqual(otherAuthorIdentities([other,selected,other,row('future','22')],'ieee','22').map(a=>a.identity_key),['ieee:11','future:22']);
});

test('IEEE source pages use the source ID losslessly and never guess IDs or hosts',()=>{
 assert.equal(ieeeAuthorHref({source:'ieee',author_id:'9007199254740995'}),'https://ieeexplore.ieee.org/author/9007199254740995');
 for(const item of [{source:'other',author_id:'11'},{source:'ieee',author_id:null},{source:'ieee',author_id:'../11'},{source:'ieee',author_id:'javascript:alert(1)'}])assert.equal(ieeeAuthorHref(item),undefined);
});

test('stored profile links keep string identity and do not change paper-search links',async()=>{
 const {authorProfileHref}=await import('../src/authorLinks.ts');
 assert.equal(authorProfileHref({source:'ieee',author_id:'9007199254740993'}),'/authors/ieee/9007199254740993');
 assert.equal(authorProfileHref({source:'ieee',author_id:null}),undefined);
 assert.equal(authorProfileHref({source:'other',author_id:'123'}),undefined);
});
