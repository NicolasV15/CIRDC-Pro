import {createElement,Fragment,useMemo} from 'react';
import ScientificTitle from './ScientificTitle';
import {abstractParts} from './abstractMath';
import type {TitlePart} from './titleMath';

export function AbstractPartContent({part}:{part:TitlePart}){
 const content=part.type==='math'?<ScientificTitle value={part.raw}/>:part.value;
 return part.script?createElement(part.script,null,content):content;
}

export default function AbstractText({value,fallback=''}:{value:unknown;fallback?:string}){
 const parts=useMemo(()=>abstractParts(value),[value]);
 return <>{parts.length?parts.map((part,index)=><Fragment key={index}><AbstractPartContent part={part}/></Fragment>):fallback}</>;
}
