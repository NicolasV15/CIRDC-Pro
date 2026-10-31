import {venueRanking} from './venueRanking.ts';
/** Display-only selection of publication families. No article-level classification. */
export type VenuePeriod={start:number;end:number|'Present';label?:string;old?:boolean};
export type VenueFamily={periods:VenuePeriod[];periodType?:'catalog';key:string;label:string;title:string;kind:'Journals'|'Conferences';seriesIds:string[];aliases?:string[];oldIds?:string[]};
export type VenueReference={kind?:string;venue?:string;venue_series?:string[];publication?:string};
export type VenueTag={family:VenueFamily;label:string;old:boolean};
export const venueFamilies:VenueFamily[]=[
 {key:'jssc',periods:[{"start":1966,"end":"Present"}],label:'JSSC',title:'IEEE Journal of Solid-State Circuits',kind:'Journals',seriesIds:['4']},
 {key:'lssc',periods:[{"start":2018,"end":"Present"}],label:'LSSC',title:'IEEE Solid-State Circuits Letters',kind:'Journals',seriesIds:['8011414'],aliases:['SSCL']},
 {key:'tcas',periods:[{"start":1974,"end":1991}],label:'TCAS',title:'IEEE Transactions on Circuits and Systems',kind:'Journals',seriesIds:['31'],oldIds:['31']},
 {key:'tcas-i',periods:[{"start":2004,"end":"Present"},{"start":1992,"end":2003,"old":true}],label:'TCAS-I',title:'IEEE Transactions on Circuits and Systems I: Regular Papers / Fundamental Theory and Applications',kind:'Journals',seriesIds:['8919','81'],oldIds:['81']},
 {key:'tcas-ii',periods:[{"start":2004,"end":"Present"},{"start":1992,"end":2003,"old":true}],label:'TCAS-II',title:'IEEE Transactions on Circuits and Systems II: Express Briefs / Analog and Digital Signal Processing',kind:'Journals',seriesIds:['8920','82'],oldIds:['82']},
 {key:'tvlsi',periods:[{"start":1993,"end":"Present"}],label:'TVLSI',title:'IEEE Transactions on Very Large Scale Integration (VLSI) Systems',kind:'Journals',seriesIds:['92']},
 {key:'tcad',periods:[{"start":1982,"end":"Present"}],label:'TCAD',title:'IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems',kind:'Journals',seriesIds:['43']},
 {key:'proc-ieee',periods:[{"start":1963,"end":"Present"}],label:'Proc. IEEE',title:'Proceedings of the IEEE',kind:'Journals',seriesIds:['5']},
 {key:'j-tcad',periods:[{"start":1996,"end":1996}],label:'J-TCAD',title:'Journal of Technology Computer Aided Design TCAD',kind:'Journals',seriesIds:['6414145'],oldIds:['6414145'],aliases:['Technology CAD','网站显示别名']},
 {key:'a-sscc',periods:[{"start":2005,"end":2025}],periodType:'catalog',label:'A-SSCC',title:'IEEE Asian Solid-State Circuits Conference',kind:'Conferences',seriesIds:['1001114'],aliases:['ASSCC']},
 {key:'async',periods:[{"start":1994,"end":2026}],periodType:'catalog',label:'ASYNC',title:'International Symposium on Asynchronous Circuits and Systems',kind:'Conferences',seriesIds:['1000014']},
 {key:'cicc',periods:[{"start":1988,"end":2026}],periodType:'catalog',label:'CICC',title:'IEEE Custom Integrated Circuits Conference',kind:'Conferences',seriesIds:['1000173']},
 {key:'dac',periods:[{"start":1978,"end":2025}],periodType:'catalog',label:'DAC',title:'Design Automation Conference',kind:'Conferences',seriesIds:['1000196']},
 {key:'date',periods:[{"start":1998,"end":2026}],periodType:'catalog',label:'DATE',title:'Design, Automation and Test in Europe',kind:'Conferences',seriesIds:['1000198']},
 {key:'esserc',periods:[{"label":"ESSERC","start":2024,"end":2025},{"label":"ESSCIRC","start":1975,"end":2023,"old":true}],periodType:'catalog',label:'ESSERC / ESSCIRC',title:'European Solid-State Electronics Research Conference / European Solid-State Circuits Conference',kind:'Conferences',seriesIds:['1000709'],aliases:['ESSERC','ESSCIRC']},
 {key:'iccad',periods:[{"start":1988,"end":2025}],periodType:'catalog',label:'ICCAD',title:'International Conference on Computer-Aided Design',kind:'Conferences',seriesIds:['1000151']},
 {key:'iedm',periods:[{"start":1955,"end":2025}],periodType:'catalog',label:'IEDM',title:'International Electron Devices Meeting',kind:'Conferences',seriesIds:['1000245']},
 {key:'isca',periods:[{"start":1988,"end":2026}],periodType:'catalog',label:'ISCA',title:'International Symposium on Computer Architecture',kind:'Conferences',seriesIds:['1000123']},
 {key:'iscas',periods:[{"start":1988,"end":2026}],periodType:'catalog',label:'ISCAS',title:'IEEE International Symposium on Circuits and Systems',kind:'Conferences',seriesIds:['1000089']},
 {key:'isscc',periods:[{"start":1955,"end":2026}],periodType:'catalog',label:'ISSCC',title:'IEEE International Solid-State Circuits Conference',kind:'Conferences',seriesIds:['1000708']},
 {key:'mems',periods:[{"start":1989,"end":2026}],periodType:'catalog',label:'MEMS',title:'IEEE International Conference on Micro Electro Mechanical Systems',kind:'Conferences',seriesIds:['1000438']},
 {key:'vlsi',periods:[{"start":2022,"end":2026},{"label":"VLSI-C","start":1987,"end":2021,"old":true},{"label":"VLSI-T","start":1981,"end":2021,"old":true}],periodType:'catalog',label:'VLSI',title:'Symposium on VLSI Technology and Circuits / Symposium on VLSI Circuits / Symposium on VLSI Technology',kind:'Conferences',seriesIds:['1000798','1000802'],aliases:['VLSI-C','VLSI-T']},
];
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
// describe catalog editions verified on 2026-10-28, not conference founding dates.
export function isHistoricalFamily(family:VenueFamily){return family.seriesIds.every(id=>family.oldIds?.includes(id));}
export function orderVenueFamilies(families:VenueFamily[]){return [...families].sort((a,b)=>{const x=venueRanking[a.key],y=venueRanking[b.key];const old=Number(isHistoricalFamily(a))-Number(isHistoricalFamily(b));return (x?.tier||4)-(y?.tier||4)||old||(x?.order||999)-(y?.order||999);});}
export function venuePeriodText(family:VenueFamily,present='至今',catalog='目录'){
 const ranges=family.periods.map(period=>{
  const range=period.start===period.end?String(period.start):period.start+'–'+(period.end==='Present'?present:period.end);
  return [period.label,period.old?'Old':'',range].filter(Boolean).join(' ');
 });
 return (family.periodType==='catalog'?catalog+'：':'')+ranges.join('；');
}
