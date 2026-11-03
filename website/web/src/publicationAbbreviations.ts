import {citationText} from './citations.ts';

export type PublicationAbbreviations=Readonly<Record<string,string>>;

/** Same lookup normalization as the supplied Papers by Venue mapping. */
export function publicationLookupKey(title:string){
 return title.replace(/\b(19|20)\d{2}\b/gu,'').replace(/'\d{2}\b/gu,'')
  .replace(/\b\d+(?:st|nd|rd|th)\b/giu,'').replace(/[.,-]/gu,' ')
  .replace(/\bIEEE\b/giu,'').replace(/\s+/gu,' ').trim().toLowerCase();
}

// Display fallbacks only. These rules never define filter families or tiers.
const fallbackRules:readonly (readonly [string,string])[]=[
 ['design automation and test in europe','DATE'],
 ['international symposium on circuits and systems','ISCAS'],
 ['international symposium of circuits and systems','ISCAS'],
 ['asian solid state circuits conference','A-SSCC'],
 ['solid state circuits letters','IEEE SSC-L'],
 ['journal of solid state circuits','IEEE JSSC'],
 ['circuits and systems ii','IEEE TCAS-II'],
 ['circuits and systems i','IEEE TCAS-I'],
 ['very large scale integration','IEEE TVLSI'],
 ['international conference on vlsi design','VLSID'],
 ['midwest symposium on circuits and systems','MWSCAS'],
];

export function publicationAbbreviation(value:unknown,map?:PublicationAbbreviations){
 const title=citationText(value);if(!title)return;
 const matched=map?.[publicationLookupKey(title)];
 if(typeof matched==='string'&&matched.trim())return matched.trim();
 const acronym=/\(([A-Z][A-Z0-9-]{1,12})\)\s*$/u.exec(title);
 if(acronym)return acronym[1];
 const key=title.toLowerCase().replace(/&/gu,'and').replace(/[–—]/gu,' ').replace(/[^a-z0-9]+/gu,' ').trim();
 for(const [needle,short] of fallbackRules)if(key.includes(needle))return short;
}
