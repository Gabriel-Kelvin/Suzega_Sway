export type StrategyId = 'current' | 'automated' | 'augmented';
export type Disruption = 'none' | 'surge' | 'outage' | 'absence' | 'exceptions';
export interface Stage { id: string; name: string; role: string; human_minutes: number; ai_minutes: number; workers: number; requires_human: boolean }
export interface Config {name:string; days:number; daily_cases:number; work_hours:number; learning_hours:number; complex_share:number; ai_speed:number; exception_rate:number; assist_multiplier:number; hourly_cost:number; ai_case_cost:number; sla_hours:number; repetitions:number; seed:number; disruption:Disruption; stages:Stage[]}
export interface Range {mean:number; low:number; high:number}
export interface Frame {time:number; day:number; stages:{waiting:number; active:number}[]; completed:number}
export interface Strategy {id:StrategyId; name:string; description:string; metrics:Record<string,Range>; stages:{id:string; name:string; utilization:number; mean_wait_hours:number; human_hours:number}[]; daily:{day:number; backlog:number; completed:number; arrived:number}[]; frames:Frame[]; horizon_minutes:number}
export interface Experiment {id:string; created_at:string; input_hash:string; engine_version:string; config:Config; strategies:Strategy[]; insight:{title:string;body:string;improvement_percent:number;bottleneck_stage:string}; methodology:{range:string;latency:string;cost:string;calendar:string;limitations:string[];seeds:number[];repetitions:number}}
export interface SavedRun {id:string;name:string;created_at:string}
export interface Draft {summary:string;assumptions:string[];config:Config;model:string;tokens:number}
export interface Brief {headline:string;observations:string[];questions:string[];pilot_plan:string[];model:string;tokens:number}
export const COLORS: Record<StrategyId,string> = {current:'#94a39e',automated:'#cb895a',augmented:'#236d59'};
export const fmt = (n:number, digits=0) => new Intl.NumberFormat('en-US',{maximumFractionDigits:digits}).format(n);
