const textArguments=new Set('text textrm textnormal textbf textmd textit textup textsl textsc textsf texttt mbox hbox operatorname tag label ref eqref url href'.split(' '));

// IEEE sometimes supplies an unbraced \sum as the one argument of \mathop.
// KaTeX requires this operator argument to be grouped. Insert only those braces
// in the display input; the DOM's data-copy-tex and stored source stay original.
function adaptDisplayCommands(tex:string){
 // Definitions and verbatim can change token interpretation; leave them alone.
 if(/\\(?:def|gdef|edef|xdef|let|futurelet|newcommand|renewcommand|providecommand|catcode|csname|verb)(?![A-Za-z@])/.test(tex))return tex;
 let result='',last=0;
 function commentEnd(start:number){const end=tex.indexOf('\n',start);return end<0?tex.length:end+1;}
 function groupEnd(start:number){
  let depth=1;
  for(let i=start+1;i<tex.length;i++){
   if(tex[i]==='\\'){i++;continue;}if(tex[i]==='%'){i=commentEnd(i)-1;continue;}
   if(tex[i]==='{')depth++;else if(tex[i]==='}'&&!--depth)return i+1;
  }
  return -1;
 }
 for(let i=0;i<tex.length;){
  if(tex[i]==='%'){i=commentEnd(i);continue;}if(tex[i]!=='\\'){i++;continue;}
  const token=/^\\([A-Za-z@]+|[\s\S])/.exec(tex.slice(i));if(!token){i++;continue;}
  i+=token[0].length;
  if(textArguments.has(token[1])){
   if(tex[i]==='*')i++;
   let start=i;while(/\s/.test(tex[start]||'')&&start<tex.length)start++;
   if(tex[start]==='{'){const end=groupEnd(start);i=end<0?tex.length:end;}
  }else if(token[1]==='mathop'){
   const argument=/^(\s*)(\\sum)(?![A-Za-z@])/.exec(tex.slice(i));
   if(argument){const start=i+argument[1].length;result+=tex.slice(last,start)+'{'+argument[2]+'}';last=i+argument[0].length;i=last;}
  }else if(token[1]==='raise'||token[1]==='lower'){
   // IEEE's slanted fractions use TeX box shifts unsupported by KaTeX.
   // Translate only a literal dimension followed by a complete hbox; retain
   // its text/math content and leave other TeX box syntax untouched.
   const box=/^\s*([+-]?)(\d+(?:\.\d*)?|\.\d+)\s*(em|ex|pt|pc|in|bp|cm|mm|dd|cc|sp)\s*\\hbox\s*\{/.exec(tex.slice(i));
   if(box){
    const start=i+box[0].length-1,end=groupEnd(start);
    if(end>=0){
     const negative=(box[1]==='-')!==(token[1]==='lower');
     result+=tex.slice(last,i-token[0].length)+'\\raisebox{'+(negative?'-':'')+box[2]+box[3]+'}'+tex.slice(start,end);
     last=end;i=end;
    }
   }
  }
 }
 return result+tex.slice(last);
}

export function documentMathForDisplay(tex:string){
 // Some PDF exports repeat identical adjacent equation tags.
 return adaptDisplayCommands(tex.replace(/(\\tag\s*\{([^{}]*)\})(?:\s*\\tag\s*\{\2\})+/g,'$1'));
}
