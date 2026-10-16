import {ArrowDownRight, Clock3, Layers3, ShieldCheck, UsersRound} from 'lucide-react';
import type {Strategy} from '../types';
import {fmt} from '../types';
export function Metrics({strategy,baseline}:{strategy:Strategy;baseline:Strategy}) {
  const items=[{key:'mean_hours',label:'Average turnaround',unit:'h',icon:Clock3,digits:1}, {key:'backlog',label:'Cases still open',unit:'',icon:Layers3,digits:0}, {key:'human_hours',label:'Human service time',unit:'h',icon:UsersRound,digits:0}, {key:'sla_percent',label:'Within service target',unit:'%',icon:ShieldCheck,digits:1}];
  return <div className="metrics">{items.map(({key,label,unit,icon:Icon,digits})=>{
    const m=strategy.metrics[key], base=baseline.metrics[key].mean;
    const delta=key==='sla_percent'?m.mean-base:base ? (m.mean-base)/base*100 : 0;
    const improved=key==='sla_percent'?delta>0:delta<0;
    return <article className="metric" key={key}><div className="metric-label">{label}<Icon size={16}/></div><div className="metric-value">{fmt(m.mean,digits)}<span>{unit}</span></div><div className="metric-bottom"><span title="10th–90th percentile across runs">{fmt(m.low,digits)}–{fmt(m.high,digits)}{unit} across runs</span>{strategy.id!=='current' && Math.abs(delta)>.5 && <span className={`delta ${improved?'':'worse'}`} title={`${delta>0?'Increase':'Decrease'} versus today’s process${key==='sla_percent'?' in percentage points':''}`}><ArrowDownRight size={13} style={{transform:delta>0?'rotate(-90deg)':undefined}}/>{fmt(Math.abs(delta))}{key==='sla_percent'?' pp':'%'}</span>}</div></article>
  })}</div>
}
