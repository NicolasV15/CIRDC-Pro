const number='(?:[A-Z]\\.?)?\\d+(?:[.\\-]\\d+)*(?:[A-Z])?|[IVXLCDM]+';
const label=new RegExp('^(figure|fig|table|tab|tbl|图|表)\\.?\\s*('+number+')(?:\\s*\\([a-z]\\))?(?=$|[\\s:.,;\\-–—])','i');

export function documentReferenceKey(text:string,caption=false):string|undefined{
 const value=text.normalize('NFKC').replace(/\s+/g,' ').trim(),match=label.exec(value);
 if(!match||(!caption&&value.slice(match[0].length).trim()))return undefined;
 const kind=/^(?:fig|图)/i.test(match[1])?'figure':'table';
 return kind+':'+match[2].toLowerCase().replace(/\.$/,'');
}

/** Restore local cross-references in sanitized and already-cached article HTML. */
export function restoreDocumentReferences(container:HTMLElement,pageURL:string=location.href){
 const targets=new Map<string,HTMLElement|null>();
 const ids=new Map(Array.from(container.querySelectorAll<HTMLElement>('[id]')).map(node=>[node.id,node]));
 for(const node of container.querySelectorAll<HTMLElement>('figure,table,[id]')){
  if(!node.matches('figure,table')&&!/^(?:fig(?:ure)?|tab(?:le)?|tbl|f|t)[\d_.:-]/i.test(node.id))continue;
  const caption=node.querySelector('figcaption,caption');
  const key=documentReferenceKey(caption?.textContent||node.textContent||'',true);
  if(!key)continue;
  if(!node.id){let id='document-'+key.replace(/[^a-z0-9_-]/g,'-'),suffix=1;while(document.getElementById(id))id='document-'+key.replace(/[^a-z0-9_-]/g,'-')+'-'+suffix++;node.id=id;ids.set(id,node);}
  const previous=targets.get(key);
  if(previous===undefined)targets.set(key,node);
  else if(previous&&previous!==node&&!previous.contains(node))targets.set(key,node.contains(previous)?node:null);
 }
 const page=new URL(pageURL),article=page.pathname.match(/^\/papers\/([0-9]+)\/?$/)?.[1];
 for(const anchor of container.querySelectorAll<HTMLAnchorElement>('a')){
  const href=anchor.getAttribute('href');let target:HTMLElement|undefined;
  if(href){
   try{
    const url=new URL(href,page),samePage=url.origin===page.origin&&url.pathname===page.pathname&&url.search===page.search;
    const sourcePage=!!article&&url.protocol==='https:'&&url.hostname==='ieeexplore.ieee.org'&&url.pathname.match(/^\/document\/([0-9]+)(?:\/|$)/)?.[1]===article;
    if(url.hash&&(samePage||sourcePage))target=ids.get(decodeURIComponent(url.hash.slice(1)));
    if(!target&&!href.startsWith('#')&&!samePage&&!sourcePage)continue;
   }catch{continue;}
  }
  if(!target){const key=documentReferenceKey(anchor.textContent||'');if(key)target=targets.get(key)||undefined;}
  if(!target)continue;
  anchor.setAttribute('href','#'+encodeURIComponent(target.id));anchor.removeAttribute('target');anchor.classList.add('document-reference-link');
  target.classList.add('document-reference-target');if(!target.hasAttribute('tabindex'))target.tabIndex=-1;
 }
}
