export type ContentState={message?:string;next_action?:string;pdf_acquisition?:{state?:string};state?:string;job?:{state?:string;kind?:string;error?:string};document?:{source?:string};result?:{reason?:string}};
const sourceLabels:Record<string,string>={missing:'正文尚未缓存',queued:'等待采集节点',fetching:'正在获取正文',body_ready:'正文已就绪，正在补齐图片',ready:'共享正文已缓存',source_no_body:'检查完成，官网无正文',partial:'部分资源未完成',failed:'当前节点未能取得正文'};
const pdfLabels:Record<string,string>={queued:'等待 PDF 转换',fetching:'正在转换 PDF',body_ready:'正在保存 PDF 转换结果',ready:'PDF 转换正文',partial:'部分资源未完成',failed:'PDF 转换失败'};
export function contentLabel(value?:ContentState){
 if(value?.next_action==='wait')return '后台服务繁忙，请求高峰期，请重新尝试获取';
 if(value?.next_action==='contact_administrator')return '后台服务繁忙，请求高峰期，请重新尝试获取';
 if(value?.state==='recovered')return '已完成';
 if(value?.job?.kind==='ieee_pdf')return ({queued:'PDF 等待获取',fetching:'正在获取 PDF',ready:'PDF 已就绪',failed:'PDF 获取失败',unavailable:'PDF 不可获取（机构未授权）'} as Record<string,string>)[value.state||'']||'获取 PDF';
 if(value?.pdf_acquisition&&!value.document&&value.job?.kind!=='pdf_parse'&&['queued','fetching','failed'].includes(value.pdf_acquisition.state||''))return ({queued:'PDF 等待获取',fetching:'正在获取 PDF',failed:'PDF 获取失败'} as Record<string,string>)[value.pdf_acquisition.state||'']||'正在检查共享正文';
 if(value?.document?.source==='pdf_parse'&&value.state==='ready')return 'PDF 转换正文';
 if(value?.job?.kind==='pdf_parse'&&!value.document)return pdfLabels[value.state||'']||'正在检查共享正文';
 return sourceLabels[value?.state||'']||'正在检查共享正文';
}
export function contentPending(value:ContentState){if(value.next_action==='wait')return true;if(!value.document&&['queued','fetching'].includes(value.pdf_acquisition?.state||''))return true;return ['queued','fetching','body_ready'].includes(value.job?.state||value.state||'');}
export function contentCurrentError(value?:ContentState){if(value?.next_action==='wait')return '';if(value?.next_action==='contact_administrator')return '后台服务繁忙，请求高峰期，请重新尝试获取';return value?.job?.error&&['failed','partial'].includes(value.job.state||value.state||'')?value.job.error:'';}
export function shouldEnsureContent(value:ContentState){
 if(value.next_action)return false;
 if(value.pdf_acquisition?.state==="unavailable")return false;
 if(value.document||contentPending(value))return false;
 if(value.job?.kind==='pdf_parse')return false;
 return !value.job||['missing','failed','source_no_body'].includes(value.state||'');
}
export function pdfRetryable(value?:ContentState){return !value?.next_action&&!value?.document&&value?.job?.kind==='pdf_parse'&&value.state==='failed';}
export function contentDocumentReady(value?:ContentState){return !!value?.document&&['ready','partial'].includes(value.state||'');}
export function contentReason(value?:ContentState){
 if(value?.message)return value.message;
 if(value?.pdf_acquisition?.state==="unavailable"&&!value.document)return "官网无在线正文，PDF 因机构未授权不可获取。";
 if(value?.pdf_acquisition&&!value.document&&['queued','fetching'].includes(value.pdf_acquisition.state||''))return '官网无在线正文，正在获取原始 PDF，随后转换正文。';
 if(value?.pdf_acquisition?.state==='failed'&&value.job?.kind!=='pdf_parse')return 'PDF 获取未完成，请稍后重试。';
 const reasons:Record<string,string>={local_pdf_missing:'官网未提供在线正文，本地尚无 PDF。',pdf_storage_unavailable:'本地 PDF 存储暂不可用，请稍后重新打开。',pdf_file_unavailable:'本地 PDF 暂不可读取，请稍后重新打开。',pdf_invalid_input:'本地 PDF 文件无效，暂时无法转换。',pdf_service_not_configured:'PDF 转换服务尚未就绪，请稍后重新打开。'};
 if(value?.result?.reason&&reasons[value.result.reason])return reasons[value.result.reason];
 if(value?.job?.kind==='pdf_parse')return value.state==='failed'?'PDF 转换未完成，可以重试；原 PDF 仍可阅读。':'转换完成后将自动显示正文，可先阅读原 PDF。';
 return value?.state==='source_no_body'?'官网未提供在线正文，正在检查本地 PDF。':'已缓存时直接读取；缺失时由固定节点自动获取本篇文章。';
}

export function assetsRetryable(value?:ContentState){return !value?.next_action&&value?.document?.source==='ieee_html'&&value.state==='partial'&&!contentPending(value);}
