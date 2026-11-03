export type CopyFormat='markdown'|'latex'|'text';
export type CopyWarning='table-simplified'|'image-link'|'source-unmapped'|'math-unavailable'|'link-omitted';
export type CopyNode={kind:'text';value:string}|{kind:'math';tex:string;display:boolean}|{kind:'image';alt:string;href:string}|{kind:'element';tag:string;children:CopyNode[];href?:string;start?:number;complete?:boolean;simple?:boolean};
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
export function hasMathEnvironment(tex:string){return /^\s*\\begin\{(?:equation\*?|align\*?|alignat\*?|flalign\*?|xalignat\*?|xxalignat|gather\*?|multline\*?|eqnarray\*?|displaymath|math)\}/.test(tex);}
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
 for(const format of ['markdown','latex','text'] as const){
  const notes=new Set(commonWarnings);
  const normal=(value:string)=>format==='latex'?escapeLatex(value):format==='markdown'?escapeMarkdown(value):value;
  const renderChildren=(children:CopyNode[],depth=0)=>join(children.map(n=>render(n,depth)));
  function render(node:CopyNode,depth=0):Piece{
   if(node.kind==='text')return {value:normal(node.value),block:false};
   if(node.kind==='math'){
    const tex=unwrappedMath(node.tex),environment=hasMathEnvironment(tex),display=node.display||environment;
    if(format==='text')return {value:tex,block:display};
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
