import {locale} from './i18n';

export const statusNames:Record<string,string>={complete:'已完成',pending:'待补查',no_data:'来源无数据',failed:'失败',queued:'排队中',running:'运行中',blocked:'访问受限 / 已暂停',done:'已完成',completed:'已完成',partial:'部分完成',paused:'已暂停',deferred:'待后续发布',building:'首次构建中',catching_up:'追平变更中',ready:'已同步',interrupted:'进程中断'};
export const contentStateNames:Record<string,string>={complete:'已收录',pending:'待补查',no_data:'来源无数据',failed:'失败'};
export const fmt=(n:number|undefined)=>Number(n||0).toLocaleString(locale());
// Server times without an explicit offset are recorded in China Standard Time.
export const time=(s:string|undefined)=>s?new Date(s.replace(' ','T')+(/(?:Z|[+-]\d{2}:\d{2})$/.test(s)?'':'+08:00')).toLocaleString(locale()):'—';
