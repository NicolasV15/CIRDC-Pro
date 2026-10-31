const roman=/^(?=.+$)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$/;
const normalized=(text:string)=>text.normalize('NFKC').replace(/\s+/g,' ').trim();

/** Read a standalone publisher label, never derive numbering from anchor IDs. */
export function documentSectionNumber(text:string):string|undefined{
 const match=/^SECTION\s+([IVXLCDM]+|[1-9]\d*)\.?$/i.exec(normalized(text));
 if(!match)return undefined;
 const number=match[1].toUpperCase();
 return /^\d+$/.test(number)||roman.test(number)?number:undefined;
}

export function documentHeadingTitle(label:string,title:string):string|undefined{
 const number=documentSectionNumber(label);if(!number)return undefined;
 const value=title.replace(/\s+/g,' ').trim(),prefix=/^(?:SECTION\s+)?([IVXLCDM\d\u2160-\u2188]+)\.\s*/i.exec(value);
 const existing=prefix?documentSectionNumber('SECTION '+prefix[1]+'.'):undefined;
 if(existing&&existing!==number)return undefined;
 const heading=existing?value.slice(prefix![0].length):value;
 return heading?number+'. '+heading:undefined;
}

/** Restore publisher numbering in cached HTML without changing the source cache. */
export function restoreDocumentHeadings(container:HTMLElement):Record<string,string>{
 const titles:Record<string,string>=Object.create(null);
 for(const heading of container.querySelectorAll<HTMLElement>('h1[id],h2[id],h3[id],h4[id],h5[id],h6[id]')){
  const first=heading.firstElementChild;
  const existing=first?.classList.contains('document-section-number')?first:null;
  let prefix:Node|null=existing||heading.previousSibling;
  if(!existing)while(prefix?.nodeType===Node.TEXT_NODE&&!prefix.textContent?.trim())prefix=prefix.previousSibling;
  if(!prefix)continue;
  if(prefix instanceof Element){
   if(!existing&&!prefix.matches('div,p,span'))continue;
   if(Array.from(prefix.querySelectorAll('*')).some(node=>!node.matches('span,strong,em,b,i,small,br')))continue;
  }else if(prefix.nodeType!==Node.TEXT_NODE)continue;
  const label=prefix.textContent||'',number=documentSectionNumber(label);
  const title=existing?(heading.textContent||'').slice(label.length):heading.textContent||'';
  const outlineTitle=documentHeadingTitle(label,title);
  if(!number||!outlineTitle)continue;
  if(!existing){
   const marker=heading.ownerDocument.createElement('span');marker.className='document-section-number';
   if(prefix instanceof Element){if(prefix.id)marker.id=prefix.id;marker.append(...Array.from(prefix.childNodes));}
   else marker.textContent=label;
   marker.append(heading.ownerDocument.createTextNode(' '));prefix.parentNode?.removeChild(prefix);heading.prepend(marker);
  }
  titles[heading.id]=outlineTitle;
 }
 return titles;
}
