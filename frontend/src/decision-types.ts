export type Action = 'route' | 'request_info' | 'resolve' | 'escalate';
export type Priority = 'low' | 'normal' | 'high' | 'critical';
export interface DecisionWorkflow {name:string; objective:string; policy:string; teams:string[]; auto_execute:boolean; review_actions:Action[]; review_priorities:Priority[]}
export interface SourceDocument {name:string;text:string}
export interface Sample {id:string;title:string;text:string;documents:SourceDocument[]}
export interface Decision {summary:string;action:Action;priority:Priority;team:string;rationale:string;policy_rule_ids:string[];evidence:{source_id:string;quote:string;supports:string}[];missing_information:string[];uncertainties:string[];requires_review:boolean;response_draft:string}
export interface LocalState {status:string;team:string|null;priority:string|null;response_draft:string}
export interface CaseMeta {model:string;tokens:number;elapsed_ms:number;engine:string}
export interface CaseSummary {id:string;title:string;created_at:string;status:string;local_state:LocalState;meta:CaseMeta|null}
export interface CaseRecord extends CaseSummary {text:string;documents:SourceDocument[];workflow:DecisionWorkflow;input_hash:string;updated_at:string;decision:Decision|null;validation:{passed:boolean;checks:{name:string;passed:boolean;detail:string}[];review_reasons:string[]}|null;error:string|null;events:{case_id:string;seq:number;at:string;kind:string;data:Record<string,unknown>;previous_hash:string;hash:string}[]}
export interface Audit {valid:boolean;events:number;last_hash:string;scope:string}
