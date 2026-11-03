export type PatentCitation={
 order:number;label:string;source_id:string|null;text:string;title:string|null;
 publication_number:string|null;country:string|null;publication_date:string|null;inventors:string[];assignee:string|null;
 target_kind:'patent'|'patent_search';target_url:string|null;
};
export type PatentCitationsPage={
 number:string;state:string;version:string|null;total:number;expected_total:number|null;
 source_presence:'present'|'absent'|'unknown';empty_reason:'section_absent'|'zero_count'|null;
 checked_at:string|null;last_attempt_at:string|null;next_check_at:string|null;stale:boolean;error:string|null;
 offset:number;limit:number;next_offset:number|null;items:PatentCitation[];
};
export const PATENT_CITATION_PAGE_SIZE=50;
export const patentCitationsPending=(page:PatentCitationsPage|null)=>!!page&&(page.state==='queued'||page.state==='fetching');
export const patentSourceAbsent=(page:PatentCitationsPage)=>page.source_presence==='absent'||page.empty_reason==='section_absent';
export function patentCitationCount(page:PatentCitationsPage|null):number|undefined{
 if(!page||patentSourceAbsent(page))return;
 const value=page.expected_total;
 if(value===null||!Number.isSafeInteger(value)||value<0)return;
 if(value===0&&page.empty_reason!=='zero_count'&&!(page.source_presence==='present'&&['complete','no_data'].includes(page.state)))return;
 return value;
}
export function patentPublicationNumber(value:string|null){
 if(typeof value!=='string')return;
 const normalized=value.replace(/[\s,.-]/g,'').toUpperCase();
 return /^[A-Z]{2}[0-9]{4,15}(?:[A-Z][0-9]{0,2})?$/.test(normalized)?normalized:undefined;
}
export function patentCitationLabel(item:Pick<PatentCitation,'order'|'label'>){const label=item.label?.trim()||String(item.order);return /^\[.*\]$|^\(.*\)$/.test(label)?label:'['+label+']';}
export function patentCitationLink(item:PatentCitation):{href:string;kind:'patent'|'patent_search'}|undefined{
 // Rebuild both targets from citation metadata; an upstream URL can never become a local paper link.
 const number=patentPublicationNumber(item.publication_number);
 if(number)return {href:'https://patents.google.com/patent/'+number+'/en',kind:'patent'};
 const query=item.title?.trim()||item.text?.trim();
 if(query)return {href:'https://patents.google.com/?'+new URLSearchParams({q:query}),kind:'patent_search'};
}
export function validatePatentCitationPage(page:PatentCitationsPage,number:string){
 if(page.number!==number||!Array.isArray(page.items)||!Number.isSafeInteger(page.total)||page.total<0
   ||(page.expected_total!==null&&(!Number.isSafeInteger(page.expected_total)||page.expected_total<0))
   ||!Number.isSafeInteger(page.offset)||page.offset<0||!Number.isSafeInteger(page.limit)||page.limit<1||page.limit>100
   ||(page.next_offset!==null&&(!Number.isSafeInteger(page.next_offset)||page.next_offset<=page.offset||page.next_offset>=page.total))
   ||(!page.version&&page.items.length)||page.items.some(item=>!Number.isSafeInteger(item.order)||item.order<1)
   ||new Set(page.items.map(item=>item.order)).size!==page.items.length)throw Error('patent_citation_snapshot_mismatch');
}
export function mergePatentCitationPage(previous:PatentCitationsPage|null,page:PatentCitationsPage,append=false):PatentCitationsPage{
 if(append&&(!previous?.version||page.number!==previous.number||page.version!==previous.version||page.total!==previous.total||page.expected_total!==previous.expected_total))throw Error('patent_citation_snapshot_mismatch');
 if(!previous||previous.number!==page.number)return {...page,items:[...page.items]};
 if(previous.version&&page.version!==previous.version&&(patentCitationsPending(page)||['blocked','failed'].includes(page.state)||(!page.version&&page.state==='partial'))){
  return {...previous,state:page.state,error:page.error,last_attempt_at:page.last_attempt_at,next_check_at:page.next_check_at,stale:page.stale};
 }
 if(page.version!==previous.version)return {...page,items:[...page.items]};
 if(page.version&&(page.total!==previous.total||page.expected_total!==previous.expected_total))throw Error('patent_citation_snapshot_mismatch');
 const items=[...new Map([...previous.items,...page.items].map(item=>[item.order,item])).values()].sort((a,b)=>a.order-b.order);
 return append?{...previous,items,next_offset:page.next_offset}:{...page,items,next_offset:previous.next_offset};
}
