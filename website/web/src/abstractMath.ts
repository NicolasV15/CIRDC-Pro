import {titleParts,type TitlePart} from './titleMath.ts';

/** Keep only explicit source math and safe semantic sub/sup markup. */
export function abstractParts(value:unknown){return titleParts(value,true,true);}

export function abstractUnits(parts:TitlePart[]){
 return parts.reduce((size,part)=>size+(part.type==='math'?1:Array.from(part.value).length),0);
}

/** A collapsed excerpt can cut text, but a source formula is always atomic. */
export function abstractPrefix(parts:TitlePart[],limit:number):TitlePart[]{
 const result:TitlePart[]=[];let remaining=Math.max(0,Math.floor(limit));
 for(const part of parts){
  if(!remaining)break;
  if(part.type==='math'){result.push(part);remaining--;}
  else{
   const characters=Array.from(part.value),value=characters.slice(0,remaining).join('');
   if(value)result.push({...part,value});
   remaining-=Math.min(remaining,characters.length);
  }
 }
 return result;
}
