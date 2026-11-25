"""IGCAF educational discrete-time cloud scheduling simulator.

All rates are synthetic configurable assumptions, not real metered cloud data.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple
import math
import numpy as np
import pandas as pd

POLICIES = ['Traditional', 'Consolidation', 'Carbon-aware', 'Integrated IGCAF']

@dataclass(frozen=True)
class Config:
    hours: int = 48
    total_servers: int = 30
    tasks: int = 260
    seed: int = 42
    idle_watts: float = 105.0
    peak_watts: float = 260.0
    wake_kwh: float = 0.035
    embodied_kg_per_host_hour: float = 0.015
    max_flex_hours: int = 5
    water_weight: float = 0.15
    cost_weight: float = 0.15
    delay_weight: float = 0.20
    allow_regions: bool = True

REGIONS = [
    {'name':'North (coal-heavy)', 'carbon':0.72,'pue':1.48,'wue':1.50,'price':0.14,'latency_ms':27,'phase':0.1},
    {'name':'West (mixed grid)', 'carbon':0.40,'pue':1.28,'wue':0.92,'price':0.17,'latency_ms':49,'phase':2.0},
    {'name':'South (cleaner grid)', 'carbon':0.19,'pue':1.19,'wue':0.62,'price':0.20,'latency_ms':74,'phase':4.0},
]

def region_signals(config: Config) -> pd.DataFrame:
    rows=[]
    for r, region in enumerate(REGIONS):
        for hour in range(config.hours):
            solar = math.sin((hour % 24 / 24) * 2 * math.pi + region['phase'])
            fluctuation = 0.19 * solar + 0.05 * math.sin(hour*0.43 + r)
            rows.append({'region':region['name'], 'region_id':r,'hour':hour,
                         'carbon_kg_kwh':round(max(.06, region['carbon']*(1+fluctuation)),4),
                         'pue':region['pue'], 'water_l_kwh':region['wue'],
                         'price_usd_kwh':region['price'], 'latency_ms':region['latency_ms']})
    return pd.DataFrame(rows)

def generate_tasks(config: Config) -> pd.DataFrame:
    rng=np.random.default_rng(config.seed)
    # Nonuniform arrivals with a daytime peak; all jobs finish within simulation horizon if scheduled.
    hours=np.arange(max(1,config.hours-6))
    weights=0.35+0.65*(1+np.sin((hours%24-7)*2*np.pi/24))/2
    weights=weights/weights.sum()
    arrivals=rng.choice(hours,size=config.tasks,p=weights)
    durations=rng.choice([1,2,3,4],size=config.tasks,p=[.47,.28,.18,.07])
    cpus=np.round(rng.uniform(.16,.57,config.tasks),3)
    flexible=rng.random(config.tasks)<0.62
    deadline=np.minimum(config.hours,arrivals+durations+np.where(flexible,config.max_flex_hours,0))
    return pd.DataFrame({'task_id':np.arange(config.tasks),'arrival':arrivals.astype(int),
                         'duration':durations.astype(int),'cpu_fraction':cpus,
                         'deadline':deadline.astype(int),'flexible':flexible}).sort_values(['arrival','task_id']).reset_index(drop=True)

def _host_counts(total: int) -> List[int]:
    base=total//3
    return [base+(1 if i<total%3 else 0) for i in range(3)]

def _incremental_energy(util: np.ndarray, demand: float, cfg: Config, policy: str) -> np.ndarray:
    # kWh IT energy added by a task across hours, plus a modeled wake transition.
    before=np.where(util>1e-9,cfg.idle_watts+(cfg.peak_watts-cfg.idle_watts)*util,0.0)
    after_util=util+demand
    after=cfg.idle_watts+(cfg.peak_watts-cfg.idle_watts)*after_util
    if policy=='Integrated IGCAF':
        # stylized power-state optimization, not measured frequency scaling
        after=np.where(after_util<.60,after*.94,after)
        before=np.where(util>1e-9,np.where(util<.60,before*.94,before),0.0)
    return (after-before)/1000 + np.where(util<1e-9,cfg.wake_kwh,0.0)

def simulate_policy(tasks: pd.DataFrame, config: Config, policy: str,
                    signals: pd.DataFrame | None=None) -> Tuple[pd.DataFrame,pd.DataFrame,Dict]:
    if policy not in POLICIES:
        raise ValueError('Unknown policy')
    if signals is None:
        signals=region_signals(config)
    counts=_host_counts(config.total_servers)
    # occupancy is fractional single-host capacity in each one-hour slot
    util=np.zeros((3,max(counts),config.hours),dtype=float)
    allowed=np.zeros((3,max(counts)),dtype=bool)
    for r,n in enumerate(counts): allowed[r,:n]=True
    sig={(int(x.region_id),int(x.hour)):x for x in signals.itertuples(index=False)}
    allocations=[]
    missed=0
    rr=0
    for job in tasks.itertuples(index=False):
        earliest=int(job.arrival)
        latest=min(config.hours-int(job.duration),int(job.deadline)-int(job.duration))
        if policy in ('Traditional','Consolidation'):
            latest=earliest # no intentional shifting
        # For flexible tasks only; otherwise deadline permits no delay.
        candidates=[]
        if earliest<=latest:
            for start in range(earliest,latest+1):
                for r in range(3 if config.allow_regions else 1):
                    for h in range(counts[r]):
                        window=util[r,h,start:start+int(job.duration)]
                        if np.any(window+job.cpu_fraction>1.0000001):
                            continue
                        # Network / region penalty is a simulated latency constraint.
                        if REGIONS[r]['latency_ms']>95:
                            continue
                        is_existing=np.any(window>1e-9)
                        inc_it=_incremental_energy(window,float(job.cpu_fraction),config,policy)
                        facility=inc_it*REGIONS[r]['pue']
                        carbon=sum(float(facility[k])*sig[(r,start+k)].carbon_kg_kwh for k in range(len(facility)))
                        cost=sum(float(facility[k])*sig[(r,start+k)].price_usd_kwh for k in range(len(facility)))
                        water=sum(float(facility[k])*sig[(r,start+k)].water_l_kwh for k in range(len(facility)))
                        delay=start-earliest
                        if policy=='Traditional':
                            # Fixed placement: deterministic round-robin, no green metric considered.
                            score=((h-rr)%counts[r])*100 + r*10_000
                        elif policy=='Consolidation':
                            score=(0 if is_existing else 100) + sum(inc_it)*2 + r*.01+h*.0001
                        elif policy=='Carbon-aware':
                            score=carbon + delay*.045 + REGIONS[r]['latency_ms']*.0003
                        else:
                            score=(.35*sum(facility)/1.0 + .35*carbon/.6 +
                                   config.water_weight*water/1.0 + config.cost_weight*cost/.15 +
                                   config.delay_weight*delay + REGIONS[r]['latency_ms']*.0004)
                        candidates.append((score,start,r,h))
        if not candidates:
            missed+=1
            allocations.append({'task_id':job.task_id,'arrival':job.arrival,'start':np.nan,
                                'finish':np.nan,'deadline':job.deadline,'region':'Unscheduled',
                                'region_id':-1,'host':-1,'duration':job.duration,
                                'cpu_fraction':job.cpu_fraction,'delay_h':np.nan,'sla_met':False})
            continue
        _,start,r,h=min(candidates)
        util[r,h,start:start+int(job.duration)]+=job.cpu_fraction
        allocations.append({'task_id':job.task_id,'arrival':job.arrival,'start':start,
                            'finish':start+job.duration,'deadline':job.deadline,
                            'region':REGIONS[r]['name'],'region_id':r,'host':h,
                            'duration':job.duration,'cpu_fraction':job.cpu_fraction,
                            'delay_h':start-job.arrival,'sla_met':True})
        rr=(rr+1)%max(counts)
    # Compute exact modeled hourly consumption for all servers, not task increments.
    records=[]
    prev_on=np.zeros((3,max(counts)),dtype=bool)
    host_hours=0
    for hour in range(config.hours):
        for r in range(3):
            u=util[r,:counts[r],hour]
            active=(u>1e-9)
            if policy=='Traditional':
                active=np.ones(len(u),dtype=bool)
            raw=np.where(active,config.idle_watts+(config.peak_watts-config.idle_watts)*u,0.)
            if policy=='Integrated IGCAF':
                raw=np.where((active)&(u<.60),raw*.94,raw)
            wakes=int(np.sum(active&~prev_on[r,:counts[r]]))
            # Baseline always-on servers are assumed already powered at time zero.
            if policy=='Traditional': wakes=0
            it_kwh=float(raw.sum()/1000+wakes*config.wake_kwh)
            row=sig[(r,hour)]
            facility_kwh=it_kwh*row.pue
            operational=facility_kwh*row.carbon_kg_kwh
            embodied=int(np.sum(active))*config.embodied_kg_per_host_hour
            host_hours+=int(np.sum(active))
            records.append({'policy':policy,'hour':hour,'region':REGIONS[r]['name'],
                            'region_id':r,'active_servers':int(np.sum(active)),
                            'servers':counts[r], 'mean_cpu_util':float(np.mean(u)) if len(u) else 0,
                            'it_kwh':it_kwh,'facility_kwh':facility_kwh,
                            'operational_kg':operational,'embodied_kg':embodied,
                            'water_l':facility_kwh*row.water_l_kwh,
                            'cost_usd':facility_kwh*row.price_usd_kwh,
                            'pue':row.pue,'grid_carbon_kg_kwh':row.carbon_kg_kwh})
            prev_on[r,:counts[r]]=active
    hourly=pd.DataFrame(records)
    alloc=pd.DataFrame(allocations)
    completed=len(alloc)-missed
    kwh=float(hourly.facility_kwh.sum())
    carbon=float(hourly.operational_kg.sum())
    embodied=float(hourly.embodied_kg.sum())
    info={'policy':policy,'total_tasks':len(tasks),'completed_tasks':completed,
          'sla_violations':missed,'sla_success_pct':100*completed/max(1,len(tasks)),
          'facility_kwh':kwh,'it_kwh':float(hourly.it_kwh.sum()),
          'operational_kg':carbon,'embodied_kg':embodied,'total_kg':carbon+embodied,
          'water_l':float(hourly.water_l.sum()),'cost_usd':float(hourly.cost_usd.sum()),
          'pue':kwh/max(.00001,float(hourly.it_kwh.sum())),
          'sci_g_per_completed_task':1000*(carbon+embodied)/max(1,completed),
          'mean_delay_h':float(alloc.delay_h.mean()) if completed else 0,
          'peak_active_servers':int(hourly.groupby('hour').active_servers.sum().max()),
          'host_hours':host_hours}
    return alloc,hourly,info

def run_experiment(config:Config):
    tasks=generate_tasks(config)
    signals=region_signals(config)
    allocations={}; timelines=[]; summaries=[]
    for p in POLICIES:
        alloc,hour,summary=simulate_policy(tasks,config,p,signals)
        allocations[p]=alloc
        timelines.append(hour)
        summaries.append(summary)
    return tasks,signals,allocations,pd.concat(timelines,ignore_index=True),pd.DataFrame(summaries)
