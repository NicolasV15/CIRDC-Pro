import {test} from 'node:test';
import assert from 'node:assert/strict';
import {blankFilters,effectiveSort,fieldOnlySource,fieldsFor,filtersFromSearch,paperKey,parsePaperKey,requestParams,searchHref,selectedSources,toggleSource,unavailableSources} from '../src/unifiedSearch.ts';

test('both sources are checked by default and one always stays checked',()=>{
 assert.deepEqual(selectedSources(''),['ieee','arxiv']);
 assert.deepEqual(selectedSources('arxiv,ieee'),['ieee','arxiv']);
 assert.deepEqual(selectedSources('bogus'),['ieee','arxiv']);
 assert.equal(toggleSource('ieee,arxiv','ieee',false),'arxiv');
 assert.equal(toggleSource('arxiv','arxiv',false),'arxiv');
 assert.equal(toggleSource('arxiv','ieee',true),'ieee,arxiv');
});

test('fields follow the checked sources and single-source fields are named',()=>{
 assert.deepEqual(fieldsFor(['ieee','arxiv']),['all','title','authors','keywords','abstract','body','categories']);
 assert.deepEqual(fieldsFor(['ieee']),['all','title','authors','keywords','abstract','body']);
 assert.deepEqual(fieldsFor(['arxiv']),['all','title','authors','abstract','categories']);
 assert.equal(fieldOnlySource('keywords',['ieee','arxiv']),'ieee');
 assert.equal(fieldOnlySource('categories',['ieee','arxiv']),'arxiv');
 assert.equal(fieldOnlySource('keywords',['ieee']),null);
 assert.equal(fieldOnlySource('title',['ieee','arxiv']),null);
});

test('the URL keeps only conditions of checked sources and maps the retired arXiv mode',()=>{
 const legacy=filtersFromSearch('?source=arxiv&q=adc&field=keywords','25');
 assert.equal(legacy.sources,'arxiv');assert.equal(legacy.field,'all');assert.equal(legacy.q,'adc');
 const f={...blankFilters('25'),sources:'arxiv',q:'adc',category:'eess.SP',venue_tags:'jssc',kind:'Journals',year_from:'2024'};
 assert.equal(searchHref(f),'/?sources=arxiv&q=adc&field=all&limit=25&year_from=2024&category=eess.SP');
 const both=requestParams({...f,sources:'ieee,arxiv'},tags=>tags?['4','81']:[]);
 assert.equal(both.get('venue_any'),'4,81');assert.equal(both.get('kind'),'Journals');assert.equal(both.get('category'),'eess.SP');assert.equal(both.has('venue_tags'),false);
 assert.equal(requestParams({...f,sources:'ieee'},()=>['4']).has('category'),false);
});

test('without a query the order is newest first unless chosen',()=>{
 assert.equal(effectiveSort({q:'',sort:''}),'year');
 assert.equal(effectiveSort({q:'adc',sort:''}),'relevance');
 assert.equal(effectiveSort({q:'adc',sort:'year'}),'year');
});

test('row keys keep equal numeric ids from different sources apart',()=>{
 assert.notEqual(paperKey('ieee','12'),paperKey('arxiv','12'));
 assert.deepEqual(parsePaperKey(paperKey('arxiv','12')),{source:'arxiv',id:'12'});
 assert.deepEqual(parsePaperKey('10234567'),{id:'10234567'});
 assert.deepEqual(unavailableSources({ieee:{status:'ok',total:3},arxiv:{status:'error',total:null}}),['arxiv']);
 assert.deepEqual(unavailableSources({ieee:{status:'ok',total:3},arxiv:{status:'skipped_field',total:null}}),[]);
});
