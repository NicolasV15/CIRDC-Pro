import {locale,t} from './i18n';

type PublicationYear={name:string|null;num_records:number|null};
const yearOrder=(name:string|null)=>/^\d{4}$/.test(name||'')?Number(name):Infinity;

export default function AuthorPublicationYears({years}:{years:readonly PublicationYear[]}){
 if(!years.length)return null;
 const rows=[...years].sort((a,b)=>{
  const first=yearOrder(a.name),second=yearOrder(b.name);
  return first===second?0:first<second?-1:1;
 });
 if(rows.some(row=>row.num_records!==null&&(!Number.isInteger(row.num_records)||row.num_records<0)))throw new Error('Invalid author publication count');
 const maximum=Math.max(1,...rows.map(row=>row.num_records??0));
 return <figure className="author-year-chart">
  <figcaption>{t('IEEE 论文数')}</figcaption>
  <div className="author-year-scroll" tabIndex={0} role="region" aria-label={t('发表年份分布')}>
   <ul className="author-year-bars" role="list" style={{gridTemplateColumns:`repeat(${rows.length},minmax(44px,1fr))`,minWidth:rows.length*44}}>
    {rows.map((row,index)=>{
     const year=row.name??'—',count=row.num_records===null?'—':row.num_records.toLocaleString(locale());
     const height=row.num_records===null?0:row.num_records/maximum*100;
     const description=year+' · '+t('IEEE 论文数')+': '+(row.num_records===null?t('来源未提供'):count);
     return <li className="author-year-column" key={index} title={description} aria-label={description}>
      <span className="author-year-track" aria-hidden="true"><span className="author-year-count" style={{bottom:`calc(${height}% + 4px)`}}>{count}</span>{row.num_records!==null&&<span className="author-year-bar" style={{height:height+'%'}}/>}</span>
      <span className="author-year-label" aria-hidden="true">{year}</span>
     </li>;
    })}
   </ul>
  </div>
 </figure>;
}
