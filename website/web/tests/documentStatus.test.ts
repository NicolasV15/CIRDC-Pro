import assert from 'node:assert/strict';
import {test} from 'node:test';
import {contentCurrentError} from '../src/documentStatus.ts';

test('node failover and successful results do not retain a current error banner',()=>{
 assert.equal(contentLabel({state:'recovered',job:{kind:'ieee_pdf'}}),'已完成');
 for(const state of ['queued','fetching','body_ready','ready','source_no_body'])assert.equal(contentCurrentError({state,job:{state,error:'source_route_mismatch'}}),'');
 assert.equal(contentCurrentError({state:'ready',document:{source:'ieee_html'},job:{state:'failed',error:'access_restricted'}}),'access_restricted');
 assert.equal(contentCurrentError({state:'partial',job:{state:'partial',error:'assets_incomplete'}}),'assets_incomplete');
});
import {contentLabel,contentPending,shouldEnsureContent,pdfRetryable,assetsRetryable,contentReason,contentDocumentReady} from '../src/documentStatus.ts';
test('an absent publisher body is checked again when a reader opens the article',()=>{
 assert.equal(shouldEnsureContent({state:'source_no_body',job:{kind:'ieee_html',state:'source_no_body'}}),true);
 assert.equal(shouldEnsureContent({state:'ready',document:{source:'ieee_html'}}),false);
 assert.equal(shouldEnsureContent({state:'ready',document:{source:'pdf_parse'}}),false);
});
test('PDF failures require an explicit retry and active jobs keep polling',()=>{
 const value={state:'failed',job:{kind:'pdf_parse',state:'failed'}};
 assert.equal(shouldEnsureContent(value),false);assert.equal(pdfRetryable(value),true);
 assert.equal(contentPending(value),false);
 for(const state of ['queued','fetching']){
  const active={state,job:{state,kind:'pdf_parse'}};
  assert.equal(contentPending(active),true);assert.equal(shouldEnsureContent(active),false);
 }
});
test('publisher and converted content have distinct labels without hiding cached content',()=>{
 assert.equal(contentLabel({state:'fetching',job:{kind:'pdf_parse'}}),'正在转换 PDF');
 assert.equal(contentLabel({state:'fetching',job:{kind:'ieee_html'}}),'正在获取正文');
 assert.equal(contentLabel({state:'ready',document:{source:'pdf_parse'}}),'PDF 转换正文');
 assert.equal(contentLabel({state:'ready',document:{source:'ieee_html'},job:{kind:'pdf_parse',state:'failed'}}),'共享正文已缓存');
 assert.equal(contentReason({state:'source_no_body',result:{reason:'local_pdf_missing'}}),'官网未提供在线正文，本地尚无 PDF。');
});

test('original PDF acquisition is independent and keeps absent-body readers polling',()=>{
 const pending={state:'source_no_body',job:{kind:'ieee_html',state:'source_no_body'},pdf_acquisition:{state:'fetching'}};
 assert.equal(contentPending(pending),true);assert.equal(contentLabel(pending),'正在获取 PDF');
 assert.equal(contentLabel({...pending,state:'ready',document:{source:'ieee_html'}}),'共享正文已缓存');
 assert.equal(contentLabel({state:'ready',job:{kind:'ieee_pdf',state:'ready'}}),'PDF 已就绪');
});

test('a downloaded original hands polling to the existing conversion task',()=>{
 const state={state:'queued',job:{kind:'pdf_parse',state:'queued'},pdf_acquisition:{state:'ready'}};
 assert.equal(contentLabel(state),'等待 PDF 转换');assert.equal(contentPending(state),true);
});

test('only inactive incomplete publisher images offer an image retry',()=>{
 const value={state:'partial',document:{source:'ieee_html'},job:{state:'partial'}};
 assert.equal(assetsRetryable(value),true);
 assert.equal(assetsRetryable({...value,job:{state:'fetching'}}),false);
});

test('background follow-up waits until a cached body has finished publishing',()=>{
 assert.equal(contentDocumentReady({state:'body_ready',document:{source:'ieee_html'}}),false);
 assert.equal(contentDocumentReady({state:'ready'}),false);
 assert.equal(contentDocumentReady({state:'ready',document:{source:'ieee_html'}}),true);
 assert.equal(contentDocumentReady({state:'partial',document:{source:'ieee_html'}}),true);
 assert.equal(contentDocumentReady({state:'ready',document:{source:'pdf_parse'}}),true);
});

test("a confirmed unavailable PDF does not repeatedly request a body fallback",()=>{
 const value={state:"source_no_body",job:{kind:"ieee_html",state:"source_no_body"},pdf_acquisition:{state:"unavailable"}};
 assert.equal(shouldEnsureContent(value),false);assert.equal(contentPending(value),false);
 assert.equal(contentReason(value),"官网无在线正文，PDF 因机构未授权不可获取。");
});

test('confirmed institutional PDF denial is an availability outcome rather than a retrieval failure',()=>{
 assert.equal(contentLabel({state:'unavailable',job:{kind:'ieee_pdf',state:'unavailable',error:'pdf_not_entitled'}}),'PDF 不可获取（机构未授权）');
 assert.equal(contentPending({state:'unavailable',job:{kind:'ieee_pdf',state:'unavailable'}}),false);
});
