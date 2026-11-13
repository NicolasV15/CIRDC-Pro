/** One light read per page lifetime; no polling or resource acquisition. */
export const skillBase='/api/agent/v1/skills/cirdc-research';
export type SkillRelease={version:string;notes:{zh:string;en:string}};
let pending:Promise<SkillRelease|null>|undefined;
export function skillRelease():Promise<SkillRelease|null>{
 return pending??=fetch(skillBase+'/version.json',{signal:AbortSignal.timeout(2000)})
  .then(async response=>{if(!response.ok)return null;const value=await response.json();
   return value.name==='cirdc-research'&&value.schema_version===1&&/^\d+\.\d+\.\d+$/.test(value.version)&&typeof value.notes?.zh==='string'&&typeof value.notes?.en==='string'?{version:value.version,notes:value.notes}:null;
  }).catch(()=>null);
}
