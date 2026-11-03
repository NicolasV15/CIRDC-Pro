import type {AuthorReference} from './authorLinks';
import type {ResourceCoverage} from './resourceCoverage';

export type User={username:string;role:string;must_change:boolean;csrf:string};
export type ReadingResource={reader_href?:string;media_type?:string;kind?:string;id:string;href:string;label:string;label_i18n?:Record<string,string>;note?:string;note_i18n?:Record<string,string>;size_bytes?:number};
export type Highlighted={text:string;highlights:[number,number][]};
export type MatchReason={field:string;terms:{query:string;matched:string[];alias:boolean}[]};
export type Passage={ordinal:number;kind:string;section:string;section_id:string|null;version:string;fingerprint:string;match:string;excerpt:Highlighted};
export type Paper={venue?:string;venue_series?:string[];number:string;title:string;authors:string;publication:string;year:number;kind:string;doi:string;snippet:string;abstract_state:string;keywords_state:string;resources?:ReadingResource[];author_refs?:AuthorReference[];position?:number;reasons?:MatchReason[];flags?:Record<string,boolean|string>;excerpt?:(Highlighted&{field:string})|null;passages?:Passage[];passage_total?:number};
export type QueryGroup={kind:string;text:string;label?:string;alternatives?:string[];equivalents?:string[];related?:string[]};
export type QueryInfo={terms?:string;number?:string;doi?:string;groups?:QueryGroup[];match?:string;alternatives?:string[][]};
export type FulltextStatus={enabled:boolean;phase:string;documents:number;cataloged:number;pending:number;failed?:number;blocked?:number;next_retry_at?:number|null;catalog_total?:number|null;synced_at?:string|null;error?:string|null};
export type Venue={kind:string;number:string;title:string};
export type Overview={resource_coverage?:ResourceCoverage[];papers:number;field_states:{abstract_state:string;keywords_state:string;n:number}[];venues:{kind:string;n:number}[];sampled_at:string};
export type Index={year_range?:{min:number|null;max:number|null};phase?:string;indexed?:number;backlog?:number;checked_at?:string;error?:string;overview?:Overview};
export type Filters={limit:string;venue_tags:string;q:string;field:string;kind:string;venue:string;year_from:string;year_to:string;abstract_state:string;keywords_state:string;sort:string;author_source:string;author_id:string;author_unidentified:string;view:string;k:string;terms:string};
