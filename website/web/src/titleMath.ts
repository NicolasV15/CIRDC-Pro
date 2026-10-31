import {citationText,decodeTextEntities} from './citations.ts';

export type TitlePart={type:'text';value:string}|{type:'math';value:string;raw:string};
const delimiters=[['$$','$$'],['\\(','\\)'],['\\[','\\]'],['$','$']] as const;
function endOfMath(source:string,start:number,right:string){
 let braces=0;
 for(let i=start;i<source.length;i++){
  if(braces<=0&&source.startsWith(right,i)&&(right!=='$'||!/[0-9]/.test(source[i+1]||'')))return i;
  if(source[i]==='\\')i++;
  else if(source[i]==='{')braces++;
  else if(source[i]==='}')braces--;
 }
 return -1;
}

/** Split explicit source math only; ordinary text never becomes executable HTML. */
export function titleParts(value:unknown):TitlePart[]{
 if(typeof value!=='string')return [];
 const source=value.replace(/<tex-math\b[^>]*>([\s\S]*?)<\/tex-math\s*>/gi,(_,text:string)=>{
  const tex=text.replace(/^\s*<!\[CDATA\[|\]\]>\s*$/g,'').trim();
  return delimiters.some(([left,right])=>tex.startsWith(left)&&tex.endsWith(right))?tex:'\\('+tex+'\\)';
 }).trim(),parts:TitlePart[]=[];
 const plain=(text:string)=>{const value=citationText(text,false).replace(/\\\$/g,'$');if(value)parts.push({type:'text',value});};
 let start=0,index=0;
 while(index<source.length){
  const pair=delimiters.find(([left])=>source.startsWith(left,index));
  if(pair){
   const end=endOfMath(source,index+pair[0].length,pair[1]);
   if(end>=0&&source.slice(index+pair[0].length,end).trim()){
    plain(source.slice(start,index));const next=end+pair[1].length;
    parts.push({type:'math',value:decodeTextEntities(source.slice(index+pair[0].length,end)),raw:decodeTextEntities(source.slice(index,next))});
    index=next;start=next;continue;
   }
  }
  index+=source[index]==='\\'?2:1;
 }
 plain(source.slice(start));
 return parts;
}
