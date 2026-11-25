import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simulator import Config, POLICIES, run_experiment, generate_tasks

def test_deterministic_tasks():
    cfg=Config(hours=24,total_servers=12,tasks=70,seed=5)
    assert generate_tasks(cfg).equals(generate_tasks(cfg))

def test_policy_metrics_conserve_and_nonnegative():
    cfg=Config(hours=24,total_servers=12,tasks=70,seed=8)
    tasks,signals,allocs,hour,summary=run_experiment(cfg)
    assert len(summary)==4 and set(summary.policy)==set(POLICIES)
    assert len(hour)==24*3*4
    for _,v in summary.iterrows():
        assert v.completed_tasks+v.sla_violations==70
        assert v.facility_kwh>=v.it_kwh>=0
        assert v.operational_kg>=0 and v.embodied_kg>=0
        assert 0<=v.sla_success_pct<=100
        assert len(allocs[v.policy])==70

def test_low_and_high_workloads():
    for n in [60,250]:
        cfg=Config(hours=24,total_servers=9,tasks=n,seed=19)
        _,_,_,_,summary=run_experiment(cfg)
        assert summary.completed_tasks.max()<=n
