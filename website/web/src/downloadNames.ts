import {citationText} from './citations.ts';
import {paperVenueTags,type VenueReference} from './venueFamilies.ts';
export const filenameKey='cirdc.download-template.v1';
export const defaultFilenameTemplate='{year}_{abbr}_{id}_{title}';
export const filenameFields=['id','title','year','abbr'] as const;
export type FilenameField=typeof filenameFields[number];
export type FilenamePaper=VenueReference&{number:string;title:string;year?:number|string};
const encoder=new TextEncoder();
export function filenameTemplateError(template:string){
 if(template.length>300)return '文件名模板最多 300 个字符。';
 const unknown=[...template.matchAll(/\{([^{}]*)\}/g)].find(match=>!filenameFields.includes(match[1].toLowerCase() as FilenameField));
 if(unknown)return '模板包含未知字段，请使用 id、title、year、abbr。';
 if(/[{}]/.test(template.replace(/\{(?:id|title|year|abbr)\}/gi,'')))return '模板花括号不完整。';
 return '';
}
export function templateHas(template:string,field:FilenameField){return new RegExp('\\{'+field+'\\}','i').test(template);}
export function toggleFilenameField(template:string,field:FilenameField,enabled:boolean){
 if(enabled)return templateHas(template,field)?template:template+(template&&!/[\s_-]$/.test(template)?'_':'')+'{'+field+'}';
 return cleanLayout(template.replace(new RegExp('\\{'+field+'\\}','gi'),''));
}
function cleanLayout(value:string){return value.replace(/\[\s*\]|\(\s*\)/g,'').replace(/([_-])(?:\s*[_-])+/g,'$1').replace(/^[\s._-]+|[\s._-]+$/g,'').replace(/\s{2,}/g,' ');}
function trimBytes(value:string,budget:number){let used=0,result='';for(const char of value){const size=encoder.encode(char).length;if(used+size>budget)break;result+=char;used+=size;}return result.trim().replace(/[. ]+$/g,'');}
export function renderFilename(template:string,paper:FilenamePaper,suffix=''){
 if(filenameTemplateError(template))throw new Error(filenameTemplateError(template));
 const fields:Record<FilenameField,string>={id:paper.number,title:citationText(paper.title),year:citationText(paper.year),abbr:paperVenueTags(paper).map(tag=>tag.label).join('+')};
 const values:string[]=[];let missing=false;
 let result=template.replace(/\{(id|title|year|abbr)\}/gi,(_,field:string)=>{const value=fields[field.toLowerCase() as FilenameField];if(!value){missing=true;return '';}const index=values.push(value)-1;return '\u0000'+index+'\u0000';});
 result=(missing?cleanLayout(result):result).replace(/\u0000(\d+)\u0000/g,(_,index:string)=>values[+index]);
 result=result.normalize('NFC').replace(/\.pdf$/i,'').replace(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069/\\:*?"<>|]/g,'-').trim().replace(/^\.+|[. ]+$/g,'');
 if(!/[^\s._-]/.test(result))result=paper.number;
 if(/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(result))result='_'+result;
 return (trimBytes(result,240-4-encoder.encode(suffix).length)||paper.number)+suffix+'.pdf';
}
export function downloadFilenames(template:string,papers:FilenamePaper[]){
 const used=new Set<string>();return papers.map(paper=>{
  let name=renderFilename(template,paper),attempt=0;
  while(used.has(name.normalize('NFC').toLowerCase())){attempt++;name=renderFilename(template,paper,' ['+paper.number+']'+(attempt>1?' ('+attempt+')':''));}
  used.add(name.normalize('NFC').toLowerCase());return {number:paper.number,filename:name};
 });
}
