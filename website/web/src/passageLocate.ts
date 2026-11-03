/** Reader-side passage identity. Mirrors cirdc/web/fulltext.py so an indexed ordinal
 * and its fingerprint can be checked against the document that is actually displayed. */
const TOKEN=/[\p{L}\p{N}]+/gu;
const CONTAINERS=new Set(['P','LI','BLOCKQUOTE','FIGCAPTION','CAPTION','DT','DD','PRE','TR','H1','H2','H3','H4','H5','H6','DIV','SECTION','ARTICLE','FIGURE']);
const SEPARATED=new Set(['TD','TH','BR','TR','LI','DT','DD','P','DIV','SECTION','ARTICLE','FIGURE','FIGCAPTION','CAPTION','PRE','BLOCKQUOTE','TABLE','TBODY','THEAD','TFOOT','UL','OL','DL','H1','H2','H3','H4','H5','H6']);
const SKIPPED='.document-math-source,.document-section-number,script,style';
export const FORMULA=' ⋯ ';

// Lower-casing is context sensitive for Greek final sigma; the index folds every sigma to σ.
export function fold(value:string){return value.normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase().replace(/ς/g,'σ');}
export function textTokens(text:string){return Array.from(text.normalize('NFKC').matchAll(TOKEN),match=>fold(match[0]));}
export function fingerprintOf(text:string){return textTokens(text).slice(0,12).join(' ');}

/** Character ranges where any alternative token sequence occurs. */
export function matchRanges(text:string,alternatives:string[][]):[number,number][]{
 const spans=Array.from(text.matchAll(TOKEN),match=>({start:match.index!,end:match.index!+match[0].length,key:fold(match[0].normalize('NFKC'))}));
 const ranges:[number,number][]=[];
 for(const alternative of alternatives){
  if(!alternative.length)continue;
  for(let start=0;start+alternative.length<=spans.length;start++){
   if(alternative.every((token,index)=>spans[start+index].key===token))ranges.push([spans[start].start,spans[start+alternative.length-1].end]);
  }
 }
 return ranges.sort((a,b)=>a[0]-b[0]);
}

/** The closest block to the indexed ordinal whose leading words still match. */
export function findPassage(texts:string[],ordinal:number,fingerprint:string){
 const matches=(index:number)=>index>=0&&index<texts.length&&fingerprintOf(texts[index])===fingerprint;
 if(matches(ordinal))return ordinal;
 for(let distance=1;distance<texts.length;distance++){
  if(matches(ordinal-distance))return ordinal-distance;
  if(matches(ordinal+distance))return ordinal+distance;
 }
 return -1;
}

type Piece={node:Text;start:number};
function collect(element:Element){
 let text='';const pieces:Piece[]=[];
 const walk=(node:Node)=>{
  if(node.nodeType===Node.TEXT_NODE){pieces.push({node:node as Text,start:text.length});text+=node.textContent||'';return;}
  if(!(node instanceof Element))return;
  if(node.classList.contains('doc-math')){text+=FORMULA;return;}
  if(node.matches(SKIPPED))return;
  for(const child of Array.from(node.childNodes)){if(child instanceof Element&&SEPARATED.has(child.tagName))text+=' ';walk(child);}
 };
 walk(element);
 return {text,pieces};
}
export function blockText(element:Element){return collect(element).text.replace(/\s+/g,' ').trim();}

export function passageBlocks(root:Element){
 const inside=(element:Element)=>!!element.parentElement?.closest('.doc-math,.document-math-source')||element.matches('.doc-math,.document-math-source');
 const candidates=Array.from(root.querySelectorAll('*')).filter(element=>CONTAINERS.has(element.tagName)&&!inside(element));
 const outer=new Set<Element>();
 for(const element of candidates){let parent=element.parentElement;while(parent&&parent!==root&&!outer.has(parent)){outer.add(parent);parent=parent.parentElement;}}
 return candidates.filter(element=>!outer.has(element)&&textTokens(blockText(element)).length>0);
}

/** DOM ranges for highlighting matches inside one block, without changing its markup. */
export function blockRanges(element:Element,alternatives:string[][]){
 const {text,pieces}=collect(element),result:Range[]=[];
 const point=(offset:number,end:boolean)=>{
  for(let index=pieces.length-1;index>=0;index--){
   const piece=pieces[index],length=piece.node.textContent?.length||0;
   if(offset>piece.start||(!end&&offset===piece.start))return {node:piece.node,offset:Math.min(length,offset-piece.start)};
  }
  return null;
 };
 for(const [start,end] of matchRanges(text,alternatives)){
  const from=point(start,false),to=point(end,true);
  if(!from||!to)continue;
  const range=element.ownerDocument.createRange();
  try{range.setStart(from.node,from.offset);range.setEnd(to.node,to.offset);result.push(range);}catch{/* A range crossing removed nodes is skipped. */}
 }
 return result;
}

export type PassageFocus={ordinal:number;version:string|null;fingerprint:string;alternatives:string[][];token:number};
export type FocusResult={status:'located'|'relocated'|'missing';version:string|null};
