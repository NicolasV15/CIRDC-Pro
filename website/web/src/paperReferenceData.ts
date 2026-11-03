export type PaperReference={order:number;label:string;source_id:string|null;text:string;title:string|null;target_number:string|null;doi:string|null;target_kind:string;target_url:string|null};
export type ReferencesPage={number:string;state:string;version:string|null;total:number;expected_total:number|null;checked_at:string|null;error:string|null;offset:number;limit:number;next_offset:number|null;items:PaperReference[];source_presence?:'present'|'absent'|'unknown';empty_reason?:'section_absent'|'zero_count'|null;availability_checked_at?:string|null;needs_availability_check?:boolean};
export type ReferenceJump={order:number;source:HTMLElement;token:number};
export const REFERENCE_PAGE_SIZE=50;

export function referencesPending(state:string){return state==='queued'||state==='fetching';}
export function shouldEnsureReferences(page:ReferencesPage){return page.state==='missing'||(page.state==='unavailable'&&page.needs_availability_check===true);}
export function referenceCountKnown(page:ReferencesPage){return page.source_presence!=='absent'&&(page.items.length>0||['complete','no_data'].includes(page.state)||page.empty_reason==='zero_count'||!!(page.version&&page.checked_at));}
export function referenceLink(item:PaperReference):{href:string;kind:'paper'|'scholar'}|undefined{
 if(typeof item.target_number==='string'&&/^\d{1,64}$/.test(item.target_number))return {href:'/papers/'+item.target_number,kind:'paper'};
 if(typeof item.target_url!=='string')return;
 try{
  const url=new URL(item.target_url);
  if(url.protocol==='https:'&&url.hostname==='scholar.google.com'&&url.pathname==='/scholar'&&!url.username&&!url.password&&(!url.port||url.port==='443'))return {href:item.target_url,kind:'scholar'};
 }catch{/* A malformed target remains readable citation text. */}
}
export function referenceLabel(item:PaperReference){const label=item.label?.trim()||String(item.order);return /^\[.*\]$|^\(.*\)$/.test(label)?label:'['+label+']';}
export function mergeReferenceItems(previous:PaperReference[],items:PaperReference[]){
 return [...new Map([...previous,...items].map(item=>[item.order,item])).values()].sort((a,b)=>a.order-b.order);
}
export function mergeReferencePage(previous:ReferencesPage|null,page:ReferencesPage,append=false):ReferencesPage{
 if(append&&(!previous||!previous.version||page.number!==previous.number||page.version!==previous.version||page.total!==previous.total))throw new Error('reference_snapshot_mismatch');
 if(!previous||previous.number!==page.number||previous.version!==page.version)return {...page,items:[...page.items]};
 if(page.version&&page.total!==previous.total)throw new Error('reference_snapshot_mismatch');
 const items=mergeReferenceItems(previous.items,page.items);
 return append?{...previous,items,next_offset:page.next_offset}:{...page,items,next_offset:previous.next_offset};
}

/** Only the publisher's explicit citation marker identifies a bibliographic order. */
export function citationOrder(marker:string):number|undefined{
 const match=/^context_ref_([1-9]\d*)(?:_(?:[1-9]\d*(?:[a-z]\d*)?)?)?$/i.exec(marker);
 if(!match)return;
 const order=Number(match[1]);return Number.isSafeInteger(order)?order:undefined;
}
export function uniqueCitationOrder(markers:string[]){
 const orders=new Set(markers.map(citationOrder).filter((order):order is number=>order!==undefined));
 return orders.size===1?[...orders][0]:undefined;
}
const originalCitationMarkers=new WeakMap<HTMLElement,string[]>();
export function restoreReferenceCitations(container:HTMLElement,panelId:string,label:(order:number)=>string,pageURL=location.href){
 const page=new URL(pageURL),paper=page.pathname.match(/^\/papers\/(\d+)\/?$/)?.[1];
 for(const node of container.querySelectorAll<HTMLElement>('.document-citation-link,[data-citation-order]')){node.classList.remove('document-citation-link');node.removeAttribute('data-citation-order');}
 const nodes=Array.from(container.querySelectorAll<HTMLElement>('a,span[id]')),markers=new Map<HTMLElement,string[]>();
 for(const node of nodes){
  let source=originalCitationMarkers.get(node);
  if(!source){
   source=[node.id,node.getAttribute('name')||''];const href=node.getAttribute('href');
   if(href){try{
    const url=new URL(href,page),same=url.origin===page.origin&&url.pathname===page.pathname;
    const publisher=!!paper&&url.protocol==='https:'&&url.hostname==='ieeexplore.ieee.org'&&url.pathname.match(/^\/document\/(\d+)(?:\/|$)/)?.[1]===paper;
    if(url.hash&&(same||publisher))source.push(decodeURIComponent(url.hash.slice(1)));
   }catch{/* Unrelated URLs never identify a bibliography entry. */}}
   originalCitationMarkers.set(node,source);
  }
  markers.set(node,source);
 }
 for(const node of nodes){
  const own=markers.get(node)!,order=uniqueCitationOrder(own);if(order===undefined)continue;
  const related=nodes.filter(other=>other!==node&&(other.contains(node)||node.contains(other)));
  if(uniqueCitationOrder([...own,...related.flatMap(other=>markers.get(other)!)])!==order)continue;
  if(related.some(other=>other.contains(node)&&uniqueCitationOrder(markers.get(other)!)===order))continue;
  node.dataset.citationOrder=String(order);node.classList.add('document-citation-link');node.classList.remove('document-reference-link');
  node.setAttribute('aria-label',label(order));node.removeAttribute('target');
  if(node.tagName==='A')node.setAttribute('href','#'+panelId);
  else{node.setAttribute('role','button');node.tabIndex=0;}
 }
}
