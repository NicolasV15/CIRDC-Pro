/** Keep an author page behind the dialog when an older tab follows its AI link. */
export function agentAccessEntry(href:string,referrer:string):{open:boolean;returnPath?:string}{
 const current=new URL(href);
 if(current.pathname!=='/developers/ai')return {open:false};
 try{
  const previous=new URL(referrer);
  const author=previous.pathname.match(/^\/authors\/ieee\/([0-9]{1,64})\/?$/);
  if(previous.origin===current.origin&&!previous.username&&!previous.password&&author){
   return {open:true,returnPath:'/authors/ieee/'+author[1]+previous.search+previous.hash};
  }
 }catch{/* Direct links and browsers without a referrer keep the normal AI entry. */}
 return {open:true};
}
