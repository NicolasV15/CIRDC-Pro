export type AuthorReference={source:string;author_id:string|null;name:string;ordinal:number};
export type AuthorIdentity={identity_key:string;source:string;author_id:string;display_name:string;papers:number;first_year:number;last_year:number;name_variants:string[]};
export function authorSearchHref(author:AuthorReference){
 if(!author.author_id)return undefined;
 return '/?'+new URLSearchParams({field:'authors',q:author.name||author.author_id,author_source:author.source,author_id:author.author_id});
}
export function otherAuthorIdentities(items:AuthorIdentity[],source:string,id:string){
 const seen=new Set<string>();
 return items.filter(item=>{const key=JSON.stringify([item.source,item.author_id]);if(seen.has(key)||(item.source===source&&item.author_id===id))return false;seen.add(key);return true});
}

export function ieeeAuthorHref(author:Pick<AuthorReference,'source'|'author_id'>){
 if(author.source!=='ieee'||!author.author_id||!/^\d{1,64}$/.test(author.author_id))return undefined;
 return 'https://ieeexplore.ieee.org/author/'+author.author_id;
}

export function authorProfileHref(author:Pick<AuthorReference,'source'|'author_id'>){
 if(!ieeeAuthorHref(author))return undefined;
 return '/authors/ieee/'+author.author_id;
}
