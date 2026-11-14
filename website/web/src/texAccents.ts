/** TeX text accents in metadata prose (`moir\'e`, `Dim\v{s}a`, `S{\o}ren`) as Unicode letters. Math is never passed here. */
const symbols:Record<string,string>={'`':'\u0300',"'":'\u0301','^':'\u0302','~':'\u0303','=':'\u0304','.':'\u0307','"':'\u0308'};
const letters:Record<string,string>={u:'\u0306',r:'\u030a',H:'\u030b',v:'\u030c',c:'\u0327',k:'\u0328'};
const specials:Record<string,string>={o:'ø',O:'Ø',ss:'ß',l:'ł',L:'Ł',ae:'æ',AE:'Æ',oe:'œ',OE:'Œ',aa:'å',AA:'Å'};
const base='(?:\\\\[ij](?![A-Za-z])|[A-Za-z])';
// `\'e`, `\'{e}`, `\v{s}`, `\v s`; letter commands need a brace or space so `\cos` is never read as `\c`.
const command='\\\\(?:([`\'^~=."])\\s*(?:\\{\\s*('+base+')\\s*\\}|('+base+'))|([urHvck])(?:\\s*\\{\\s*('+base+')\\s*\\}|\\s+('+base+')))';
const braced=new RegExp('\\{'+command+'\\}','g'),bare=new RegExp(command,'g');
// A bare control word ends at `{}` or one space that TeX consumes (`Stra\ss e`).
const special=/\{\\(ss|ae|AE|oe|OE|aa|AA|o|O|l|L)\}|\\(ss|ae|AE|oe|OE|aa|AA|o|O|l|L)(?![A-Za-z])(?:\{\}| (?=[A-Za-z]))?/g;
function accented(symbol?:string,a?:string,b?:string,letter?:string,c?:string,d?:string){
 const letterBase=(a||b||c||d||'').replace(/^\\([ij])$/,'$1');
 return (letterBase+(symbol?symbols[symbol]:letters[letter!])).normalize('NFC');
}
export function decodeTexAccents(value:string):string{
 if(!value.includes('\\'))return value;
 const replace=(_:string,...groups:(string|undefined)[])=>accented(...groups as [string?,string?,string?,string?,string?,string?]);
 return value.replace(braced,replace).replace(bare,replace).replace(special,(_,inBraces?:string,plain?:string)=>specials[inBraces||plain!]);
}
/** The same decoding for a title or abstract that may contain math: math segments are kept byte-for-byte. */
export function decodeTexAccentsOutsideMath(value:string):string{
 return value.split(/(\$\$[\s\S]*?\$\$|\$[^$]*\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\])/).map((part,index)=>index%2?part:decodeTexAccents(part)).join('');
}
