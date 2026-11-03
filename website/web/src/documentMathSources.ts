/** Restore only source controls whose adjacent original TeX is an exact match. */
function unwrap(value:string){
 const text=value.trim();
 for(const [left,right] of [['\\[','\\]'],['\\(','\\)'],['$$','$$'],['$','$']])if(text.startsWith(left)&&text.endsWith(right))return text.slice(left.length,-right.length).trim();
 return text;
}

export function restoreDocumentMathSources(root:HTMLElement,label:string){
 const doc=root.ownerDocument,walker=doc.createTreeWalker(root,NodeFilter.SHOW_TEXT),labels:HTMLElement[]=[];
 let text:Node|null;
 while(text=walker.nextNode()){
  const parent=text.parentElement;
  if(text.textContent?.trim()==='View Source'&&parent&&!parent.closest('[data-copy-source-widget]')&&parent.textContent?.trim()==='View Source')labels.push(parent);
 }
 let restored=0,serial=0;
 for(const original of labels){
  const wrapper=original.parentElement,source=original.nextElementSibling;
  if(!wrapper||wrapper.tagName!=='SPAN'||original.tagName!=='SPAN'||original.childElementCount||!source||source.tagName!=='SPAN'||source.childElementCount||wrapper.children.length!==2||wrapper.firstElementChild!==original)continue;
  if(Array.from(wrapper.childNodes).some(node=>node.nodeType===Node.TEXT_NODE&&!!node.textContent?.trim()))continue;
  const formula=wrapper.previousElementSibling as HTMLElement|null;
  if(!formula?.matches('.doc-math'))continue;
  let sibling:Node|null=formula.nextSibling,clean=true;
  while(sibling&&sibling!==wrapper){if(sibling.nodeType!==Node.TEXT_NODE||sibling.textContent?.trim()){clean=false;break;}sibling=sibling.nextSibling;}
  const raw=source.textContent||'',tex=formula.dataset.copyTex??unwrap(formula.textContent||'');
  if(!clean||!raw.trim()||unwrap(raw)!==unwrap(tex))continue;
  const button=doc.createElement('button'),code=doc.createElement('code');
  let id=source.id;
  if(!id){do{id='cirdc-math-source-'+(++serial);}while(doc.getElementById(id)||root.querySelector('#'+id));}
  button.type='button';button.className='reference-toggle document-math-source-toggle';button.textContent=label;
  if(original.id)button.id=original.id;
  button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls',id);
  code.id=id;code.className='document-math-source-code';code.hidden=true;code.textContent=raw;
  code.dataset.copyContent='math-source';code.dataset.copyTex=raw;code.dataset.copyDisplay='block';
  wrapper.classList.add('document-math-source');wrapper.dataset.copyScope='';wrapper.dataset.copySourceWidget='';
  wrapper.replaceChildren(button,code);
  button.addEventListener('click',()=>{code.hidden=!code.hidden;button.setAttribute('aria-expanded',String(!code.hidden));});
  restored++;
 }
 return restored;
}

export function labelDocumentMathSources(root:HTMLElement,label:string){
 for(const button of root.querySelectorAll<HTMLElement>('.document-math-source-toggle'))button.textContent=label;
}
