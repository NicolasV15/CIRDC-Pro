import {t,locale} from './i18n';
import {failureReason,requestLabel,type Feedback} from './resourceRecovery';
export function ResourceFeedback({value,request}:{value?:Feedback;request?:Feedback}){
 const reason=failureReason(value),apiReason=failureReason(request);
 return <span className="resource-feedback" role="status">
  {request&&<span className="hint resource-request-status">{t(requestLabel(request))}{apiReason?' · '+t(apiReason):''}{request.next_action==='wait'&&t('；将在 {seconds} 秒后再次查询',{seconds:String(request.retry_after_seconds||5)})}</span>}
  {reason&&<span className="hint">{t(reason)}</span>}
  {value?.next_retry_at!=null&&value.next_action==='wait'&&<span className="hint">{t('后台下次获取重试：')}{new Date(value.next_retry_at*1000).toLocaleString(locale())}</span>}
  {typeof value?.retry_attempts==='number'&&value.max_retry_attempts!=null&&<span className="hint">{t('已实际重试 {used}/{max} 次',{used:String(value.retry_attempts),max:String(value.max_retry_attempts??'—')})}</span>}
 </span>;
}
