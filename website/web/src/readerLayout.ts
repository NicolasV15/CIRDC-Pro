export type ReaderLayout={pageWidth:number;tocWidth:number;infoWidth:number;infoOpen:boolean;fontScale:number};
export const readerLayoutPreference='cirdc.reader.layout.v1';
export const readerLayoutDefaults:Readonly<ReaderLayout>=Object.freeze({pageWidth:2000,tocWidth:200,infoWidth:220,infoOpen:true,fontScale:100});
export const readerLayoutRanges={fontScale:{min:80,max:150,step:5},pageWidth:{min:1280,max:2200,step:40},tocWidth:{min:180,max:280,step:10},infoWidth:{min:180,max:280,step:10}} as const;
export function normalizeReaderLayout(value:unknown):ReaderLayout{
 const input=value&&typeof value==='object'&&!Array.isArray(value)?value as Partial<ReaderLayout>:{};
 const result={...readerLayoutDefaults};
 for(const key of ['fontScale','pageWidth','tocWidth','infoWidth'] as const){
  const n=input[key],range=readerLayoutRanges[key];
  if(typeof n==='number'&&Number.isFinite(n))result[key]=Math.max(range.min,Math.min(range.max,range.min+Math.round((n-range.min)/range.step)*range.step));
 }
 if(typeof input.infoOpen==='boolean')result.infoOpen=input.infoOpen;
 return result;
}
export function loadReaderLayout():ReaderLayout{
 try{return normalizeReaderLayout(JSON.parse(localStorage.getItem(readerLayoutPreference)||'null'));}catch{return {...readerLayoutDefaults};}
}
