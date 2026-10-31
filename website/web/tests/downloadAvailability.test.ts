import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readPdfHead,checkDownloads,downloadGroups,safeResourceHref,type FileCheck} from '../src/downloadAvailability.ts';
import {loadPapers,type LoadedPaper} from '../src/paperBatch.ts';
const resource=(number:string)=>({id:number,href:'/api/resources/local/'+number,media_type:'application/pdf',archive_prepare_href:'/api/resources/local/archives'});
const item=(number:string):LoadedPaper=>({number,paper:{number,record:{articleTitle:'A paper'},resources:[resource(number)]}});
const head=(status:number,type='application/pdf',length='500')=>({status,headers:new Headers({'content-type':type,'content-length':length})});
test('preview requires real nonempty PDF HEAD, not metadata flags or a generic document link',async()=>{
 const inputs=Array.from({length:11},(_,i)=>item(String(i+1)));inputs[7].paper.resources=[{...resource('8'),kind:'document'}];inputs[8].paper.resources=[];inputs[9].paper.resources=[{...resource('10'),href:'https://outside/file'}];
 const responses=[head(200),head(404),head(503),head(200,'text/html'),head(200,'application/pdf','0'),head(405),head(302)];const calls:string[]=[];
 const checks=await checkDownloads(inputs,async path=>{calls.push(path);if(path.endsWith('/11'))throw Error('network');return responses[Number(path.split('/').pop())-1];});
 assert.deepEqual(checks.map(c=>c.status),['ready','file_missing','file_unavailable','unverified','unverified','unverified','unverified','not_available','not_available','not_available','file_unavailable']);assert.equal(calls.length,8);
 assert.equal(safeResourceHref('//evil/'),null);assert.equal(safeResourceHref('/api/resources/\\evil'),null);
});
test('file checks are bounded, cancellable and preserve result order',async()=>{
 let active=0,maximum=0,stopped=false;const inputs=Array.from({length:30},(_,i)=>item(String(i)));
 const checks=await checkDownloads(inputs,async()=>{active++;maximum=Math.max(active,maximum);await new Promise(resolve=>setTimeout(resolve,2));active--;return head(200);},done=>{if(done===4)stopped=true;},()=>stopped);
 assert(maximum<=3);assert(checks.length>=4&&checks.length<=6);assert.deepEqual(checks.map(c=>c.number),inputs.slice(0,checks.length).map(c=>c.number));
});
test('over 100 loaded choices are read fully and split into bounded explicit archives; never send unavailable files',async()=>{
 const ids=Array.from({length:225},(_,i)=>String(i+1));const loaded=await loadPapers(ids,async path=>({paper:item(path.split('/').pop()!).paper}));assert.equal(loaded.items.length,225);
 const names=ids.map(number=>({number,filename:number+'.pdf'})),checks:FileCheck[]=ids.map(number=>({number,status:'ready',resource:resource(number)}));checks[30].status='file_missing';checks[101].status='unverified';
 const groups=downloadGroups(names,checks);assert.deepEqual(groups.map(g=>g.ready),[99,99,25]);assert(groups.every(g=>g.items.length<=100));const sent=groups.flatMap(g=>g.items.map(i=>i.number));assert.equal(sent.length,223);assert(!sent.includes('31')&&!sent.includes('102'));assert.equal(new Set(sent).size,223);
 checks.forEach(c=>c.status='not_available');assert.deepEqual(downloadGroups(names,checks),[]);
});

test('HEAD timeout and dialog cancellation abort the reader and clear their resources',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=(_input,init)=>new Promise((_resolve,reject)=>{const signal=init!.signal!;const abort=()=>reject(new Error('aborted'));signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();});
 try{
  await assert.rejects(readPdfHead('/api/resources/test',new AbortController().signal,5),/aborted/);
  const controller=new AbortController(),pending=readPdfHead('/api/resources/test',controller.signal);controller.abort();await assert.rejects(pending,/aborted/);
  const before=new AbortController();before.abort();await assert.rejects(readPdfHead('/api/resources/test',before.signal),/aborted/);
 }finally{globalThis.fetch=original;}
});
test('provider failure is unknown, never mislabeled as no registered PDF',async()=>{
 const input=item('1');input.paper.resources=[];input.paper.resource_notice='Unavailable';const checked=await checkDownloads([input],async()=>{throw Error('should not run')});assert.equal(checked[0].status,'unverified');
});
