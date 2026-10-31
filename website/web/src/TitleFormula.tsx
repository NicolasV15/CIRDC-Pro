import {useMemo} from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

export default function TitleFormula({tex,raw}:{tex:string;raw:string}){
 const html=useMemo(()=>{
  if(tex.length>8192)return;
  try{return katex.renderToString(tex,{displayMode:false,throwOnError:true,trust:false,strict:'ignore',output:'htmlAndMathml',maxExpand:1000,maxSize:10,macros:{}});}catch{return;}
 },[tex]);
 return html?<span className="scientific-title-math" dangerouslySetInnerHTML={{__html:html}}/>:<span className="scientific-title-fallback">{raw}</span>;
}
