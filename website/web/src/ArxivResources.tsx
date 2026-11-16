import {t,useLanguage} from './i18n';
import Icon from './Icon';
import {acquisitionAction,acquisitionPending,type ArxivState} from './arxivResourceState';

const originals:[string,string][]=[['html','HTML 原件'],['pdf','PDF'],['source','TeX 源码包']];
// `not_packaged` comes from the offline demo: the file exists upstream or not, but was not bundled.
const labels:Record<string,string>={ready:'已缓存',queued:'排队中',fetching:'获取中',not_packaged:'未打包',not_requested:'未获取',unavailable:'原站未提供',blocked:'访问受限',failed:'获取失败'};
const readingLabels:Record<string,string>={ready:'可阅读',queued:'排队中',not_packaged:'未打包',not_requested:'未生成',failed:'生成失败',unavailable:'无可用正文'};

function readingState(state:ArxivState){return state.document?'ready':state.reading_state||'not_requested';}
/** Status of the selected version's originals and reading text; cached files download as-is. */
export function ArxivResources({base,state,error,busy,onAcquire,onReload}:{base:string;state:ArxivState|null;error:string;busy:boolean;onAcquire:()=>void;onReload:()=>void}){
 useLanguage();
 const action=acquisitionAction(state),queued=acquisitionPending(state),reading=state?readingState(state):'';
 return <section className="arxiv-resources" aria-label={t('本版本资料')}>
  {!state&&!error?<p className="hint" role="status">{t('正在读取资料状态…')}</p>:state&&<ul className="arxiv-resource-list">
   {originals.map(([kind,label])=>{const value=state.resources?.[kind]?.state||'not_requested';return <li key={kind} data-state={value}><span className="arxiv-resource-name">{t(label)}</span><span className={'badge '+value}>{t(labels[value]||value)}</span>{value==='ready'&&<a className="arxiv-resource-download" href={base+'/files/'+kind} download aria-label={t('下载{name}',{name:t(label)})}><Icon name="download"/>{t('下载')}</a>}</li>;})}
   <li data-state={reading}><span className="arxiv-resource-name">{t('正文')}</span><span className={'badge '+reading}>{t(readingLabels[reading]||reading)}</span></li>
  </ul>}
  <div className="arxiv-resource-actions" role="status">
   {queued&&<span className="arxiv-resource-progress"><span className="spinner" aria-hidden="true"/>{t('正在获取资料…')}</span>}
   {action&&<button type="button" className="detail-pdf-trigger" disabled={busy} aria-busy={busy||undefined} onClick={onAcquire}>{busy?<span className="spinner" aria-hidden="true"/>:<Icon name="download"/>}{busy?t('正在提交…'):action==='retry'?t('重试未完成项'):t('获取本版本资料')}</button>}
   {state?.state==='partial'&&!action&&<span className="hint">{t('已获取全部可用资料。')}</span>}
   {error&&<span className="arxiv-resource-error">{t(error)}<button type="button" className="text-button" onClick={onReload}>{t('重新读取状态')}</button></span>}
  </div>
 </section>;
}
