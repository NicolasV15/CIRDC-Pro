export type SearchOptions={q:string;field:string;sort:string;view:string;k:string;terms:string};
type Translate=(text:string,values?:Record<string,string>)=>string;
/** Labels for the search choices that differ from the page defaults, in display order; empty when all are defaults. */
export function changedSearchOptions(value:SearchOptions,fields:[string,string][],defaultSort:string,sortLabel:(sort:string)=>string,t:Translate){
 return [
  ...(value.field&&value.field!==fields[0]?.[0]?[fields.find(([field])=>field===value.field)?.[1]||value.field]:[]),
  ...(value.view==='top'?[t('最相关')+' · '+t('前 {k} 篇',{k:value.k||'20'})]:value.sort&&value.sort!==defaultSort?[sortLabel(value.sort)]:[]),
  ...(value.terms==='exact'?[t('仅原写法')]:[]),
 ];
}
