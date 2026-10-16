import type {Experiment} from '../types';
import {COLORS,fmt} from '../types';
export function BacklogChart({experiment}:{experiment:Experiment}) {
  const [width,height]=[600,180], left=40, top=15, bottom=28;
  const max=Math.max(10,...experiment.strategies.flatMap(s=>s.daily.map(d=>d.backlog)))*1.12;
  const x=(i:number)=>left+i/(experiment.config.days-1)*(width-left-15);
  const y=(n:number)=>height-bottom-n/max*(height-top-bottom);
  return <section className="panel chart-panel"><div className="panel-header"><div><span className="eyebrow">THE BIGGER PICTURE</span><h2>Where unfinished work accumulates</h2></div><span className="muted">End-of-day backlog</span></div>
    <div className="chart-legend">{experiment.strategies.map(s=><span key={s.id}><i style={{background:COLORS[s.id]}}/>{s.name}</span>)}</div>
    <svg className="backlog-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Backlog over working days for three arrangements">
      {[0,.25,.5,.75,1].map(p=><g key={p}><line x1={left} x2={width-10} y1={y(max*p)} y2={y(max*p)} stroke="#e8ece7" strokeDasharray="3 5"/><text x={left-8} y={y(max*p)+4} textAnchor="end">{fmt(max*p)}</text></g>)}
      {experiment.strategies.map(s=><path key={s.id} d={s.daily.map((d,i)=>`${i?'L':'M'} ${x(i)} ${y(d.backlog)}`).join(' ')} fill="none" stroke={COLORS[s.id]} strokeWidth={s.id==='augmented'?3:2} strokeLinecap="round"/>) }
      {[0,Math.floor((experiment.config.days-1)/2),experiment.config.days-1].map(i=><text key={i} x={x(i)} y={height-6} textAnchor="middle">Day {i+1}</text>)}
    </svg><div className="panel-footnote">Representative run · seed {experiment.config.seed} · arrivals stop after {experiment.config.days} working days.</div>
  </section>
}

export function Comparison({experiment}:{experiment:Experiment}) {
  const metrics=[['mean_hours','Average turnaround','elapsed h'],['p90_hours','Slowest 10% start at','elapsed h'],['backlog','Open at window end','cases'],['sla_percent','Within service target','%'],['human_hours','Active human service','h'],['cost_per_case','Service cost per arrival','$'],['reviewer_utilization','Busiest review team','%'],['clearance_days','Backlog clearance after window','calendar days']];
  return <section className="panel comparison-panel"><div className="panel-header"><div><span className="eyebrow">COMPARE THE ARRANGEMENTS</span><h2>See the tradeoffs, together.</h2></div><span className="small-badge">{experiment.config.repetitions} paired runs</span></div><div className="table-scroll"><table><thead><tr><th>Outcome</th>{experiment.strategies.map(s=><th key={s.id}><i style={{background:COLORS[s.id]}}/>{s.name}</th>)}</tr></thead><tbody>{metrics.map(([key,label,unit])=><tr key={key}><td>{label}<small>{unit}</small></td>{experiment.strategies.map(s=><td key={s.id}><b>{unit==='$'?'$':''}{fmt(s.metrics[key].mean,key==='backlog'?0:1)}{unit==='%'?'%':''}</b><small>{fmt(s.metrics[key].low,1)}–{fmt(s.metrics[key].high,1)}</small></td>)}</tr>)}</tbody></table></div><p className="panel-footnote">Ranges are the 10th–90th percentiles across runs. Service cost reflects active work, not payroll savings. Decision quality is not modeled.</p></section>
}
