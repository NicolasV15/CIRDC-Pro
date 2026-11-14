/** Short names for the license URLs arXiv records; any other value is shown unchanged. `values` fill a translated label. */
export function licenseLabel(value:unknown):{label:string;values?:Record<string,string>;href?:string}|null{
 if(typeof value!=='string'||!value.trim())return null;
 const text=value.trim(),href=/^https?:\/\//i.test(text)?text:undefined;
 const cc=/creativecommons\.org\/licenses\/([a-z-]+)\/(\d+(?:\.\d+)?)/i.exec(text);
 if(cc)return {label:'CC '+cc[1].toUpperCase()+' '+cc[2],href};
 const zero=/creativecommons\.org\/publicdomain\/zero\/(\d+(?:\.\d+)?)/i.exec(text);
 if(zero)return {label:'CC0 '+zero[1],href};
 const arxiv=/arxiv\.org\/licenses\/nonexclusive-distrib\/(\d+(?:\.\d+)?)/i.exec(text);
 if(arxiv)return {label:'arXiv 非独占分发许可 {v}',values:{v:arxiv[1]},href};
 return {label:text,href};
}
