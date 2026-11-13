export type ResourceCoverage={id:string;label?:string;label_i18n?:Record<string,string>;numerator:number|null;denominator?:number|null;status:string;sampled_at?:string;note?:string;note_i18n?:Record<string,string>;institution_not_licensed?:number|null};
export function coverageDisplay(metric:ResourceCoverage|undefined,total:number,language:string){
 const count=metric?.status==='ready'&&typeof metric.numerator==='number'&&Number.isInteger(metric.numerator)&&metric.numerator>=0?metric.numerator:null;
 const denominator=metric&&'denominator' in metric?metric.denominator:total;
 const valid=count!==null&&typeof denominator==='number'&&Number.isInteger(denominator)&&denominator>0&&count<=denominator;
 return {count,denominator,rate:valid?new Intl.NumberFormat(language,{style:'percent',minimumFractionDigits:2,maximumFractionDigits:2}).format(count/denominator):'—'};
}
export function institutionalCoverage(metric:ResourceCoverage|undefined,total:number,language:string){
 const coverage=coverageDisplay(metric,total,language),count=metric?.institution_not_licensed;
 if(coverage.rate==='—'||typeof count!=='number'||!Number.isInteger(count)||count<0||count>(coverage.denominator as number)-(coverage.count as number))return null;
 const ratio=count/(coverage.denominator as number);
 return {count,rate:new Intl.NumberFormat(language,{style:'percent',minimumFractionDigits:2,maximumFractionDigits:ratio>0&&ratio<0.0001?4:2}).format(ratio)};
}
