import assert from 'node:assert/strict';
import {test} from 'node:test';
import {pdfStateLabel,refreshLabel,pdfRetryState} from '../src/resourceDiagnostics.ts';

test('PDF unavailability and unresolved exceptions have separate labels',()=>{
 assert.equal(pdfStateLabel('unavailable'),'已确认不可获取（机构未授权）');
 assert.equal(pdfStateLabel('failed'),'其他待处理异常');
});

test('fixed retry deadline is shown only for eligible pending work, while exhaustion requires manual handling',()=>{
 const due={auto_attempts:1,auto_max_attempts:3,auto_retry_eligible:true,next_retry_at:1800021600};
 assert.deepEqual(pdfRetryState(due),{label:'等待自动重试',nextAt:1800021600});
 assert.deepEqual(pdfRetryState({...due,auto_attempts:3,auto_retry_exhausted:true}),{label:'次数耗尽，待人工处理',nextAt:null});
 assert.deepEqual(pdfRetryState({...due,auto_retry_eligible:false}),{label:'待人工处理',nextAt:null});
});

test('a failed refresh with an existing PDF is distinct from an ordinary missing PDF',()=>{
 assert.equal(refreshLabel({is_refresh:true,state:'failed',availability_state:'ready'}),'已有 PDF，更新检查未完成');
 assert.equal(refreshLabel({is_refresh:true,state:'fetching',availability_state:'ready'}),'已有 PDF，正在检查更新');
 assert.equal(refreshLabel({is_refresh:true,state:'ready',availability_state:'ready'}),'PDF 更新检查完成');
 assert.equal(refreshLabel({is_refresh:true,state:'failed',availability_state:'failed'}),null);
 assert.equal(refreshLabel({state:'failed'}),null);
});

test('a dispatched retry is queued until a worker starts it, with no acquisition retry date',()=>{
 assert.deepEqual(pdfRetryState({attempt_state:'queued',auto_attempts:0,auto_retry_eligible:true,next_retry_at:1800021600}),{label:'任务已排队',nextAt:null});
 assert.deepEqual(pdfRetryState({attempt_state:'fetching',auto_attempts:1,auto_retry_eligible:true}),{label:'任务处理中',nextAt:null});
});
