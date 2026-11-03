import assert from 'node:assert/strict';
import {test} from 'node:test';
import {citationNotice,citationTime} from '../src/citationSummary.ts';

const ready={kind:'papers' as const,state:'complete',absent:false,count:5,hasSnapshot:true,hasItems:true,stale:false,error:null};
test('a single notice distinguishes publisher absence, confirmed zero and unknown counts',()=>{
 assert.equal(citationNotice({...ready,state:'no_data',absent:true,count:undefined,hasItems:false}),'官网未提供被引论文栏目');
 assert.equal(citationNotice({...ready,kind:'patents',state:'no_data',absent:true,count:undefined,hasItems:false}),'官网未提供专利被引栏目');
 assert.equal(citationNotice({...ready,count:0,hasItems:false}),'已确认没有被引论文');
 assert.equal(citationNotice({...ready,kind:'patents',count:0,hasItems:false}),'官网当前记录 0 条专利被引');
 assert.equal(citationNotice({...ready,state:'unavailable',count:undefined,hasItems:false}),'来源状态待确认');
});
test('latest attempt failures and pending work are visible even when the saved snapshot records absence',()=>{
 assert.equal(citationNotice({...ready,state:'fetching',absent:true}),'正在更新，显示已有结果。');
 assert.equal(citationNotice({...ready,state:'failed',absent:true}),'更新未完成，已有结果仍可查看。');
 assert.equal(citationNotice({...ready,state:'blocked',absent:true}),'访问受限，已有结果仍可查看。');
 assert.equal(citationNotice({...ready,state:'failed',hasSnapshot:false,count:undefined}),'更新未完成，数量待确认。');
 assert.equal(citationNotice({...ready,state:'partial'}),'部分记录待补齐。');
});
test('one displayed time belongs to the saved snapshot; an attempt is never presented as a successful check',()=>{
 const page=Object.freeze({checked_at:'2026-10-20T00:00:00Z',last_attempt_at:'2026-11-01T00:00:00Z'});
 assert.deepEqual(citationTime(page),{value:page.checked_at,checked:true});
 assert.deepEqual(citationTime({...page,checked_at:null}),{value:page.last_attempt_at,checked:false});
 assert.equal(citationTime({checked_at:null,last_attempt_at:null}),undefined);assert.equal(citationTime(null),undefined);
});
test('concise citation labels and every notice remain bilingual',async()=>{
 Object.assign(globalThis,{document:{documentElement:{lang:''},title:''},window:{addEventListener:()=>{}}});
 const {setLanguage,t}=await import('../src/i18n.ts');setLanguage('en');
 assert.equal(t('论文引用'),'By Papers');assert.equal(t('专利引用'),'By Patents');assert.equal(t('检查：{time}',{time:'DATE'}),'Checked: DATE');
 for(const kind of ['papers','patents'] as const)for(const state of ['queued','fetching','blocked','failed','partial','disabled','missing','unavailable','no_data','complete']){
  for(const hasSnapshot of [true,false])for(const absent of [true,false]){
   const key=citationNotice({...ready,kind,state,hasSnapshot,absent,count:state==='unavailable'?undefined:0,hasItems:false});assert(!/[\u3400-\u9fff]/.test(t(key)),key);
  }
 }
 setLanguage('zh');assert.equal(t('By Papers'),'论文引用');assert.equal(t('By Patents'),'专利引用');
});
