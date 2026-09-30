"""Retain every changed account and independently verify both economic paths."""
from decimal import Decimal as D
from pathlib import Path
import statistics
import time
from build import REPO,HERE,OUT,OLD,read,save,sha
from account_reference import Check,verify

def main():
    destination=OUT/'independent_audit';destination.mkdir(exist_ok=False)
    fixture=read(REPO/'data/frontier_20260912/ledger/fixture.json');markets=read(REPO/'data/frontier_20260912/ledger/markets.json')
    cases=read(OUT/'cases.json');assert len(cases)==9
    bound=read(OUT/'run_inputs.json');assert all(sha(p)==h for p,h in bound.items())
    check=Check();groups=[];all_results=[];changed=0;negative_pairs=[];rejected_old=0
    for case in cases:
        folder=OUT/'accounts'/case['id'];old=OLD/'accounts'/case['id'];assert read(folder/'exit.json')['returncode']==0
        before=[__import__('json').loads(x) for x in (old/'results.jsonl').read_text().splitlines()]
        after=[__import__('json').loads(x) for x in (folder/'results.jsonl').read_text().splitlines()]
        assert len(before)==len(after)=={0:1,28:9,56:5}[case['days']];paired=[]
        for a,z in zip(before,after):
            assert a['Start']==z['Start'] and a['End']==z['End']
            ap=old/a['Ledger'];zp=folder/z['Ledger'];ac=read(ap);zc=read(zp)
            av=verify(ac,a,case,fixture,markets,check);zv=verify(zc,z,case,fixture,markets,check,require_stop_guard=True)
            same=ap.read_bytes()==zp.read_bytes();changed+=not same
            assert same==(len(av['below_stop_buys'])==0),'changed paths must start from a formerly allowed below-stop buy'
            if av['below_stop_buys'] and rejected_old==0:
                try:verify(ac,a,case,fixture,markets,Check(),require_stop_guard=True)
                except AssertionError as e:assert e.args[0][0]=='buy while below protective stop';rejected_old+=1
                else:raise AssertionError('strict reference accepted old violating account')
            delta=D(zv['return_pct'])-D(av['return_pct'])
            if delta<0:negative_pairs.append(dict(case=case['id'],start=a['Start'],delta_pp=str(delta)))
            row=dict(start=a['Start'],end=a['End'],same_complete_ledger=same,control=av,guard=zv,control_path=str(ap),guard_path=str(zp),control_sha256=sha(ap),guard_sha256=sha(zp))
            paired.append(row);all_results.append(row)
        stats=lambda key:dict(mean_return_pct=str(sum(D(r[key]['return_pct']) for r in paired)/len(paired)),worst_return_pct=str(min(D(r[key]['return_pct']) for r in paired)),maximum_drawdown_pct=str(max(D(r[key]['max_drawdown_pct']) for r in paired)),fees=str(sum(D(r[key]['fees']) for r in paired)),fills=sum(r[key]['fills'] for r in paired))
        group=dict(case=case,control=stats('control'),guard=stats('guard'),accounts=paired)
        save(destination/(case['id']+'.json'),group);groups.append(group);print('STOP_ACCOUNT_AUDIT',case['id'],len(paired),flush=True)
    assert len(all_results)==45 and rejected_old==1
    summary=dict(verified=True,at_ns=time.time_ns(),accounts=45,unchanged_complete_ledgers=45-changed,changed_accounts=changed,
        comparisons=check.count,maximum_metric_error=str(check.maximum),below_stop_buys_before=sum(len(r['control']['below_stop_buys']) for r in all_results),below_stop_buys_after=0,
        changed_cases_with_lower_return=negative_pairs,control_violations_rejected_by_guard_reference=True,
        groups=[{k:v for k,v in g.items() if k!='accounts'} for g in groups],historical_reuse=True,independent_holdout=False,
        all_group_mean_returns_nondecreasing=all(D(g['guard']['mean_return_pct'])>=D(g['control']['mean_return_pct']) for g in groups),
        lower_drawdown_in_every_group=all(D(g['guard']['maximum_drawdown_pct'])<=D(g['control']['maximum_drawdown_pct']) for g in groups),live_changed=False,
        hashes={str(p):sha(p) for p in [Path(__file__),HERE/'account_reference.py',*destination.glob('*.json'),OUT/'cases.json',OUT/'run_inputs.json']})
    save(OUT/'independent_verification.json',summary);print('STOP_COMPLETE_AUDIT',changed,summary['below_stop_buys_before'],check.count,flush=True)

if __name__=='__main__':main()
