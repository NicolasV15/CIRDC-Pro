type Resource={state:string;download_url?:string;error?:string};
export type ArxivState={state:string;reading_ready?:boolean;acquisition_complete?:boolean;resources?:Record<string,Resource>;document?:unknown;reading_state?:string;conversion_errors?:Record<string,string>;request_id?:string};

const RETRYABLE=['failed','blocked'];

/** The only upstream action the current state permits: a first request, an explicit retry of unfinished branches, or none. */
export function acquisitionAction(state:ArxivState|null):'ensure'|'retry'|null{
 if(!state)return null;
 if(state.state==='not_requested')return 'ensure';
 if(state.state!=='partial')return null;
 return Object.values(state.resources||{}).some(r=>RETRYABLE.includes(r.state))||state.reading_state==='failed'?'retry':null;
}
