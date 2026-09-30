"""Apply all predeclared three-arm comparisons after independent account checks."""
from copy import deepcopy
from decimal import Decimal as D
import gzip
import json
from pathlib import Path
import subprocess
import sys
from build import BASE,HERE,OUT,REPO,ARMS,read,save,sha
from checks_v2 import causal,daily_budget,ns,iso
from assessment import drawdowns,summarize,gates,first_difference


def main():
    folder=OUT/'assessment';folder.mkdir(exist_ok=False)
    proof=read(OUT/'historical_accounts/verification.json');assert proof['verified']
    accounts=read(OUT/'historical_accounts/accounts.json')
    assert sha(OUT/'historical_accounts/accounts.json')==proof['accounts_sha256']
    tests=subprocess.run([sys.executable,str(HERE/'test_assessment.py')],cwd=HERE,capture_output=True,text=True)
    save(folder/'tests.json',dict(returncode=tests.returncode,stdout=tests.stdout,stderr=tests.stderr));assert tests.returncode==0
    for row in accounts:
        row['risk']={};states={}
        for arm,binding in row['bindings'].items():
            assert sha(binding['path'])==binding['sha256']
            state=read(binding['path']);states[arm]=state
            values=[(ns(point['At']),D(point['Value'])) for point in state['Equity']]
            row['risk'][arm]=drawdowns(values)
            assert abs(D(row['risk'][arm]['full_drawdown_pct'])-D(row['arms'][arm]['initial_budget_drawdown_pct']))<=D('1e-12')
        row['first_difference']={arm:first_difference(states[arm],states['reserve3'],arm) for arm in ('baseline','cap9')}
        row['differences']={arm:{key:str(D(row['arms']['reserve3'][key])-D(row['arms'][arm][key]))
                                for key in ('return_pct','max_drawdown_pct','final_equity','fees')} for arm in ('baseline','cap9')}
    cases=read(BASE/'poloniex_stop_topup_guard_v1/cases.json');groups=[]
    for case in cases:
        members=[row for row in accounts if row['case']==case['id']]
        checks=gates(members,case['days'])
        groups.append(dict(case=case,accounts=len(members),arms={arm:summarize(members,arm) for arm in ARMS},
                           gates=checks,passes_all=all(checks.values())))
    regression=read(OUT/'regressions_v3/verification.json');assert regression['verified']
    path=OUT/'regressions_v3/cycles.jsonl.gz';assert sha(path)==regression['cycles_sha256']
    cycles=[json.loads(line) for line in gzip.open(path,'rt')]
    sample=next(row for row in cycles if row['output']['State']['Holdings'] and row['output']['State']['Fills'])
    rejected=[];now=sample['input']['NowNS']
    for name in ('LastCycle','Equity','Entered','Fills'):
        changed=deepcopy(sample['output']['State']);future=iso(now+1)
        if name=='LastCycle':changed[name]=future
        elif name=='Equity':changed[name][-1]['At']=future
        elif name=='Entered':next(iter(changed['Holdings'].values()))[name]=future
        else:changed[name][-1]['At']=future
        try:causal(changed,now)
        except AssertionError:rejected.append(name)
        else:raise AssertionError('future timestamp accepted')
    baseline=next(row for row in cycles if row['input']['ID']=='buys_.003_baseline_3')
    for name,maximum,reserve in [('total_cap',9,0),('buy_reserve',12,3)]:
        cfg={**baseline['input']['Config'],'MaxOrdersDay':maximum,'ExitOrderReserve':reserve}
        try:daily_budget(baseline['input']['Before'],baseline['output']['State'],cfg,baseline['input']['NowNS'])
        except AssertionError:rejected.append(name)
        else:raise AssertionError('budget violation accepted')
    save(folder/'accounts.json',accounts);save(folder/'groups.json',groups)
    hashes={str(p):sha(p) for p in (Path(__file__),HERE/'assessment.py',HERE/'test_assessment.py',
            OUT/'historical_accounts/verification.json',OUT/'historical_accounts/accounts.json',
            OUT/'regressions_v3/verification.json',path,folder/'accounts.json',folder/'groups.json',folder/'tests.json')}
    save(folder/'verification.json',dict(verified=True,hashes=hashes,groups=len(groups),accounts_per_arm=len(accounts),
        groups_passing=sum(g['passes_all'] for g in groups),historical_screen_passes=all(g['passes_all'] for g in groups),
        gates_passed=sum(sum(g['gates'].values()) for g in groups),gates_total=sum(len(g['gates']) for g in groups),
        exact_calendar_risk_from_sampled_marks=True,first_divergences_explained_by_registered_rule=True,
        clock_and_budget_mutations_rejected=rejected,live_changed=False,deployment_qualified=False))
    print('EXIT_RESERVE_ASSESSED',sum(g['passes_all'] for g in groups),'of',len(groups),flush=True)


if __name__=='__main__':main()
