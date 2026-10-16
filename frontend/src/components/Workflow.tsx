import {useEffect,useState} from 'react';
import {ArrowRight, Bot, Check, ChevronRight, FileInput, Pause, Play, RotateCcw, ShieldCheck, UsersRound, Waypoints} from 'lucide-react';
import type {Config,Strategy} from '../types';
import {fmt} from '../types';

export function Workflow({strategy,config,stageIndex,onSelect}:{strategy:Strategy;config:Config;stageIndex:number;onSelect:(i:number)=>void}) {
  const [frame,setFrame]=useState(22), [playing,setPlaying]=useState(false);
  useEffect(()=>{setFrame(Math.min(22,strategy.frames.length-1));setPlaying(false)},[strategy]);
  useEffect(()=>{
    if(!playing) return;
    const timer=window.setInterval(()=>setFrame(f=>(f+1)%strategy.frames.length),700);
    return ()=>window.clearInterval(timer);
  },[playing,strategy.frames.length]);
  const snap=strategy.frames[frame]??strategy.frames[0];
  const hour = 9 + (snap.time%1440)/60;
  const time=`${String(Math.floor(hour)).padStart(2,'0')}:${String(Math.floor((hour%1)*60)).padStart(2,'0')}`;
  const icons=[FileInput,Waypoints,ShieldCheck,Check];
  return <section className="panel flow-panel">
    <div className="panel-header"><div><span className="eyebrow">THE WORK, IN MOTION</span><h2>A process is only as fast as its people can follow.</h2></div><span className="small-badge"><span className="live-dot"/>Recorded simulation</span></div>
    <div className="flow-legend"><span><i className="legend-dot human"/>Human work</span><span><i className="legend-dot ai"/>AI work</span><span><i className="legend-dot queue"/>Waiting cases</span></div>
    <div className={`workflow ${playing?'is-playing':''}`}>
      <div className="workflow-end"><span className="end-dot"/><small>NEW CASES</small></div>
      <div className="flow-stages" style={{gridTemplateColumns:`repeat(${config.stages.length}, minmax(130px, 1fr))`}}>
        {config.stages.map((stage,i)=>{
          const isHuman = strategy.id==='current'||stage.requires_human;
          const assisted = strategy.id==='augmented'&&stage.requires_human;
          const Icon=icons[i%icons.length], counts=snap.stages[i];
          return <div className="stage-wrap" key={stage.id}>
            {i>0&&<div className="connector"><span/><ChevronRight size={14}/></div>}
            <button className={`stage ${stageIndex===i?'selected':''} ${!isHuman?'ai-stage':''}`} onClick={()=>onSelect(i)} aria-label={`Inspect ${stage.name}`}>
              <div className="stage-top"><span className={`stage-icon ${!isHuman?'ai':''}`}><Icon size={19}/></span><span className="stage-number">0{i+1}</span></div>
              <h3>{stage.name}</h3><span className="stage-role">{isHuman?stage.role:'AI agent'}</span>
              <div className="stage-type">{isHuman?<UsersRound size={13}/>:<Bot size={13}/>} {assisted?'Human + AI support':isHuman?'Human-led':'AI-assisted workflow'}</div>
              <div className="stage-counts"><span><b>{counts.active}</b> active</span><span className={counts.waiting>20?'waiting-hot':''}><b>{counts.waiting}</b> waiting</span></div>
            </button>
            <div className="stage-caption">{stage.requires_human?<><ShieldCheck size={12}/>Human decision protected</>:<>{fmt(strategy.stages[i].mean_wait_hours,1)}h average wait</>}</div>
          </div>
        })}
      </div>
      <div className="workflow-end finish"><span className="end-dot"><Check size={9}/></span><small>CLOSED</small></div>
    </div>
    <div className="flow-summary"><span><span className="queue-pips">••••</span> {snap.stages.reduce((a,s)=>a+s.waiting,0)} waiting across the process</span><span>{fmt(snap.completed)} cases completed <ArrowRight size={13}/></span></div>
    <div className="playback"><button className="icon-button" onClick={()=>setPlaying(!playing)} aria-label={playing?'Pause playback':'Play playback'}>{playing?<Pause size={16}/>:<Play size={16}/>}</button><button className="icon-button" onClick={()=>{setFrame(0);setPlaying(false)}} aria-label="Reset playback"><RotateCcw size={15}/></button><input aria-label="Simulation playback position" type="range" min={0} max={strategy.frames.length-1} value={frame} onChange={e=>{setFrame(+e.target.value);setPlaying(false)}}/><span><b>Day {snap.day}</b><small>{time}</small></span></div>
    <div className="panel-footnote">Playback shows one seeded run. Counters include every case; motion is illustrative.</div>
  </section>
}
