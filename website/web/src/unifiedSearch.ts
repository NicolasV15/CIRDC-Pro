import type {SearchOptions} from './searchOptions';
export type Source='ieee'|'arxiv';
export const allSources:Source[]=['ieee','arxiv'];
/** Every key of the home page query. IEEE and arXiv filters stay in state while their source is unchecked. */
export type UnifiedFilters=SearchOptions&{sources:string;limit:string;year_from:string;year_to:string;
 venue_tags:string;kind:string;venue:string;abstract_state:string;keywords_state:string;author_source:string;author_id:string;author_unidentified:string;
 category:string};
const common=['sources','q','field','sort','view','k','terms','limit','year_from','year_to'] as const;
export const ieeeKeys=['venue_tags','kind','venue','abstract_state','keywords_state','author_source','author_id','author_unidentified'] as const;
export const arxivKeys=['category'] as const;
export const fieldSources:Record<string,Source[]>={all:allSources,title:allSources,authors:allSources,abstract:allSources,keywords:['ieee'],body:['ieee'],categories:['arxiv']};
const fieldOrder=['all','title','authors','keywords','abstract','body','categories'];

export function blankFilters(limit:string):UnifiedFilters{
 return {sources:'ieee,arxiv',q:'',field:'all',sort:'',view:'',k:'',terms:'',limit,year_from:'',year_to:'',venue_tags:'',kind:'',venue:'',abstract_state:'',keywords_state:'',author_source:'',author_id:'',author_unidentified:'',category:''};
}
/** Checked sources in a stable order; an empty or unknown value means both. */
export function selectedSources(value:string):Source[]{
 const wanted=new Set(value.split(',').map(part=>part.trim().toLowerCase()));
 const chosen=allSources.filter(source=>wanted.has(source));
 return chosen.length?chosen:[...allSources];
}
/** At least one source stays checked. */
export function toggleSource(value:string,source:Source,checked:boolean){
 const current=new Set(selectedSources(value));
 if(checked)current.add(source);else if(current.size>1)current.delete(source);
 return allSources.filter(item=>current.has(item)).join(',');
}
/** Search fields offered for the checked sources. */
export function fieldsFor(sources:Source[]){
 return fieldOrder.filter(field=>fieldSources[field].some(source=>sources.includes(source)));
}
/** The source a field is limited to, when another checked source cannot match it. */
export function fieldOnlySource(field:string,sources:Source[]):Source|null{
 const supported=(fieldSources[field]||allSources).filter(source=>sources.includes(source));
 return supported.length===1&&sources.length>1?supported[0]:null;
}
/** With a query, results rank by relevance unless the reader picked dates; without one, newest first. */
export function effectiveSort(f:Pick<UnifiedFilters,'q'|'sort'>){return f.sort||(f.q.trim()?'relevance':'year');}

/** Read the home page URL; the retired `source=arxiv` mode opens with only arXiv checked. */
export function filtersFromSearch(search:string,limit:string):UnifiedFilters{
 const params=new URLSearchParams(search),f=blankFilters(limit);
 for(const key of Object.keys(f) as (keyof UnifiedFilters)[])if(params.has(key))f[key]=params.get(key)||'';
 if(!params.has('sources')&&params.get('source')==='arxiv')f.sources='arxiv';
 f.sources=selectedSources(f.sources).join(',');
 if(!fieldsFor(selectedSources(f.sources)).includes(f.field))f.field='all';
 return f;
}
/** Only conditions of checked sources appear in the URL and the request. */
export function activeEntries(f:UnifiedFilters){
 const sources=selectedSources(f.sources);
 const keys=[...common,...(sources.includes('ieee')?ieeeKeys:[]),...(sources.includes('arxiv')?arxivKeys:[])];
 return keys.filter(key=>!!f[key]).map(key=>[key,f[key]] as [string,string]);
}
export function searchHref(f:UnifiedFilters){return '/?'+new URLSearchParams(activeEntries(f));}
/** Request parameters; IEEE family tags become publication numbers as on the former IEEE page. */
export function requestParams(f:UnifiedFilters,venueNumbers:(tags:string)=>string[]){
 const params=new URLSearchParams(activeEntries(f).filter(([key])=>key!=='venue_tags'));
 params.set('sort',effectiveSort(f));
 if(selectedSources(f.sources).includes('ieee')){const ids=venueNumbers(f.venue_tags);if(ids.length)params.set('venue_any',ids.join(','));}
 return params;
}

/** Rows of both sources share one selection; the key names the source so equal numeric ids never collide. */
export function paperKey(source:Source,id:string|number){return source+':'+id;}
export function parsePaperKey(key:string):{source?:Source;id:string}{
 const match=/^(ieee|arxiv):(.+)$/.exec(key);
 return match?{source:match[1] as Source,id:match[2]}:{id:key};
}

export type SourceStatus={enabled?:boolean;selected?:boolean;status:string;total:number|null;total_exact?:boolean;error?:string};
export type SourceNote={source:Source;code:string;field?:string};
/** Sources a reader checked that did not answer; a skipped field or unconfigured source is reported separately. */
export function unavailableSources(sources:Partial<Record<Source,SourceStatus>>|undefined){
 return allSources.filter(source=>sources?.[source]?.status==='error');
}
