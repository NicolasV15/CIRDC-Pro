export type ResourceCoverage={id:string;label?:string;label_i18n?:Record<string,string>;numerator:number|null;denominator?:number|null;status:string;sampled_at?:string;note?:string;note_i18n?:Record<string,string>};
export function coverageDisplay(metric:ResourceCoverage|undefined,total:number,language:string){
 const count=metric?.status==='ready'&&typeof metric.numerator==='number'&&Number.isInteger(metric.numerator)&&metric.numerator>=0?metric.numerator:null;
 const denominator=metric&&'denominator' in metric?metric.denominator:total;
 const valid=count!==null&&typeof denominator==='number'&&Number.isInteger(denominator)&&denominator>0&&count<=denominator;
 return {count,denominator,rate:valid?new Intl.NumberFormat(language,{style:'percent',minimumFractionDigits:2,maximumFractionDigits:2}).format(count/denominator):'—'};
}
