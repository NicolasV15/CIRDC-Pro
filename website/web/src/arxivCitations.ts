import type {CitationRecord} from './citations';
import {decodeTexAccents,decodeTexAccentsOutsideMath} from './texAccents.ts';
type Paper={arxiv_id:string;title:string;authors_raw?:string;metadata?:Record<string,any>;versions?:{version:number;version_date?:string}[]};
/** List and detail citations share the same explicit arXiv version identity. */
export function arxivCitationRecord(paper:Paper,version:number):CitationRecord{
 const metadata=paper.metadata||{},selected=paper.versions?.find(v=>v.version===version);
 if(!selected)throw Error('unknown_arxiv_version');
 const date=selected.version_date||metadata.submitted_at||'',year=date?Number(date.slice(0,4)):undefined;
 let authors=(metadata.authors_structured||[]).map((a:any)=>Array.isArray(a)?{lastName:a[0],firstName:a[1]}:a.keyname?{lastName:a.keyname,firstName:a.forenames}:{preferredName:a.name||''});
 if(!authors.length&&paper.authors_raw)authors=[{preferredName:decodeTexAccents(paper.authors_raw)}];
 return {source:'arxiv',sourceId:paper.arxiv_id,sourceVersion:version,articleTitle:decodeTexAccentsOutsideMath(paper.title),authors,publicationTitle:'arXiv:'+paper.arxiv_id+'v'+version,articleContentType:'Preprint',publicationYear:year,publicationDate:date.slice(0,10),doi:/^10\.48550\//i.test(metadata.doi||'')?metadata.doi:undefined};
}
