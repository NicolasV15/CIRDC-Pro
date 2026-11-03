import circuitScope from "./data/circuit-scope.json" with { type: "json" };
import {venueRanking} from './venueRanking.ts';
/** Display-only selection of publication families. No article-level classification. */
export type VenuePeriod={start:number;end:number|'Present';label?:string;old?:boolean};
export type VenueFamily={periods:VenuePeriod[];periodType?:'catalog';key:string;label:string;title:string;kind:'Journals'|'Conferences';seriesIds:string[];aliases?:string[];oldIds?:string[]};
export type VenueReference={kind?:string;venue?:string;venue_series?:string[];publication?:string};
export type VenueTag={family:VenueFamily;label:string;old:boolean};
export const venueFamilies:VenueFamily[]=circuitScope.families as VenueFamily[];
export function selectedVenueFamilies(value:string){const keys=new Set(value.split(','));return venueFamilies.filter(f=>keys.has(f.key));}
export function venueNumbers(value:string){return [...new Set(selectedVenueFamilies(value).flatMap(f=>f.seriesIds))];}
const normalized=(value:string)=>value.toLowerCase().replace(/[\s\-.:/()]/g,'');
export function matchingVenueFamilies(value:string){const query=normalized(value.trim());return venueFamilies.filter(f=>!query||normalized([f.label,f.title,...(f.aliases||[])].join(' ')).includes(query));}
export function paperVenueTags(paper:VenueReference):VenueTag[]{
 const kind=['Early Access Articles','Magazines'].includes(paper.kind||'')?'Journals':paper.kind;
 const ids=new Set([paper.venue||'',...(paper.venue_series||[])]);
 const title=(paper.publication||'').replace(/<[^>]*>/g,'').replace(/&amp;/g,'&');
 return venueFamilies.filter(f=>f.kind===kind&&f.seriesIds.some(id=>ids.has(id))).map(f=>{
  let label=f.label,old=(f.oldIds||[]).some(id=>ids.has(id));
  if(f.key==='esserc'){
   if(/\bESSERC\b|European\s+Solid[\s-]*State\s+Electronics\s+Research/i.test(title))label='ESSERC';
   else if(/\bESSCIRC\b|European\s+(?:Conference\s+on\s+)?Solid[\s-]*State\s+Circuits/i.test(title)){label='ESSCIRC';old=true;}
  }
  if(f.key==='vlsi'){
   if(/VLSI\s+Technology\s+(?:and|&)\s+Circuits/i.test(title))label='VLSI';
   else if(/VLSI\s+Circuits/i.test(title)||ids.has('1000798')){label='VLSI-C';old=true;}
   else if(/VLSI\s+Technology/i.test(title)){label='VLSI-T';old=true;}
  }
  return {family:f,label,old};
 });
}

// Journal ranges follow the source's title start/end years. Conference ranges
// describe known catalog editions, not conference founding dates or query limits.
export function isHistoricalFamily(family:VenueFamily){return family.seriesIds.every(id=>family.oldIds?.includes(id));}
export function orderVenueFamilies(families:VenueFamily[]){return [...families].sort((a,b)=>{const x=venueRanking[a.key],y=venueRanking[b.key];const old=Number(isHistoricalFamily(a))-Number(isHistoricalFamily(b));return (x?.tier||4)-(y?.tier||4)||old||(x?.order||999)-(y?.order||999);});}
export function venuePeriodText(family:VenueFamily,present='至今',catalog='目录'){
 const ranges=family.periods.map(period=>{
  const range=period.start===period.end?String(period.start):period.start+'–'+(period.end==='Present'?present:period.end);
  return [period.label,period.old?'Old':'',range].filter(Boolean).join(' ');
 });
 return (family.periodType==='catalog'?catalog+'：':'')+ranges.join('；');
}
