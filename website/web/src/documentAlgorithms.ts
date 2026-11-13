export type AlgorithmControl='line'|'section'|'unknown'|'for'|'while'|'if'|'repeat'|'end for'|'end while'|'end if'|'until'|'else';
type Block='for'|'while'|'if'|'repeat';

/** An uncertain or unbalanced control sequence must never invent indentation. */
export function algorithmIndentation(controls:AlgorithmControl[]):number[]|undefined{
 const stack:Block[]=[],depths:number[]=[];
 for(const control of controls){
  if(control==='unknown')return;
  if(control==='section'){if(stack.length)return;depths.push(0);continue;}
  if(control==='else'){if(stack.at(-1)!=='if')return;depths.push(stack.length-1);continue;}
  const closing=control==='until'?'repeat':control.startsWith('end ')?control.slice(4):undefined;
  if(closing&&stack.pop()!==closing)return;
  depths.push(stack.length);
  if(['for','while','if','repeat'].includes(control))stack.push(control as Block);
 }
 return stack.length?undefined:depths;
}

const text=(node:Node)=>node.textContent?.replace(/\s+/g,' ').trim()||'';
function controlOf(body:HTMLElement):AlgorithmControl{
 const nodes=Array.from(body.childNodes).filter(node=>node.nodeType!==Node.TEXT_NODE||!!text(node));
 const first=nodes[0],last=nodes.at(-1);
 if(!(first instanceof Element)||!first.matches('b,strong'))return 'line';
 const start=text(first).toLowerCase(),whole=text(body).toLowerCase();
 if(/^end\s*(for|while|if)$/.test(whole))return ('end '+whole.replace(/^end\s*/,'')) as AlgorithmControl;
 if(start==='until')return 'until';
 if(start==='repeat')return 'repeat';
 if(start==='else'&&whole==='else')return 'else';
 const end=last instanceof Element&&last.matches('b,strong')?text(last).toLowerCase():'';
 if((start==='for'||start==='for all')&&end==='do')return 'for';
 if(start==='while'&&end==='do')return 'while';
 if(start==='if'&&end==='then')return 'if';
 if(/^(?:for|foreach|while|if|else|elseif|repeat|until|end|switch|case|loop|do|try|catch)\b/.test(start))return 'unknown';
 return 'line';
}

type Row={element:HTMLElement;body:HTMLElement;label?:HTMLElement;kind:'line'|'io'|'role';control:AlgorithmControl};
function rowsOf(heading:HTMLElement):{parent:HTMLElement;rows:Row[]}|undefined{
 const parent=heading.parentElement;
 if(!parent?.matches('div,section,figure')||parent.firstElementChild!==heading||parent.classList.contains('document-algorithm'))return;
 const children=Array.from(parent.children),rows:Row[]=[];
 if(Array.from(parent.childNodes).some(node=>node.nodeType===Node.TEXT_NODE&&!!text(node)))return;
 let numbered=0,next:number|undefined;
 for(const element of children.slice(1)){
  if(!(element instanceof HTMLElement)||element.tagName!=='DIV'||Array.from(element.childNodes).some(node=>node.nodeType===Node.TEXT_NODE&&!!text(node)))return;
  const parts=Array.from(element.children),label=parts.length===2&&parts[0].tagName==='SPAN'?parts[0] as HTMLElement:undefined;
  const body=parts.at(-1);
  if(!(body instanceof HTMLElement)||body.tagName!=='P'||body.querySelector('table,ul,ol,pre,figure,h1,h2,h3,h4,h5,h6'))return;
  if(!label){
   const bold=body.firstElementChild;
   if(parts.length!==1||body.children.length!==1||!bold?.matches('b,strong')||!text(bold)||text(body)!==text(bold))return;
   next=undefined;rows.push({element,body,kind:'role',control:'section'});continue;
  }
  if(label.childElementCount)return;
  const match=/^(\d+)\s*:$/.exec(text(label));
  if(match){
   const number=Number(match[1]);
   if(!Number.isSafeInteger(number)||(next===undefined?number!==0&&number!==1:number!==next))return;
   next=number+1;numbered++;rows.push({element,body,label,kind:'line',control:controlOf(body)});
  }else{
   if(!/^(?:input|output|require|ensure)\s*:$/i.test(text(label)))return;
   rows.push({element,body,label,kind:'io',control:'section'});
  }
 }
 return numbered>=2?{parent,rows}:undefined;
}

/** Decorate only a dedicated algorithm container with explicit numbered rows.
 * Original nodes, text, numbering, links and TeX remain in place for copying. */
export function restoreDocumentAlgorithms(container:HTMLElement){
 let restored=0;
 for(const heading of container.querySelectorAll<HTMLElement>('h1,h2,h3,h4,h5,h6')){
  if(!/^Algorithm\s+(?:[1-9]\d*|[IVXLCDM]+)(?=$|[\s:–—.-])/i.test(text(heading)))continue;
  const parsed=rowsOf(heading);if(!parsed||parsed.parent===container)continue;
  const {parent,rows}=parsed,depths=algorithmIndentation(rows.map(row=>row.control));
  parent.classList.add('document-algorithm');parent.dataset.algorithmIndent=depths?'verified':'flat';
  heading.classList.add('document-algorithm-heading');
  rows.forEach((row,i)=>{
   row.element.classList.add('document-algorithm-row','document-algorithm-'+row.kind);
   row.body.classList.add('document-algorithm-content');
   row.label?.classList.add('document-algorithm-label');
   row.element.style.setProperty('--document-algorithm-depth',String(depths?.[i]||0));
  });
  restored++;
 }
 return restored;
}
