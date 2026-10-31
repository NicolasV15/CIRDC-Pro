import {lazy,Suspense,useMemo} from 'react';
import {titleParts} from './titleMath';

const TitleFormula=lazy(()=>import('./TitleFormula'));
export default function ScientificTitle({value,fallback=''}:{value:unknown;fallback?:string}){
 const parts=useMemo(()=>titleParts(value),[value]);
 return <span className="scientific-title">{parts.length?parts.map((part,index)=>part.type==='text'?part.value:<Suspense key={index} fallback={part.raw}><TitleFormula tex={part.value} raw={part.raw}/></Suspense>):fallback}</span>;
}
