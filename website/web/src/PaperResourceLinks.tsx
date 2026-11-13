import Icon from './Icon';
import {t} from './i18n';

/** Shared file controls keep publisher readers visually identical. */
export function PaperPdfLink({href}:{href?:string}){
 return href?<a className="button detail-pdf-trigger" href={href} target="_blank" rel="noopener noreferrer"><Icon name="file"/>{t('阅读 PDF')}<Icon name="external" className="icon-trailing"/></a>:<button type="button" className="detail-pdf-trigger reading-pdf-unavailable" disabled><Icon name="file"/>{t('阅读 PDF')}</button>;
}
export function PaperSourceLink({href,label}:{href:string;label:string}){
 return <a className="button detail-source-link" href={href} target="_blank" rel="noreferrer">{t(label)}<Icon name="external" className="icon-trailing"/></a>;
}
export function PaperSourceDownload({href,label,onAcquire,pending=false,unavailable=false}:{href?:string;label:string;onAcquire?:()=>void;pending?:boolean;unavailable?:boolean}){
 return href?<a className="button detail-source-download" href={href} download><Icon name="download"/>{t(label)}</a>:<button type="button" className="detail-source-download" disabled={!onAcquire||pending||unavailable} onClick={onAcquire} aria-busy={pending||undefined}><Icon name="download"/>{t(label)}</button>;
}
