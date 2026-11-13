type Fetcher=(path:string,method?:string,data?:unknown)=>Promise<any>;
export type CitationActivity={busy:boolean;disabled:boolean};

export function createCitationUpdates(number:string,fetcher:Fetcher){
 const paper='/api/papers/'+encodeURIComponent(number)+'/citations',patent='/api/papers/'+encodeURIComponent(number)+'/patent-citations';
 const states:{papers?:any;patents?:any}={},known=new Set<string>(),requests=new Map<string,Promise<any>>();
 let ready!:()=>void;const initial=new Promise<void>(resolve=>{ready=resolve});
 function received(kind:'papers'|'patents',value:any){states[kind]=value;known.add(kind);if(known.size===2)ready();}
 const wrapped:Fetcher=async(path,method='GET',data)=>{
  const base=path.split('?')[0],kind=base===paper?'papers':base===patent?'patents':undefined;
  if(method==='GET'&&kind){
   const query=new URLSearchParams(path.split('?')[1]||'');
   const overview=(!query.has('offset')||query.get('offset')==='0')&&(kind!=='papers'||!query.has('group')||query.get('group')==='ieee');
   try{const value=await fetcher(path,method,data);if(overview)received(kind,value);return value;}
   catch(error){if(overview)received(kind,undefined);throw error;}
  }
  if(method!=='POST'||![paper+'/ensure',patent+'/ensure'].includes(path))return fetcher(path,method,data);
  await initial;
  const refresh=!!(data as {refresh?:boolean}|undefined)?.refresh,key=refresh?'update':'open';
  if(!requests.has(key))requests.set(key,(async()=>{
   if(states.papers?.state==='disabled')return {papers:states.papers,patents:await fetcher(patent+'/ensure','POST',data)};
   if(states.patents?.state==='disabled')return {papers:await fetcher(paper+'/ensure','POST',data),patents:states.patents};
   return fetcher(paper+'/ensure','POST',{refresh,include_patents:true});
  })());
  const result=await requests.get(key)!;
  const value=path===paper+'/ensure'?result.papers:result.patents;
  if(!value)throw Error('Invalid joint citation response');
  received(path===paper+'/ensure'?'papers':'patents',value);return value;
 };
 return {fetcher:wrapped,beginUpdate:()=>requests.delete('update')};
}
