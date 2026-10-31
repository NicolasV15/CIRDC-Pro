import type {CitationRecord} from './citations';
export type SelectedPaper={number:string;title:string;year?:number;kind?:string;venue?:string;venue_series?:string[];publication?:string};
export type BatchResource={id:string;href:string;media_type?:string;archive_prepare_href?:string;reader_href?:string;kind?:string};
export type StoredPaper={number:string;record:CitationRecord&{publicationNumber?:string|number};venue_series?:string[];resources?:BatchResource[];resource_notice?:string};
export type LoadedPaper={number:string;paper:StoredPaper};
export type BatchFailure={number:string;message:string};
/** Three bounded readers preserve selection order without mounting any document viewer. */
export async function loadPapers(numbers:string[],fetcher:(path:string)=>Promise<any>,progress:(done:number)=>void=()=>{},cancelled:()=>boolean=()=>false){
 const ids=[...new Set(numbers)],results=new Map<string,LoadedPaper>(),errors=new Map<string,BatchFailure>();let cursor=0,done=0;
 await Promise.all(Array.from({length:Math.min(3,ids.length)},async()=>{
  while(!cancelled()){
   const number=ids[cursor++];if(!number)return;
   try{const value=await fetcher('/api/papers/'+encodeURIComponent(number));if(!value.paper?.record)throw new Error('未找到记录。');results.set(number,{number,paper:value.paper});}
   catch(error){errors.set(number,{number,message:error instanceof Error?error.message:'操作暂时无法完成，请稍后重试。'});}
   finally{done++;if(!cancelled())progress(done);}
  }
 }));
 return {items:ids.flatMap(n=>results.has(n)?[results.get(n)!]:[]),failures:ids.flatMap(n=>errors.has(n)?[errors.get(n)!]:[])};
}
