// Some PDF exports append an equation number already present in their TeX.
// Only identical adjacent tags are redundant; conflicting numbers stay visible.
export function documentMathForDisplay(tex:string){
 return tex.replace(/(\\tag\s*\{([^{}]*)\})(?:\s*\\tag\s*\{\2\})+/g,'$1');
}
