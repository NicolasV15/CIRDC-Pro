/** Stable calendar date in fixed UTC+8, independent of browser language or timezone. */
export function arxivDate(value?:string|null,missing='—'){
 if(!value)return missing;
 const parsed=new Date(value);
 return Number.isNaN(parsed.getTime())?value:new Date(parsed.getTime()+8*60*60*1000).toISOString().slice(0,10);
}
