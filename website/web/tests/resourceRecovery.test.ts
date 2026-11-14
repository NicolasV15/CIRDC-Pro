import {test,beforeEach} from 'node:test';
import assert from 'node:assert/strict';
import {ResourceFlow,queryDelay,recoveryLabel,requestLabel,terminal,failureReason} from '../src/resourceRecovery.ts';
const href='/api/content/100',id='a'.repeat(32);
const failure=(value:any)=>Object.assign(Error('fixture'),{value});
// Node 25+ provides a process-wide sessionStorage; saved receipts must not leak between tests.
beforeEach(()=>{globalThis.sessionStorage?.clear();});
test('API acceptance, backend state and recovery time are independent',()=>{
 assert.equal(requestLabel({accepted:null}),'接口未及时返回，是否已受理尚未确认');
 assert.equal(requestLabel({accepted:false}),'本次请求未受理');
 assert.equal(recoveryLabel({next_action:'wait',phase:'ieee_pdf:queued'}),'任务已排队');
 assert.equal(recoveryLabel({next_action:'wait',phase:'ieee_html:fetching'}),'任务处理中');
 assert.equal(recoveryLabel({next_action:'wait',next_retry_at:1800000000,job:{state:'failed'}}),'等待自动重试');
 assert.equal(queryDelay({retry_after_seconds:7,next_retry_at:1800000000}),7000);
 assert(!failureReason({reason:'resource_service_unavailable'}).includes('繁忙'));
 assert(failureReason({reason:'capacity_limited'}).includes('繁忙'));
 for(const value of [{next_action:'stop'},{next_action:'contact_administrator'},{state:'unavailable'}])assert(terminal(value));
});
test('unknown submission reads first, ordinary ensure reattaches, and receipt polling never submits',async()=>{
 const calls:any[]=[];let submits=0;
 const api=async(path:string,method='GET',data?:any)=>{
  calls.push({path,method,data});
  if(method==='POST'){if(++submits===1)throw failure({accepted:null,next_action:'wait',retry_after_seconds:5});return {request_id:id,resources:{content:{state:'pending'}}};}
  return path.includes('/requests/')?{resources:{content:{state:'pending',next_action:'wait',retry_after_seconds:4}}}:{state:'missing'};
 };
 const flow=new ResourceFlow(href,'content',api);
 await assert.rejects(flow.submit(true));assert.equal(flow.failure?.accepted,null);
 await flow.read();assert.equal(submits,2);assert.equal(calls[1].method,'GET');assert.equal(calls[2].data.automatic,false);
 const count=calls.length;await flow.read();assert.equal(submits,2);assert.equal(calls[count].path,'/api/agent/v1/requests/'+id);
 assert.equal(calls.filter(v=>v.data?.retry===true).length,0);
});
test('unknown acceptance reads the active job then joins its receipt without repeating retry',async()=>{
 let posts=0;
 const flow=new ResourceFlow(href,'content',async(path,method)=>{
  if(method==='POST'){posts++;if(posts===1)throw failure({accepted:null,next_action:'wait'});return {request_id:id};}
  if(path.includes('/requests/'))return {resources:{content:{state:'pending',next_action:'wait'}}};
  return {state:'fetching',job:{state:'fetching'}};
 });
 await assert.rejects(flow.submit());for(let i=0;i<4;i++)assert.equal((await flow.read()).state,'fetching');assert.equal(posts,2);
});
test('receipt on an API failure is retained and only that receipt is queried',async()=>{
 const calls:string[]=[];
 const flow=new ResourceFlow(href,'content',async(path,method)=>{calls.push(path);if(method==='POST')throw failure({request_id:id,accepted:true,next_action:'wait'});if(path.includes('/requests/'))throw failure({next_action:'wait'});throw Error('must not reach the legacy read');});
 await assert.rejects(flow.submit());await assert.rejects(flow.read());assert.equal(calls[1],'/api/agent/v1/requests/'+id);assert.equal(flow.failure?.request_id,id);
});

test('a known terminal receipt stops recovery even if the rendering status read fails',async()=>{
 const flow=new ResourceFlow(href,'content',async(path,method)=>{
  if(method==='POST')return {request_id:id};
  if(path.includes('/requests/'))return {resources:{content:{state:'failed',next_action:'contact_administrator',retry_attempts:10,max_retry_attempts:10}}};
  throw failure({error:'resource_service_unavailable',next_action:'wait'});
 });
 await flow.submit();const value=await flow.read();assert(terminal(value));assert.equal(flow.failure?.next_action,'stop');
});
test('a transient initial status failure recovers with a cached read before ordinary ensure',async()=>{
 const calls:string[]=[];let reads=0;
 const flow=new ResourceFlow(href,'content',async(path,method='GET')=>{
  calls.push(method+' '+path);
  if(method==='POST')return {request_id:id};
  if(path.includes('/requests/'))return {resources:{content:{state:'pending'}}};
  if(++reads===1)throw failure({error:'resource_service_unavailable',next_action:'wait'});
  return {state:'missing'};
 });
 await assert.rejects(flow.read());await flow.read();assert.equal(calls[1],'GET '+href);assert(calls[2].startsWith('POST '));
});


test('normal PDF download and persistence have accurate progress labels',()=>{
 for(const phase of ['downloading','ieee_pdf:fetching'])assert.equal(recoveryLabel({state:'pending',phase,next_action:'wait',job:{state:'fetching'}}),'正在下载 PDF');
 for(const phase of ['uploading','publishing','registering'])assert.equal(recoveryLabel({state:'fetching',phase,next_action:'wait'}),'正在保存 PDF');
 assert.equal(recoveryLabel({state:'pending',phase:'waiting_node',next_action:'wait'}),'等待下载服务就绪');
});
test('PDF availability is explicit while waiting for and generating full text',()=>{
 assert.equal(recoveryLabel({state:'source_no_body',phase:'conversion_pending',next_action:'wait',job:{kind:'ieee_pdf',state:'ready'}}),'PDF 已获取，等待生成正文');
 assert.equal(recoveryLabel({state:'queued',phase:'pdf_parse:queued',next_action:'wait',job:{kind:'pdf_parse',state:'queued'}}),'PDF 已获取，等待生成正文');
 assert.equal(recoveryLabel({state:'fetching',phase:'pdf_parse:fetching',next_action:'wait',job:{kind:'pdf_parse',state:'fetching'}}),'PDF 已获取，正在生成正文');
 assert.equal(recoveryLabel({state:'body_ready',phase:'pdf_parse:body_ready',next_action:'wait',job:{kind:'pdf_parse',state:'body_ready'}}),'正文已就绪，正在补齐图片');
});
test('only a scheduled retry claims to be waiting for automatic retry',()=>{
 for(const phase of ['retry_wait','assets_retry_wait']){
  assert.equal(recoveryLabel({state:'pending',phase,next_action:'wait',next_retry_at:1800000000}),'等待自动重试');
  assert.equal(recoveryLabel({state:'pending',phase,next_action:'wait'}),'等待任务状态更新');
 }
 assert.equal(recoveryLabel({next_action:'wait'}),'等待任务状态更新');
 assert.equal(recoveryLabel({next_action:'wait',phase:'unknown',job:{state:'queued'}}),'任务已排队');
});
test('cached availability and terminal states are not described as recovery',()=>{
 assert.equal(recoveryLabel({state:'ready',phase:'downloading',next_action:'wait'}),'');
 assert.equal(recoveryLabel({state:'unavailable',phase:'downloading',next_action:'wait'}),'已确认不可获取');
 assert.equal(recoveryLabel({state:'failed',next_action:'contact_administrator'}),'需要管理员处理');
 assert.equal(recoveryLabel({next_action:'stop'}),'获取已停止');
});
test('normal PDF-to-body handoff keeps polling without creating another request',async()=>{
 const values:any[]=[
  {state:'source_no_body',phase:'downloading',next_action:'wait',job:{kind:'ieee_html',state:'source_no_body'},pdf_acquisition:{state:'fetching'}},
  {state:'source_no_body',phase:'conversion_pending',next_action:'wait',job:{kind:'ieee_html',state:'source_no_body'},pdf_acquisition:{state:'ready'}},
  {state:'fetching',phase:'pdf_parse:fetching',next_action:'wait',job:{kind:'pdf_parse',state:'fetching'}},
  {state:'ready',document:{source:'pdf_parse'}}
 ];
 const methods:string[]=[];
 const flow=new ResourceFlow(href,'content',async(_path,method='GET')=>{methods.push(method);return values.shift();});
 const labels=[];for(let i=0;i<4;i++)labels.push(recoveryLabel(await flow.read()));
 assert.deepEqual(labels,['正在下载 PDF','PDF 已获取，等待生成正文','PDF 已获取，正在生成正文','']);
 assert.deepEqual(methods,['GET','GET','GET','GET']);
});
