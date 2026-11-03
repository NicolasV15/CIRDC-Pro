import type {ReactNode} from 'react';

// One stroke icon set keeps actions recognizable across pages and themes.
const shapes={
 search:<><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/></>,
 filter:<><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></>,
 text:<path d="M3.5 18 8.5 6l5 12M5.3 14h6.4M15 18l3-7 3 7M15.9 16h4.2"/>,
 quote:<path d="M10 11H6V7h4v4c0 3.4-1.4 5.4-4.3 6.4M19.5 11h-4V7h4v4c0 3.4-1.4 5.4-4.3 6.4"/>,
 file:<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></>,
 external:<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>,
 back:<path d="M19 12H5M11 6l-6 6 6 6"/>,
 down:<path d="m6 9 6 6 6-6"/>,
 right:<path d="m9 6 6 6-6 6"/>,
 close:<path d="M6 6l12 12M18 6 6 18"/>,
 check:<path d="m5 12.5 4.5 4.5L19 7.5"/>,
 menu:<path d="M4 7h16M4 12h16M4 17h16"/>,
 appearance:<><circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17Z" className="icon-fill"/></>,
 info:<><circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.2"/></>,
 download:<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>,
 copy:<><rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/></>,
 lock:<><rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></>,
 terminal:<><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="m7.5 9.5 3 2.5-3 2.5M13 15h3.5"/></>,
 server:<><rect x="4" y="4" width="16" height="7" rx="1.5"/><rect x="4" y="13" width="16" height="7" rx="1.5"/><path d="M8 7.5h.01M8 16.5h.01"/></>,
 link:<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>,
 book:<><path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v14H7.5A2.5 2.5 0 0 0 5 19.5Z"/><path d="M5 19.5A2.5 2.5 0 0 0 7.5 22H19v-5"/></>,
 key:<><circle cx="8" cy="15" r="4"/><path d="m11 12 8.5-8.5M16.5 6.5l2.5 2.5M14 9l2 2"/></>,
 logout:<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 8l-4 4 4 4M6 12h10"/>,
 database:<><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/></>,
 user:<><circle cx="12" cy="8" r="4"/><path d="M4.5 20.5c1.2-3.6 4.1-5.5 7.5-5.5s6.3 1.9 7.5 5.5"/></>,
} satisfies Record<string,ReactNode>;
export type IconName=keyof typeof shapes;
export default function Icon({name,className}:{name:IconName;className?:string}){
 return <svg className={'icon'+(className?' '+className:'')} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{shapes[name]}</svg>;
}
