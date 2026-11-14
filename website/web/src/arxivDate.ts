/** Stable calendar date in UTC, independent of browser language or timezone. */
export function arxivDate(value?:string|null,missing='—'){
 if(!value)return missing;
 const parsed=new Date(value);
 return Number.isNaN(parsed.getTime())?value:parsed.toISOString().slice(0,10);
}
