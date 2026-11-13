import katex from 'katex';

export type CopyFormat='markdown'|'latex'|'text';
export type CopyWarning='table-simplified'|'image-link'|'source-unmapped'|'math-unavailable'|'link-omitted';
export type CopyNode={kind:'text';value:string}|{kind:'math';tex:string;display:boolean;preserveWhitespace?:boolean}|{kind:'image';alt:string;href:string}|{kind:'element';tag:string;children:CopyNode[];href?:string;start?:number;complete?:boolean;simple?:boolean};
export type CopyResult={values:Record<CopyFormat,string>;warnings:Record<CopyFormat,CopyWarning[]>};
type Piece={value:string;block:boolean};
const blocks=new Set(['p','div','section','article','figure','figcaption','caption','blockquote','pre','ul','ol','table','h1','h2','h3','h4','h5','h6']);
export function escapeLatex(value:string){
 const replacements:Record<string,string>={'\\':'\\textbackslash{}','{':'\\{','}':'\\}','%':'\\%','&':'\\&','#':'\\#','_':'\\_','$':'\\$','~':'\\textasciitilde{}','^':'\\textasciicircum{}','<':'\\textless{}','>':'\\textgreater{}'};
 return [...value].map(char=>replacements[char]??char).join('');
}
export function escapeMarkdown(value:string){return value.replace(/[\\`*_[\]<>#|~$&]/g,'\\$&').replace(/^(\s*)([-+])(?=\s)/gm,'$1\\$2').replace(/^(\s*\d+)\.(?=\s)/gm,'$1\\.');}
export function unwrappedMath(value:string){
 const tex=value.trim();
 for(const [left,right] of [['$$','$$'],['\\[','\\]'],['\\(','\\)'],['$','$']])if(tex.startsWith(left)&&tex.endsWith(right)&&tex.length>=left.length+right.length)return tex.slice(left.length,-right.length).trim();
 return tex;
}
export function hasMathEnvironment(tex:string){return /^\s*\\begin\s*\{(?:equation\*?|align\*?|alignat\*?|flalign\*?|xalignat\*?|xxalignat|gather\*?|multline\*?|eqnarray\*?|displaymath|math)\}/.test(tex);}

const greekLetters=new Map(Object.entries({
 alpha:'α',beta:'β',gamma:'γ',delta:'δ',epsilon:'ϵ',zeta:'ζ',eta:'η',theta:'θ',iota:'ι',kappa:'κ',lambda:'λ',mu:'μ',nu:'ν',xi:'ξ',omicron:'ο',pi:'π',rho:'ρ',sigma:'σ',tau:'τ',upsilon:'υ',phi:'ϕ',chi:'χ',psi:'ψ',omega:'ω',
 varepsilon:'ε',vartheta:'ϑ',varkappa:'ϰ',varpi:'ϖ',varrho:'ϱ',varsigma:'ς',varphi:'φ',
 Gamma:'Γ',Delta:'Δ',Theta:'Θ',Lambda:'Λ',Xi:'Ξ',Pi:'Π',Sigma:'Σ',Upsilon:'Υ',Phi:'Φ',Psi:'Ψ',Omega:'Ω',
}));
const plainMathFonts=new Set(['mathrm','mathnormal','mathit']);
/** Convert only a flat, known Greek expression. Unsupported structure keeps all TeX. */
function plainGreekMath(tex:string):string{
 let value='',greek=false,depth=0;
 for(let i=0;i<tex.length;){
  const char=tex[i];
  if(/\s/.test(char)){i++;continue;}
  if(char==='{'){if(++depth>64)return tex;i++;continue;}
  if(char==='}'){if(--depth<0)return tex;i++;continue;}
  if(char==='\\'){
   const command=/^\\([A-Za-z]+)/.exec(tex.slice(i));
   if(!command){
    if([',',':',';',' '].includes(tex[i+1])){value+=' ';i+=2;continue;}
    return tex;
   }
   const name=command[1],symbol=greekLetters.get(name);i+=command[0].length;
   if(symbol!==undefined){value+=symbol;greek=true;continue;}
   if(name==='quad'||name==='qquad'){value+=' ';continue;}
   if(plainMathFonts.has(name)&&/^\s*\{/.test(tex.slice(i)))continue;
   return tex;
  }
  // Scripts, accents, environments and macro definitions are deliberately absent.
  if(!/[A-Za-z0-9\u0370-\u03ff+\-=(),.;:/|\[\]<>*!]/.test(char))return tex;
  value+=char;i++;
 }
 return greek&&depth===0?value:tex;
}

const opaqueMathArguments=new Set(('text textrm textnormal textbf textmd textit textup textsl textsc textsf texttt mbox hbox vbox makebox parbox shortstack intertext shortintertext operatorname begin end label ref eqref tag url href htmlClass htmlId htmlStyle htmlData html@mathml includegraphics color textcolor definecolor hspace mspace kern mkern raisebox rule mathchoice').split(' '));
const statefulMathCommands=new Set(('def gdef edef xdef let futurelet newcommand renewcommand providecommand newenvironment renewenvironment catcode csname endcsname makeatletter makeatother global long protected everymath everydisplay DeclareMathOperator expandafter noexpand unexpanded if ifcase ifx ifcat ifnum ifdim ifodd ifvmode ifhmode ifmmode ifinner ifvoid ifhbox ifvbox ifeof iftrue iffalse ifdefined ifcsname else or fi verb').split(' '));

function mathArgumentEnd(tex:string,start:number):number|undefined{
 const open=tex[start],close=open==='{'?'}':']';let depth=1;
 for(let i=start+1;i<tex.length;i++){
  if(tex[i]==='\\'){i++;continue;}
  if(open==='['&&tex[i]==='{'){const end=mathArgumentEnd(tex,i);if(end===undefined)return;i=end-1;continue;}
  if(tex[i]===open)depth++;else if(tex[i]===close&&!--depth)return i+1;
 }
}

/** Remove only source whitespace whose unchanged rendering can be verified. */
export function compactMathSource(tex:string,display=false):string{
 if(!/[ \t]/.test(tex))return tex;
 // Comments, verbatim and definitions can affect later tokens or fragments.
 for(let i=0;i<tex.length;i++){if(tex[i]==='\\'){i++;continue;}if(tex[i]==='%')return tex;}
 if(/\\verb(?:\*|[^A-Za-z@]|$)/.test(tex))return tex;
 let candidate='',controlWord=false;
 for(let i=0;i<tex.length;){
  const char=tex[i];
  if(char===' '||char==='\t'){
   while(tex[i]===' '||tex[i]==='\t')i++;
   const next=i<tex.length?String.fromCodePoint(tex.codePointAt(i)!):'';
   if(controlWord&&/[\p{L}@]/u.test(next))candidate+=' ';
   controlWord=false;continue;
  }
  if(char!=='\\'){candidate+=char;i++;controlWord=false;continue;}
  const command=/^\\([A-Za-z@]+)/.exec(tex.slice(i));
  if(!command){candidate+=tex.slice(i,i+2);i+=2;controlWord=false;continue;}
  const name=command[1];if(statefulMathCommands.has(name))return tex;
  candidate+=command[0];i+=command[0].length;controlWord=true;
  if(!opaqueMathArguments.has(name))continue;
  if(['operatorname','tag','hspace'].includes(name)){
   let star=i;while(/[ \t]/.test(tex[star]||'')&&star<tex.length)star++;
   if(tex[star]==='*'){candidate+='*';i=star+1;controlWord=false;}
  }
  while(i<tex.length){
   let start=i;while(/[ \t\r\n]/.test(tex[start]||'')&&start<tex.length)start++;
   if(tex[start]!=='{'&&tex[start]!=='[')break;
   const end=mathArgumentEnd(tex,start);if(end===undefined)return tex;
   candidate+=tex.slice(i,start).replace(/[ \t]/g,'')+tex.slice(start,end);i=end;controlWord=false;
  }
 }
 if(candidate===tex)return tex;
 try{
  const rendered=(value:string)=>katex.renderToString(value,{displayMode:display,output:'mathml',throwOnError:true,strict:'ignore',trust:false,maxExpand:1000,macros:{}}).replace(/<annotation\b[^>]*>[\s\S]*?<\/annotation>/g,'');
  return rendered(tex)===rendered(candidate)?candidate:tex;
 }catch{return tex;}
}
function join(pieces:Piece[]){
 const relevant=pieces.filter((p,i)=>p.value&&!(p.value.trim()===''&&(pieces[i-1]?.block||pieces[i+1]?.block)));
 let value='',previous=false;
 for(const piece of relevant){if(value&&(previous||piece.block))value+='\n\n';value+=piece.value;previous=piece.block;}
 return value;
}
function plainSource(nodes:CopyNode[]):string{return nodes.map(n=>n.kind==='text'?n.value:n.kind==='math'?n.tex:n.kind==='image'?n.alt:plainSource(n.children)).join('');}
function descendants(node:CopyNode,tag:string):Extract<CopyNode,{kind:'element'}>[] {
 if(node.kind!=='element')return [];
 if(node.tag===tag)return [node];
 return node.children.flatMap(child=>descendants(child,tag));
}
function unsafeTableMath(nodes:CopyNode[]):boolean{return nodes.some(n=>n.kind==='math'?(n.display||n.tex.includes('|')):n.kind==='element'?(n.tag==='ul'||n.tag==='ol'||n.tag==='pre'||unsafeTableMath(n.children)):false);}
const destination=(href:string)=>href.replace(/[()<>\\\s]/g,char=>encodeURIComponent(char));

export function formatSelection(nodes:CopyNode[],commonWarnings:CopyWarning[]=[]):CopyResult{
 const warnings={} as Record<CopyFormat,CopyWarning[]>,values={} as Record<CopyFormat,string>;
 const mathSources=new Map<string,string>();
 for(const format of ['markdown','latex','text'] as const){
  const notes=new Set(commonWarnings);
  const normal=(value:string)=>format==='latex'?escapeLatex(value):format==='markdown'?escapeMarkdown(value):value;
  const renderChildren=(children:CopyNode[],depth=0)=>join(children.map(n=>render(n,depth)));
  function render(node:CopyNode,depth=0):Piece{
   if(node.kind==='text')return {value:normal(node.value),block:false};
   if(node.kind==='math'){
    const source=unwrappedMath(node.tex),display=node.display||hasMathEnvironment(source),key=(display?'1':'0')+'\0'+source;
    if(!node.preserveWhitespace&&!mathSources.has(key))mathSources.set(key,compactMathSource(source,display));
    const tex=node.preserveWhitespace?source:mathSources.get(key)!,environment=hasMathEnvironment(tex);
    if(format==='text')return {value:node.preserveWhitespace?tex:plainGreekMath(tex),block:display};
    if(format==='latex')return {value:environment?tex:display?'\\[\n'+tex+'\n\\]':'\\('+tex+'\\)',block:display};
    return {value:display?'$$\n'+tex+'\n$$':'$'+tex+'$',block:display};
   }
   if(node.kind==='image'){
    notes.add('image-link');const label=normal(node.alt||'Image');
    return {value:node.href?(format==='markdown'?'['+label+']('+destination(node.href)+')':format==='latex'?'\\href{'+escapeLatex(destination(node.href))+'}{'+label+'}':label+' ('+node.href+')'):label,block:true};
   }
   const {tag,children}=node;
   if(tag==='br')return {value:format==='latex'?'\\\\\n':format==='markdown'?'  \n':'\n',block:false};
   if(tag==='pre'){
    const text=plainSource(children);const fence='`'.repeat(Math.max(3,...(text.match(/`+/g)||[]).map(x=>x.length+1)));
    // Verbatim is valid only when the selected text cannot close the environment.
    return {value:format==='markdown'?fence+'text\n'+text+'\n'+fence:format==='latex'?(text.includes('\\end{verbatim}')?escapeLatex(text):'\\begin{verbatim}\n'+text+'\n\\end{verbatim}'):text,block:true};
   }
   if(tag==='code'){
    const text=plainSource(children),fence='`'.repeat(Math.max(1,...(text.match(/`+/g)||[]).map(x=>x.length+1)));
    return {value:format==='markdown'?fence+' '+text+' '+fence:format==='latex'?'\\texttt{'+escapeLatex(text)+'}':text,block:false};
   }
   if(tag==='table'){
    const rows=children.flatMap(n=>descendants(n,'tr')).map(row=>row.children.filter((c):c is Extract<CopyNode,{kind:'element'}>=>c.kind==='element'&&(c.tag==='td'||c.tag==='th')));
    const width=rows[0]?.length||0;
    const cells=rows.map(row=>row.map(cell=>renderChildren(cell.children,depth).trim()));
    const simple=node.complete&&node.simple&&width>0&&rows.every(row=>row.length===width)&&!rows.some(row=>row.some(cell=>unsafeTableMath(cell.children)))&&!cells.some(row=>row.some(cell=>cell.includes('\n')))&&(format!=='markdown'||rows[0].every(cell=>cell.tag==='th'));
    const caption=renderChildren(children.filter(c=>c.kind==='element'&&c.tag==='caption'),depth);
    if(!simple){notes.add('table-simplified');return {value:[caption,cells.map(row=>row.join(format==='latex'?' \\quad ':'\t')).join(format==='latex'?'\n\n':'\n')].filter(Boolean).join('\n\n'),block:true};}
    if(format==='text')return {value:[caption,cells.map(row=>row.join('\t')).join('\n')].filter(Boolean).join('\n\n'),block:true};
    if(format==='latex')return {value:[caption,'\\begin{tabular}{'+('l'.repeat(width))+'}\n'+cells.map(row=>row.join(' & ')+' \\\\').join('\n')+'\n\\end{tabular}'].filter(Boolean).join('\n\n'),block:true};
    const line=(row:string[])=>'| '+row.join(' | ')+' |';
    return {value:[caption,[line(cells[0]),line(Array.from({length:width},()=> '---')),...cells.slice(1).map(line)].join('\n')].filter(Boolean).join('\n\n'),block:true};
   }
   if(tag==='ul'||tag==='ol'){
    const entries=children.filter((c):c is Extract<CopyNode,{kind:'element'}>=>c.kind==='element'&&c.tag==='li'),ordered=tag==='ol',start=node.start||1;
    if(format==='latex'){
     const env=ordered?'enumerate':'itemize',counter=['enumi','enumii','enumiii','enumiv'][Math.min(depth,3)];
     return {value:'\\begin{'+env+'}\n'+(ordered&&start!==1?'\\setcounter{'+counter+'}{'+(start-1)+'}\n':'')+entries.map(c=>'\\item '+renderChildren(c.children,depth+1)).join('\n')+'\n\\end{'+env+'}',block:true};
    }
    return {value:entries.map((c,i)=>{const prefix=ordered?String(start+i)+'. ':'- ';return prefix+renderChildren(c.children,depth+1).replace(/\n/g,'\n'+' '.repeat(prefix.length));}).join('\n'),block:true};
   }
   let value=renderChildren(children,depth);
   if(tag==='strong'||tag==='b')value=format==='markdown'?'**'+value+'**':format==='latex'?'\\textbf{'+value+'}':value;
   else if(tag==='em'||tag==='i')value=format==='markdown'?'*'+value+'*':format==='latex'?'\\emph{'+value+'}':value;
   else if(tag==='sub'||tag==='sup')value=format==='markdown'?'<'+tag+'>'+value+'</'+tag+'>':format==='latex'?'\\text'+(tag==='sub'?'subscript':'superscript')+'{'+value+'}':(tag==='sub'?'_':'^')+'{'+value+'}';
   else if(tag==='a'&&node.href)value=format==='markdown'?'['+value+']('+destination(node.href)+')':format==='latex'?'\\href{'+escapeLatex(destination(node.href))+'}{'+value+'}':value===node.href?value:value+' ('+node.href+')';
   else if(/^h[1-6]$/.test(tag)){
    const level=Number(tag[1]);if(format==='markdown')value='#'.repeat(level)+' '+value;
    if(format==='latex')value='\\'+['section','subsection','subsubsection','paragraph','subparagraph','subparagraph'][level-1]+'*{'+value+'}';
   }else if(tag==='blockquote')value=format==='markdown'?value.split('\n').map(line=>'> '+line).join('\n'):format==='latex'?'\\begin{quote}\n'+value+'\n\\end{quote}':value;
   return {value,block:blocks.has(tag)};
  }
  values[format]=renderChildren(nodes);warnings[format]=[...notes];
 }
 return {values,warnings};
}

