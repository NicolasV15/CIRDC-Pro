import {titleParts} from './titleMath';
import {formatSelection,unwrappedMath,type CopyNode,type CopyWarning} from './selectionFormats';

const mathSelector='[data-copy-tex],.doc-math,.scientific-title-math,.scientific-title-fallback';
const ignoreSelector='[data-copy-ui],[data-copy-ignore],[hidden],[aria-hidden="true"],button,input,textarea,select,option,script,style,nav,summary,svg,.abstract-measure,.abstract-source,.abstract-tail,.metadata-maintenance,.document-progress,.reader-layout-controls,.detail-toolbar,.detail-record-toolbar,.paper-selection-control,.paper-meta,.citation-snapshot-meta';
const blockTags=new Set(['p','div','section','article','figure','figcaption','caption','blockquote','pre','ul','ol','li','table','thead','tbody','tfoot','tr','td','th','h1','h2','h3','h4','h5','h6']);
const elementOf=(node:Node)=>node.nodeType===Node.ELEMENT_NODE?node as HTMLElement:node.parentElement;
function ignored(el:Element|null){
 if(!el)return false;
 if(el.closest(ignoreSelector)||el.closest('details:not([open])'))return true;
 if(el.isConnected){const style=getComputedStyle(el);if(style.display==='none'||style.visibility==='hidden')return true;}
 return false;
}
function mathRoot(node:Node){const el=elementOf(node);return el?.closest<HTMLElement>(mathSelector)||el?.closest<HTMLElement>('.katex')||null;}
type Point={node:Node;offset:number};
function compare(a:Point,b:Point){const r=a.node.ownerDocument!.createRange(),s=b.node.ownerDocument!.createRange();r.setStart(a.node,a.offset);r.collapse(true);s.setStart(b.node,b.offset);s.collapse(true);return r.compareBoundaryPoints(Range.START_TO_START,s);}
function boundaries(node:Node){const range=node.ownerDocument!.createRange();range.selectNodeContents(node);return {start:{node:range.startContainer,offset:range.startOffset},end:{node:range.endContainer,offset:range.endOffset}};}
function overlaps(range:Range,node:Node){
 const points=boundaries(node);
 return compare({node:range.endContainer,offset:range.endOffset},points.start)>0&&compare({node:range.startContainer,offset:range.startOffset},points.end)<0;
}
export function normalizedCopyRange(original:Range){
 const range=original.cloneRange(),start=mathRoot(range.startContainer),end=mathRoot(range.endContainer);
 if(start&&overlaps(original,start))range.setStartBefore(start);
 if(end&&overlaps(original,end))range.setEndAfter(end);
 return range;
}
function mathValue(el:Element):{tex:string;display:boolean;raw:string}|undefined{
 const explicit=el.getAttribute('data-copy-tex');
 const annotation=el.querySelector('annotation[encoding="application/x-tex"]');
 const error=el.querySelector('.katex-error');
 const content=explicit??annotation?.textContent??error?.textContent??(el.matches('.doc-math,tex-math')?el.textContent:null);
 if(content===null||content===undefined)return;
 const display=el.getAttribute('data-copy-display')==='block'||el.getAttribute('data-display')==='1'||!!el.querySelector('.katex-display')||content.startsWith('\\[')||content.startsWith('$$');
 const tex=unwrappedMath(content);
 return {tex,display,raw:el.getAttribute('data-copy-raw')??(display?'\\['+tex+'\\]':'\\('+tex+'\\)')};
}
function safeHref(value:string|null,pageURL:string){
 if(!value)return '';
 try{const u=new URL(value,pageURL);return ['http:','https:','mailto:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}
}
function logicalText(node:Node):string{
 if(node.nodeType===Node.TEXT_NODE)return node.textContent||'';
 if(node.nodeType!==Node.ELEMENT_NODE&&node.nodeType!==Node.DOCUMENT_FRAGMENT_NODE)return '';
 if(node.nodeType===Node.ELEMENT_NODE){const el=node as Element;if(ignored(el))return '';if(el.matches(mathSelector+',.katex,tex-math'))return mathValue(el)?.raw||'';}
 return Array.from(node.childNodes).map(logicalText).join('');
}
function offsetAt(root:Element,point:Point){
 const {start,end}=boundaries(root);if(compare(point,start)<=0)return 0;if(compare(point,end)>=0)return logicalText(root).length;
 const prefix=root.ownerDocument.createRange();prefix.selectNodeContents(root);prefix.setEnd(point.node,point.offset);return logicalText(prefix.cloneContents()).length;
}
function sourcePoint(root:Element,offset:number,end:boolean):Point{
 let remaining=offset,result:Point|undefined;
 function visit(node:Node):boolean{
  if(node.nodeType===Node.TEXT_NODE){const size=node.textContent?.length||0;if(remaining<=size){result={node,offset:remaining};return true;}remaining-=size;return false;}
  if(node.nodeType!==Node.ELEMENT_NODE)return false;
  const el=node as Element;if(ignored(el))return false;
  if(el.matches(mathSelector+',.katex,tex-math')){
   const size=mathValue(el)?.raw.length||0;
   if(remaining<=size){const parent=el.parentNode!,index=Array.prototype.indexOf.call(parent.childNodes,el);result={node:parent,offset:index+(remaining===0?0:remaining===size?1:end?1:0)};return true;}
   remaining-=size;return false;
  }
  return Array.from(node.childNodes).some(visit);
 }
 Array.from(root.childNodes).some(visit);return result||{node:root,offset:root.childNodes.length};
}
function prepareSource(root:Element,mode:string){
 for(const el of Array.from(root.querySelectorAll('script,style,iframe,object,embed,button,input,select,textarea')))el.remove();
 for(const el of Array.from(root.querySelectorAll('tex-math'))){const tex=unwrappedMath(el.textContent||'');el.setAttribute('data-copy-tex',tex);el.setAttribute('data-copy-raw','\\('+tex+'\\)');el.setAttribute('data-copy-display',el.getAttribute('data-display')==='1'?'block':'inline');}
 const walker=root.ownerDocument.createTreeWalker(root,NodeFilter.SHOW_TEXT),texts:Text[]=[];let value:Node|null;
 while(value=walker.nextNode())if(!elementOf(value)?.closest('[data-copy-tex],code,pre'))texts.push(value as Text);
 for(const node of texts){
  const value=node.data,parts=titleParts(value,true);
  if(!parts.some(part=>part.type==='math')){if(mode==='normalized')node.data=value.replace(/\s+/g,' ');continue;}
  const fragment=root.ownerDocument.createDocumentFragment();
  // titleParts trims its whole input; these are individual DOM text nodes, so
  // whitespace next to formatting tags is still part of the displayed content.
  const leading=value.match(/^\s+/)?.[0],trailing=value.match(/\s+$/)?.[0];
  if(leading)fragment.append(root.ownerDocument.createTextNode(mode==='normalized'?' ':leading));
  for(const part of parts){if(part.type==='text')fragment.append(root.ownerDocument.createTextNode(mode==='normalized'?part.value.replace(/\s+/g,' '):part.value));else{const span=root.ownerDocument.createElement('span');span.setAttribute('data-copy-tex',part.value);span.setAttribute('data-copy-raw',part.raw);span.setAttribute('data-copy-display',part.raw.startsWith('$$')||part.raw.startsWith('\\[')?'block':'inline');span.textContent=part.raw;fragment.append(span);}}
  if(trailing)fragment.append(root.ownerDocument.createTextNode(mode==='normalized'?' ':trailing));
  node.replaceWith(fragment);
 }
}
function visibleEdge(node:Node,last:boolean):Point|undefined{
 if(node.nodeType===Node.TEXT_NODE){const text=node.textContent||'';if(!text.trim())return;return {node,offset:last?text.trimEnd().length:text.length-text.trimStart().length};}
 if(node.nodeType!==Node.ELEMENT_NODE)return;
 const el=node as Element;if(ignored(el))return;
 if(el.matches(mathSelector+',.katex,img')){const p=el.parentNode!,i=Array.prototype.indexOf.call(p.childNodes,el);return {node:p,offset:i+(last?1:0)};}
 const children=Array.from(el.childNodes);if(last)children.reverse();for(const child of children){const point=visibleEdge(child,last);if(point)return point;}
}

export function captureSelection(original:Range,scope:HTMLElement,pageURL=location.href){
 if(!original.startContainer.isConnected||!original.endContainer.isConnected)throw Error('selection_expired');
 const range=normalizedCopyRange(original),warnings=new Set<CopyWarning>();
 function wrap(el:Element,children:CopyNode[],selected:Range):CopyNode[]{
  if(ignored(el))return [];
  const tag=el.tagName.toLowerCase();if(!children.length&&tag!=='br')return [];
  const node:Extract<CopyNode,{kind:'element'}>={kind:'element',tag,children};
  if(tag==='a'){node.href=safeHref(el.getAttribute('href'),pageURL);if(el.hasAttribute('href')&&!node.href)warnings.add('link-omitted');}
  if(tag==='ol'){
   const entries=Array.from(el.children).filter(n=>n.tagName==='LI'),first=entries.findIndex(n=>selected.intersectsNode(n));node.start=(Number(el.getAttribute('start'))||1)+Math.max(0,first);
  }
  if(tag==='table'){
   const rows=Array.from(el.querySelectorAll('tr')).filter(row=>row.closest('table')===el),first=rows[0]&&visibleEdge(rows[0],false),last=rows.at(-1)&&visibleEdge(rows.at(-1)!,true);
   node.complete=!!first&&!!last&&compare({node:selected.startContainer,offset:selected.startOffset},first)<=0&&compare({node:selected.endContainer,offset:selected.endOffset},last)>=0;
   node.simple=!el.querySelector('table')&&Array.from(el.querySelectorAll('td,th')).every(cell=>['rowspan','colspan'].every(key=>!cell.hasAttribute(key)||Number(cell.getAttribute(key))===1));
  }
  return [node];
 }
 function mapped(el:HTMLElement,selected:Range):CopyNode[]|undefined{
  const raw=el.getAttribute('data-copy-source-html');if(raw===null)return;
  const template=el.ownerDocument.createElement('template');
  // Protect XML TeX (including CDATA and its original delimiters) before the
  // HTML parser can interpret comparison symbols or XML nodes as markup.
  template.innerHTML=raw.replace(/<tex-math\b[^>]*>[\s\S]*?<\/tex-math\s*>/gi,source=>{
   const part=titleParts(source,true).find(part=>part.type==='math');if(!part||part.type!=='math')return '';
   const math=el.ownerDocument.createElement('span');math.setAttribute('data-copy-tex',part.value);math.setAttribute('data-copy-raw',part.raw);math.setAttribute('data-copy-display',part.raw.startsWith('$$')||part.raw.startsWith('\\[')?'block':'inline');math.textContent=part.raw;return math.outerHTML;
  });
  // Source metadata stays inert: even detached images must not start network requests.
  for(const node of template.content.querySelectorAll('img,iframe,link,script,style,source,video,audio,object,embed'))node.remove();
  const source=el.ownerDocument.createElement('div');source.append(template.content);
  prepareSource(source,el.getAttribute('data-copy-source-mode')||'literal');
  const displayed=logicalText(el),semantic=logicalText(source),prefix=el.getAttribute('data-copy-source-mode')==='prefix';
  if(!(semantic===displayed||(prefix&&semantic.startsWith(displayed)))){warnings.add('source-unmapped');return;}
  const start=offsetAt(el,{node:selected.startContainer,offset:selected.startOffset}),end=offsetAt(el,{node:selected.endContainer,offset:selected.endOffset});
  const a=sourcePoint(source,start,false),b=sourcePoint(source,end,true),sourceRange=source.ownerDocument.createRange();sourceRange.setStart(a.node,a.offset);sourceRange.setEnd(b.node,b.offset);
  return Array.from(source.childNodes).flatMap(child=>walk(child,sourceRange,true));
 }
 function walk(node:Node,selected:Range,source=false):CopyNode[]{
  if(!selected.intersectsNode(node))return [];
  if(node.nodeType===Node.TEXT_NODE){
   const parent=node.parentElement;if(ignored(parent))return [];
   const text=node.textContent||'',start=selected.startContainer===node?selected.startOffset:0,end=selected.endContainer===node?selected.endOffset:text.length,value=text.slice(start,end);
   if(!value)return [];
   if(!value.trim()&&parent&&blockTags.has(parent.tagName.toLowerCase())&&Array.from(parent.children).some(n=>blockTags.has(n.tagName.toLowerCase())))return [];
   if(parent?.matches('[data-copy-preserve-lines]'))return value.split('\n').flatMap((part,i)=>[...(i?[{kind:'element' as const,tag:'br',children:[]}]:[]),...(part?[{kind:'text' as const,value:part}]:[])]);
   return [{kind:'text',value}];
  }
  if(node.nodeType!==Node.ELEMENT_NODE)return [];
  const el=node as HTMLElement;if(ignored(el))return [];
  // Source viewers are utility copies of an equation. Include them only when
  // the selection explicitly belongs to that viewer's own copy scope.
  if(el.hasAttribute('data-copy-source-widget')&&el!==scope)return [];
  if(el.matches(mathSelector+',.katex,tex-math')){
   if(!overlaps(selected,el))return [];
   const value=mathValue(el);if(!value){warnings.add('math-unavailable');return [];}
   return [{kind:'math',tex:value.tex,display:value.display}];
  }
  if(el.tagName==='IMG'){warnings.add('image-link');return [{kind:'image',alt:el.getAttribute('alt')||'Image',href:safeHref(el.getAttribute('src'),pageURL)}];}
  if(!source&&el.hasAttribute('data-copy-source-html')){const value=mapped(el,selected);if(value)return wrap(el,value,selected);}
  return wrap(el,Array.from(el.childNodes).flatMap(child=>walk(child,selected,source)),selected);
 }
 let common=range.commonAncestorContainer;
 const owner=elementOf(common)?.closest<HTMLElement>('[data-copy-source-html]');
 if(owner&&scope.contains(owner)&&owner.contains(range.startContainer)&&owner.contains(range.endContainer))common=owner;
 let nodes=walk(common,range);
 for(let parent=common.parentElement;parent&&scope.contains(parent);parent=parent.parentElement){nodes=wrap(parent,nodes,range);if(parent===scope)break;}
 return formatSelection(nodes,[...warnings]);
}
