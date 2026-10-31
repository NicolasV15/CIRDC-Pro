type Row={number:string};
export type ResultSelection<T extends Row>={rows:T[];selected:string[]};
type Action<T extends Row>=
 | {type:'reset'}
 | {type:'replace'|'append';rows:T[]}
 | {type:'all';checked:boolean}
 | {type:'select';numbers:string[];checked:boolean};

/** Rows and their checks change atomically; off-screen selections cannot survive. */
export function resultSelection<T extends Row>(state:ResultSelection<T>,action:Action<T>):ResultSelection<T>{
 if(action.type==='reset')return {rows:[],selected:[]};
 if(action.type==='replace'||action.type==='append'){
  const rows=[...new Map((action.type==='append'?[...state.rows,...action.rows]:action.rows).map(row=>[row.number,row])).values()];
  return {rows,selected:action.type==='replace'?[]:state.selected.filter(number=>rows.some(row=>row.number===number))};
 }
 if(action.type==='all')return {...state,selected:action.checked?state.rows.map(row=>row.number):[]};
 if(action.type==='select'){
  const requested=new Set(action.numbers),old=new Set(state.selected);
  return {...state,selected:state.rows.filter(row=>requested.has(row.number)?action.checked:old.has(row.number)).map(row=>row.number)};
 }
 return state;
}
