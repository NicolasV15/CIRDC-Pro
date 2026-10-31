export type CitationStyle = 'bibtex' | 'ieee' | 'gbt2025';
type Author = {firstName?: string; lastName?: string; preferredName?: string; name?: string};
export type CitationRecord = {
 articleTitle?: string; authors?: Author[]; articleContentType?: string;
 publicationTitle?: string; publicationYear?: string | number; publicationDate?: string;
 volume?: string | number; issue?: string | number; startPage?: string | number;
 endPage?: string | number; doi?: string; publisher?: string;
};

const entities: Record<string, string> = {amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' ',mu:'μ',micro:'µ',deg:'°',times:'×',minus:'−',plusmn:'±',alpha:'α',beta:'β',gamma:'γ',Delta:'Δ',Omega:'Ω',pi:'π',sigma:'σ'};
export function decodeTextEntities(value:string):string {
 return value.replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi,(original,key:string)=>{
   if(key[0]!=='#')return entities[key] ?? original;
   const number=key[1]?.toLowerCase()==='x'?parseInt(key.slice(2),16):parseInt(key.slice(1),10);
   return number>0&&number<=0x10ffff&&!(number>=0xd800&&number<=0xdfff)?String.fromCodePoint(number):original;
  });
}
export function citationText(value: unknown,trim=true): string {
 const text=decodeTextEntities((typeof value === 'string' || typeof value === 'number' ? String(value) : '')
  .replace(/<\/?[a-z][\w:.-]*(?:\s[^<>]*?)?\s*\/?>/gi,'')).replace(/[\s\u0000-\u001f]+/g,' ');
 return trim?text.trim():text;
}
function tex(value: string): string {
 const replacements: Record<string,string> = {'\\':'\\textbackslash{}','{':'\\{','}':'\\}','%':'\\%','&':'\\&','#':'\\#','_':'\\_','$':'\\$','~':'\\textasciitilde{}','^':'\\textasciicircum{}','μ':'\\ensuremath{\\mu}','µ':'\\ensuremath{\\mu}','°':'\\ensuremath{^{\\circ}}','Ω':'\\ensuremath{\\Omega}','Δ':'\\ensuremath{\\Delta}','α':'\\ensuremath{\\alpha}','β':'\\ensuremath{\\beta}','γ':'\\ensuremath{\\gamma}','π':'\\ensuremath{\\pi}','σ':'\\ensuremath{\\sigma}','×':'\\ensuremath{\\times}','±':'\\ensuremath{\\pm}','−':'-','<':'\\textless{}','>':'\\textgreater{}','≤':'\\ensuremath{\\leq}','≥':'\\ensuremath{\\geq}'};
 return [...value].map(char=>replacements[char] ?? char).join('');
}
function initials(given: string): string {
 return given.split(/\s+/).filter(Boolean).map(word=>word.split('-').map(part=>part.split('.').filter(Boolean).map(piece=>[...piece][0]+'.').join('')).join('-')).join(' ');
}
function names(record: CitationRecord) {
 return (Array.isArray(record.authors)?record.authors:[]).map(author=>{
  const first=citationText(author?.firstName),last=citationText(author?.lastName);
  const full=citationText(author?.preferredName || author?.name) || [first,last].filter(Boolean).join(' ');
  return {first,last,full};
 }).filter(author=>author.full);
}
function yearOf(record: CitationRecord) {
 const year=citationText(record.publicationYear);
 return /^\d{4}$/.test(year)?year:'';
}
function earlyDate(raw: unknown,year: string): string {
 const value=citationText(raw);
 const iso=value.match(/^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/);
 const months=['Jan.','Feb.','Mar.','Apr.','May','Jun.','Jul.','Aug.','Sep.','Oct.','Nov.','Dec.'];
 if(iso&&+iso[2]>=1&&+iso[2]<=12&&+iso[3]>=1&&+iso[3]<=31)return `${months[+iso[2]-1]} ${+iso[3]}, ${iso[1]}`;
 return value || year;
}
export function localCitationDate(date=new Date()): string {
 return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
}

/** Format only the available source metadata; Xplore document IDs are not publisher article numbers. */
export function buildCitations(record: CitationRecord,number: string,accessed=localCitationDate()) {
 if(!/^\d{1,64}$/.test(number))throw new Error('Invalid article number');
 const title=citationText(record.articleTitle),publication=citationText(record.publicationTitle),authors=names(record),year=yearOf(record);
 const kind=citationText(record.articleContentType),conference=kind==='Conferences';
 const early=/early\s*access/i.test(kind)||/^PP$/i.test(citationText(record.volume));
 const volume=early?'':citationText(record.volume),issue=early?'':citationText(record.issue);
 const start=early?'':citationText(record.startPage),end=early?'':citationText(record.endPage);
 const pages=start ? start+(end&&end!==start?'–'+end:'') : '';
 const candidate=citationText(record.doi).replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i,'');
 const doi=/^10\.\d+\/\S+$/.test(candidate)?candidate:'';
 const url=doi?'https://doi.org/'+doi:'https://ieeexplore.ieee.org/document/'+number;
 const missing: string[]=[];
 if(!title)missing.push('title');if(!authors.length)missing.push('authors');if(!publication)missing.push('publication');if(!year)missing.push('year');
 if(early&&!citationText(record.publicationDate))missing.push('online_date');

 const bibType=conference?'inproceedings':/^(Journals|Magazines|Early Access Articles)$/i.test(kind)||early?'article':'misc';
 const fields: [string,string][]=[];
 if(authors.length)fields.push(['author',authors.map(author=>author.first&&author.last?tex(author.last)+', '+tex(author.first):'{'+tex(author.full)+'}').join(' and ')]);
 if(title)fields.push(['title','{'+tex(title)+'}']);
 if(publication)fields.push([conference?'booktitle':bibType==='article'?'journal':'howpublished',tex(publication)]);
 if(year)fields.push(['year',year]);if(volume)fields.push(['volume',tex(volume)]);if(issue)fields.push(['number',tex(issue)]);
 if(pages)fields.push(['pages',tex(pages.replace('–','--'))]);
 if(conference&&citationText(record.publisher))fields.push(['publisher',tex(citationText(record.publisher))]);
 if(early)fields.push(['note','Early Access']);if(doi)fields.push(['doi',tex(doi)]);fields.push(['url',tex(url)]);
 const bibtex=`@${bibType}{ieee${number},\n`+fields.map(([key,value])=>`  ${key} = {${value}}`).join(',\n')+'\n}';

 const ieeeNames=authors.map(author=>author.first&&author.last?initials(author.first)+' '+author.last:author.full);
 const ieeeAuthors=ieeeNames.length>6?ieeeNames[0]+' et al.':ieeeNames.length>1?ieeeNames.slice(0,-1).join(', ')+(ieeeNames.length>2?', and ':' and ')+ieeeNames.at(-1):ieeeNames[0]||'';
 const ieeeParts=[publication?(conference?'in ':'')+publication:''];
 if(early)ieeeParts.push('early access');
 if(volume)ieeeParts.push('vol. '+volume);if(issue)ieeeParts.push('no. '+issue);
 if(pages)ieeeParts.push((start===end||!end?'p. ':'pp. ')+pages);
 const date=early?earlyDate(record.publicationDate,year):conference?year:citationText(record.publicationDate)||year;
 if(date)ieeeParts.push(date);
 const ieee=(ieeeAuthors?ieeeAuthors+', ':'')+(title?'“'+title+',” ':'')+ieeeParts.filter(Boolean).join(', ')+(doi?', doi: '+doi+'.':'. [Online]. Available: '+url);

 const gbtNames=authors.slice(0,3).map(author=>author.first&&author.last?author.last.toUpperCase()+' '+initials(author.first).replace(/[.-]/g,' ').replace(/\s+/g,' ').trim():author.full);
 if(authors.length>3)gbtNames.push('et al.');
 let gbt=gbtNames.length?gbtNames.join(', ')+'. ':'';
 if(title)gbt+=title;
 gbt+=conference?'[C]//':early?'[J/OL]. ':'[J]. ';
 gbt+=publication;
 if(year)gbt+=(publication?', ':'')+year;
 if(volume)gbt+=', '+volume;if(issue)gbt+='('+issue+')';if(pages)gbt+=': '+pages;
 if(early&&/^\d{4}-\d{2}-\d{2}$/.test(accessed))gbt+='['+accessed+']';
 gbt+='.';
 if(doi)gbt+=' DOI: '+doi+'.';else if(early||!publication)gbt+=' '+url;
 return {values:{bibtex,ieee,gbt2025:gbt},missing,earlyAccess:early,unstructuredAuthors:authors.some(author=>!author.first||!author.last)};
}
