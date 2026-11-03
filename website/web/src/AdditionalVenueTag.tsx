import {useEffect,useState} from 'react';
import mappingURL from './data/publication-venues.json?url';
import {citationText} from './citations';
import {t} from './i18n';
import {publicationAbbreviation,type PublicationAbbreviations} from './publicationAbbreviations';
import type {VenueReference} from './venueFamilies';

let cached:PublicationAbbreviations|undefined;
let loading:Promise<PublicationAbbreviations>|undefined;
function loadMapping(){
 if(cached)return Promise.resolve(cached);
 if(!loading)loading=new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())))
  .then(()=>fetch(mappingURL,{credentials:'same-origin'}))
  .then(response=>{if(!response.ok)throw Error('mapping_unavailable');return response.json();})
  .then(value=>{if(!value?.map||typeof value.map!=='object'||Array.isArray(value.map))throw Error('invalid_mapping');cached=value.map as PublicationAbbreviations;return cached;})
  .catch(error=>{loading=undefined;throw error;});
 return loading;
}

/** Non-curated source badges are independent from the curated filter list. */
export default function AdditionalVenueTag({paper}:{paper:VenueReference}){
 const title=citationText(paper.publication),[map,setMap]=useState(()=>cached);
 useEffect(()=>{if(!title)return;let active=true;void loadMapping().then(value=>{if(active)setMap(value);}).catch(()=>{});return()=>{active=false;};},[title]);
 const label=publicationAbbreviation(title,map);if(!label)return null;
 const kind=['Magazines','Early Access Articles'].includes(paper.kind||'')?'Journals':paper.kind;
 return <div className="venue-tags" aria-label={t('刊会来源标签')}><span className={'venue-tag'+(kind==='Journals'||kind==='Conferences'?' '+kind.toLowerCase():'')} title={title}>{label}</span></div>;
}
