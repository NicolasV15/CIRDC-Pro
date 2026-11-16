export type CitationSummary={count:number|null;absent:boolean};

type CitationNotice={kind:'papers'|'patents';state:string;absent:boolean;count:number|undefined;hasSnapshot:boolean;hasItems:boolean;stale:boolean;error:string|null};
/** One visible status, without treating unavailable or failed source counts as zero. */
export function citationNotice(value:CitationNotice):string{
 const {kind,state,absent,count,hasSnapshot,hasItems,stale,error}=value;
 if(state==='queued')return '等待更新';
 if(state==='fetching')return '正在更新…';
 if(state==='blocked')return hasSnapshot?'访问受限':'访问受限，数量待确认。';
 if(state==='failed'||error)return hasSnapshot?'更新未完成':'更新未完成，数量待确认。';
 if(state==='partial')return '部分记录待补齐。';
 if(state==='disabled')return kind==='papers'?'被引论文功能尚未启用':'专利被引功能尚未启用';
 if(absent)return kind==='papers'?'官网未提供被引论文':'官网未提供专利被引';
 if((state==='unavailable'||state==='no_data')&&count===undefined)return '来源状态待确认';
 if(count===0&&!hasItems)return kind==='papers'?'暂无被引论文（0 条）':'暂无专利被引（0 条）';
 if(state==='missing')return kind==='papers'?'被引论文尚未获取':'专利被引尚未获取';
 if(stale)return '结果待更新';
 if(state==='complete')return '已收录';
 return kind==='papers'?'被引论文状态暂不可用':'专利被引状态暂不可用';
}

export function citationTime(value:{checked_at:string|null;last_attempt_at:string|null}|null){
 if(value?.checked_at)return {value:value.checked_at,checked:true};
 if(value?.last_attempt_at)return {value:value.last_attempt_at,checked:false};
}
