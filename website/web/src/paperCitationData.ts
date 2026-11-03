import type {PaperReference} from './paperReferenceData';

export type CitationGroup='ieee'|'nonIeee';
export type PaperCitation=PaperReference&{group:CitationGroup};
export type CitationCounts={ieee:number|null;nonIeee:number|null;total:number|null};
export type CitationsPage={
 number:string;state:string;version:string|null;group:CitationGroup;total:number|null;expected_total:number|null;
 counts:CitationCounts;stored_counts:CitationCounts;group_states:Record<CitationGroup,string>;
 source_presence:'present'|'absent'|'unknown';empty_reason:'section_absent'|'zero_count'|null;
 checked_at:string|null;last_attempt_at:string|null;next_check_at:string|null;stale:boolean;error:string|null;
 offset:number;limit:number;next_offset:number|null;items:PaperCitation[];
};
export const CITATION_GROUPS:CitationGroup[]=['ieee','nonIeee'];
export const CITATION_PAGE_SIZE=50;
export const citationItemKey=(item:Pick<PaperCitation,'group'|'order'>)=>item.group+':'+item.order;
export function citationsPending(page:CitationsPage|null){return !!page&&[page.state,...Object.values(page.group_states)].some(state=>state==='queued'||state==='fetching');}
export function citationGroupState(page:CitationsPage,group:CitationGroup=page.group){return page.group_states[group]||page.state;}
export function citationCount(page:CitationsPage|null,group:CitationGroup):number|undefined{
 if(!page||page.source_presence==='absent')return;
 const value=page.counts[group],state=citationGroupState(page,group);
 if(!Number.isSafeInteger(value)||value===null||value<0)return;
 if(value===0&&!['complete','no_data'].includes(state)&&!(page.version&&page.checked_at))return;
 return value;
}
export function initialCitationGroup(pages:Record<CitationGroup,CitationsPage|null>):CitationGroup|undefined{
 const saved=CITATION_GROUPS.find(group=>!!pages[group]?.items.length);
 if(saved)return saved;
 const known=CITATION_GROUPS.find(group=>(citationCount(pages[group],group)||0)>0);
 if(known)return known;
 if(CITATION_GROUPS.some(group=>pages[group]?.version||citationCount(pages[group],group)!==undefined))return 'ieee';
}
export function showCitationGroups(pages:Record<CitationGroup,CitationsPage|null>){
 return CITATION_GROUPS.every(group=>!!pages[group]?.items.length||(citationCount(pages[group],group)||0)>0);
}
export function validateCitationPage(page:CitationsPage,number:string,group:CitationGroup){
 if(page.number!==number||page.group!==group||!Array.isArray(page.items)||!page.counts||!page.stored_counts||!page.group_states
   ||(page.total!==null&&(!Number.isSafeInteger(page.total)||page.total<0))||(!page.version&&page.items.length)
   ||page.items.some(item=>item.group!==group||!Number.isSafeInteger(item.order)||item.order<1))throw Error('citation_snapshot_mismatch');
}
export function mergeCitationItems(previous:PaperCitation[],items:PaperCitation[]){
 return [...new Map([...previous,...items].map(item=>[citationItemKey(item),item])).values()]
  .sort((a,b)=>a.group.localeCompare(b.group)||a.order-b.order);
}
export function mergeCitationPage(previous:CitationsPage|null,page:CitationsPage,append=false):CitationsPage{
 if(append&&(!previous?.version||page.number!==previous.number||page.group!==previous.group||page.version!==previous.version||page.total!==previous.total))throw Error('citation_snapshot_mismatch');
 if(!previous||previous.number!==page.number||previous.group!==page.group)return {...page,items:[...page.items]};
 // A failed or pending update must never discard a previously readable snapshot.
 if(previous.version&&!page.version&&['queued','fetching','partial','blocked','failed'].includes(page.state))return {...previous,state:page.state,
  error:page.error,last_attempt_at:page.last_attempt_at,next_check_at:page.next_check_at,stale:page.stale,group_states:page.group_states};
 if(page.version!==previous.version)return {...page,items:[...page.items]};
 if(page.version&&page.total!==previous.total)throw Error('citation_snapshot_mismatch');
 const items=mergeCitationItems(previous.items,page.items);
 return append?{...previous,items,next_offset:page.next_offset}:{...page,items,next_offset:previous.next_offset};
}
