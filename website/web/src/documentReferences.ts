const number='(?:[A-Z]\\.?)?\\d+(?:[.\\-]\\d+)*(?:[A-Z])?|[IVXLCDM]+';
const label=new RegExp('^(figure|fig|table|tab|tbl|图|表)\\.?\\s*('+number+')(?:\\s*\\([a-z]\\))?(?=$|[\\s:.,;\\-–—])','i');

export function documentReferenceKey(text:string,caption=false):string|undefined{
 const value=text.normalize('NFKC').replace(/\s+/g,' ').trim(),match=label.exec(value);
 if(!match||(!caption&&value.slice(match[0].length).trim()))return undefined;
 const kind=/^(?:fig|图)/i.test(match[1])?'figure':'table';
 return kind+':'+match[2].toLowerCase().replace(/\.$/,'');
}

/** The publisher sometimes makes only the number clickable, leaving Fig./Table outside. */
export function contextualDocumentReferenceKey(text:string,before:string,previous?:{key:string;subfigure:boolean}):string|undefined{
 const prefix=before.normalize('NFKC').replace(/[\u200b\ufeff]/g,'');
 const match=/(?:^|[^\p{L}\p{N}_])(fig(?:ure)?s?|tab(?:le)?s?|tbls?|图|表)\.?\s*$/iu.exec(prefix);
 if(match)return documentReferenceKey(match[1].replace(/s$/i,'')+' '+text);
 if(!previous||!/^\s*(?:,|[-–—−]|(?:,\s*)?(?:and|or|&|to|through))\s*$/i.test(prefix))return;
 if(previous.subfigure&&previous.key.startsWith('figure:')&&/^\([a-z]\)$/i.test(text.trim()))return previous.key;
 return documentReferenceKey((previous.key.startsWith('figure:')?'Fig. ':'Table ')+text);
}

/** Restore local cross-references in sanitized and already-cached article HTML. */
export function restoreDocumentReferences(container:HTMLElement,pageURL:string=location.href){
 const targets=new Map<string,HTMLElement|null>();
 const ids=new Map<string,HTMLElement|null>();
 for(const node of container.querySelectorAll<HTMLElement>('[id]'))ids.set(node.id,ids.has(node.id)?null:node);
 for(const node of container.querySelectorAll<HTMLElement>('figure,table,[id]')){
  if(!node.matches('figure,table')&&!/^(?:fig(?:ure)?|tab(?:le)?|tbl|f|t)[\d_.:-]/i.test(node.id))continue;
  const caption=node.querySelector('figcaption,caption');
  const key=documentReferenceKey(caption?.textContent||node.textContent||'',true);
  if(!key)continue;
  if(!node.id){let id='document-'+key.replace(/[^a-z0-9_-]/g,'-'),suffix=1;while(ids.has(id)||container.ownerDocument.getElementById(id))id='document-'+key.replace(/[^a-z0-9_-]/g,'-')+'-'+suffix++;node.id=id;ids.set(id,node);}
  const previous=targets.get(key);
  if(previous===undefined)targets.set(key,node);
  else if(previous&&previous!==node&&!previous.contains(node))targets.set(key,node.contains(previous)?node:null);
 }
 const page=new URL(pageURL),article=page.pathname.match(/^\/papers\/([0-9]+)\/?$/)?.[1];
 let previous:{anchor:HTMLAnchorElement;scope:Element;key:string;subfigure:boolean}|undefined;
 for(const anchor of container.querySelectorAll<HTMLAnchorElement>('a')){
  const prior=previous;previous=undefined;
  const href=anchor.getAttribute('href');let target:HTMLElement|undefined;
  if(href){
   try{
    const url=new URL(href,page),samePage=url.origin===page.origin&&url.pathname===page.pathname&&url.search===page.search;
    const sourcePage=!!article&&url.protocol==='https:'&&url.hostname==='ieeexplore.ieee.org'&&url.pathname.match(/^\/document\/([0-9]+)(?:\/|$)/)?.[1]===article;
    if(url.hash&&(samePage||sourcePage)){
     target=ids.get(decodeURIComponent(url.hash.slice(1)))||undefined;
     if(!target)continue; // A missing explicit destination is not evidence for a different one.
    }
    if(!target&&!href.startsWith('#')&&!samePage&&!sourcePage)continue;
   }catch{continue;}
  }
  const text=anchor.textContent||'',scope=anchor.closest('p,li,dd,dt,td,th,figcaption,caption,h1,h2,h3,h4,h5,h6')||anchor.parentElement!;
  let key=documentReferenceKey(text);
  if(!key){
   const range=container.ownerDocument.createRange();range.setStart(scope,0);range.setEndBefore(anchor);
   key=contextualDocumentReferenceKey(text,range.toString());
   if(!key&&prior?.scope===scope){
    range.setStartAfter(prior.anchor);
    if(!range.cloneContents().querySelector('br,p,div,section,li,dd,dt,table,hr'))key=contextualDocumentReferenceKey(text,range.toString(),prior);
   }
  }
  if(!target&&key)target=targets.get(key)||undefined;
  if(target&&ids.get(target.id)!==target)target=undefined;
  if(!target)continue;
  if(key&&targets.get(key)===target)previous={anchor,scope,key,subfigure:/\([a-z]\)\s*$/i.test(text)};
  anchor.setAttribute('href','#'+encodeURIComponent(target.id));anchor.removeAttribute('target');anchor.classList.add('document-reference-link');
  target.classList.add('document-reference-target');if(!target.hasAttribute('tabindex'))target.tabIndex=-1;
 }
}
