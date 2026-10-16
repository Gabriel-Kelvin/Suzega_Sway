import {ArrowUpRight, CloudOff, Settings2, ShieldCheck, UserMinus, Waves, Zap} from 'lucide-react';
import type {Config,Disruption} from '../types';
export function Slider({label,value,min,max,step=1,suffix='',onChange,hint}:{label:string;value:number;min:number;max:number;step?:number;suffix?:string;onChange:(n:number)=>void;hint?:string}) {
  return <label className="slider-field"><span>{label}<b>{Number(value.toFixed(2))}{suffix}</b></span><input type="range" min={min} max={max} step={step} value={value} onChange={e=>onChange(+e.target.value)}/>{hint&&<small>{hint}</small>}</label>
}
export function Controls({config,onChange,stageIndex}:{config:Config;onChange:(c:Config)=>void;stageIndex:number}) {
  const stage=config.stages[stageIndex]??config.stages[0];
  const set=(key:keyof Config,value:unknown)=>onChange({...config,[key]:value});
  const selectedIndex=Math.min(stageIndex,config.stages.length-1);
  const setStage=(key:string,value:unknown)=>onChange({...config,stages:config.stages.map((s,i)=>i===selectedIndex?{...s,[key]:value}:s)});
  return <aside className="panel controls"><div className="panel-header"><div><span className="eyebrow">SHAPE THE EXPERIMENT</span><h2>Change the conditions</h2></div><Settings2 size={17}/></div>
    <div className="control-body"><Slider label="Incoming cases / day" value={config.daily_cases} min={5} max={160} step={1} onChange={v=>set('daily_cases',v)}/><Slider label="AI processing speed" value={config.ai_speed} min={.25} max={20} step={.25} suffix="×" onChange={v=>set('ai_speed',v)} hint="Speed affects AI service only; human capacity stays fixed."/>
      <Slider label="AI exception rate" value={config.exception_rate*100} min={0} max={60} suffix="%" onChange={v=>set('exception_rate',v/100)}/>
      <Slider label="Assisted review time saved" value={(1-config.assist_multiplier)*100} min={0} max={80} step={5} suffix="%" onChange={v=>set('assist_multiplier',1-v/100)} hint="A hypothesis to validate. Quality is not assumed equal."/>
      <div className="control-divider"/><span className="eyebrow">HUMAN BOUNDARIES</span><Slider label="Working hours / day" value={config.work_hours} min={4} max={10} suffix="h" onChange={v=>set('work_hours',v)}/><Slider label="Friday learning time" value={config.learning_hours} min={0} max={3} step={.5} suffix="h" onChange={v=>set('learning_hours',v)}/>
      <div className="boundary-note"><ShieldCheck size={15}/><span>Human decisions stay human. Work pauses outside shifts.</span></div>
      <div className="control-divider"/><span className="eyebrow">SELECTED STEP</span><h3>{stage.name}</h3><Slider label="People at this step" value={stage.workers} min={1} max={20} onChange={v=>setStage('workers',v)}/><Slider label="Human service / case" value={stage.human_minutes} min={1} max={240} suffix=" min" onChange={v=>setStage('human_minutes',v)}/>
      <details className="advanced"><summary>Edit this step <Settings2 size={13}/></summary><label>Step name<input value={stage.name} maxLength={50} onChange={e=>setStage('name',e.target.value)}/></label><label>Human role<input value={stage.role} maxLength={60} onChange={e=>setStage('role',e.target.value)}/></label><label>AI service / case (minutes)<input type="number" min={.1} max={60} step={.1} value={stage.ai_minutes} onChange={e=>setStage('ai_minutes',+e.target.value)}/></label><label className="check-field"><input type="checkbox" checked={stage.requires_human} disabled={stage.requires_human&&config.stages.filter(s=>s.requires_human).length===1} onChange={e=>setStage('requires_human',e.target.checked)}/>Require human authority</label><p className="edit-hint">At least one step must retain human authority. Use New workflow to draft a different sequence.</p></details>
      <details className="advanced"><summary>More assumptions <ArrowUpRight size={13}/></summary><label>Working days<input type="number" min={5} max={40} value={config.days} onChange={e=>set('days',+e.target.value)}/></label><label>Paired runs<input type="number" min={3} max={30} value={config.repetitions} onChange={e=>set('repetitions',+e.target.value)}/></label><label>Human cost / hour ($)<input type="number" min={0} max={250} value={config.hourly_cost} onChange={e=>set('hourly_cost',+e.target.value)}/></label><label>AI cost / execution ($)<input type="number" min={0} max={5} step={.01} value={config.ai_case_cost} onChange={e=>set('ai_case_cost',+e.target.value)}/></label><label>SLA (elapsed hours)<input type="number" min={1} max={240} value={config.sla_hours} onChange={e=>set('sla_hours',+e.target.value)}/></label><label>Random seed<input type="number" min={0} max={1000000} value={config.seed} onChange={e=>set('seed',+e.target.value)}/></label></details>
    </div></aside>
}
export const DISRUPTIONS:{id:Disruption;name:string;detail:string;icon:typeof Zap}[]=[
  {id:'none',name:'Steady conditions',detail:'Standard workload',icon:Waves},
  {id:'surge',name:'Demand spike',detail:'2× arrivals on working days 9–11',icon:ArrowUpRight},
  {id:'outage',name:'AI outage',detail:'24 hours from day 9, 11:00',icon:CloudOff},
  {id:'absence',name:'Reviewer away',detail:'One fewer reviewer per review stage (minimum one)',icon:UserMinus},
  {id:'exceptions',name:'Messier inputs',detail:'2× AI exception probability',icon:Zap},
];
