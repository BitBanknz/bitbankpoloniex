"""Audit complete replay cases and apply the fixed nine-group comparison."""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path
import time
from build import ROOT,HERE,OUT,read,save,sha
from account_reference_v2 import verify,Check


def summarize(cases):
    groups={};comparisons={};gain=False
    assert len(cases)==27
    for c in cases:
        setting=c['case'];key=(setting['days'],D(str(setting['fee'])),setting['variant'])
        assert key not in groups
        results=c['accounts'];returns=[D(r['return_pct']) for r in results]
        assert len(results)=={0:1,28:9,56:5}[key[0]]
        groups[key]=dict(mean=sum(returns)/len(returns),worst=min(returns),max_dd=max(D(r['max_drawdown_pct']) for r in results),
            max_initial_budget_dd=max(D(r['initial_budget_drawdown_pct']) for r in results),positive=sum(x>0 for x in returns),
            fills=sum(r['fills'] for r in results),topups=sum(r['topups'] for r in results),fees=sum(D(r['fees']) for r in results),
            same_cycle_sell_then_topup=sum(r['same_cycle_sell_then_topup'] for r in results),halts=sum(r['halted'] for r in results),
            dust_drops=sum(len(r['dust']) for r in results),accounts=len(results))
    expected={(d,f,v) for d in (0,28,56) for f in (D('.003'),D('.004'),D('.006')) for v in (0,1,2)}
    assert set(groups)==expected
    for days in (0,28,56):
        for fee in (D('.003'),D('.004'),D('.006')):
            legacy,control,candidate=(groups[(days,fee,v)] for v in (0,1,2))
            gain|=candidate['mean']>control['mean']
            gates=dict(mean_nonregression=candidate['mean']>=control['mean'],worst_nonregression=candidate['worst']>=control['worst'],
                dd_nonregression=candidate['max_dd']<=control['max_dd'],positive_count_nonregression=candidate['positive']>=control['positive'],
                positive_continuous=days!=0 or candidate['mean']>0,
                absolute_dd=days not in (0,28) or candidate['max_dd']<=D(40 if days==0 else 35))
            encode=lambda a:{k:str(v) if isinstance(v,D) else v for k,v in a.items()}
            comparisons[f'days{days}_fee{fee}']=dict(legacy=encode(legacy),incumbent=encode(control),candidate=encode(candidate),gates=gates,passes=all(gates.values()))
    return dict(comparisons=comparisons,strict_mean_gain_somewhere=gain,
        research_screen_passed=gain and all(c['passes'] for c in comparisons.values()),deployment_eligible=False)


def main(complete=False):
    inputs=read(OUT/'run_inputs.json');assert all(sha(p)==h for p,h in inputs.items())
    fixture=read(ROOT/'data/frontier_20260912/ledger/fixture.json');markets=read(ROOT/'data/frontier_20260912/ledger/markets.json')
    cases=read(OUT/'replay/cases.json');corrected=[];pending=[]
    destination=OUT/'audits';destination.mkdir(exist_ok=True)
    source_hashes={str(p):sha(p) for p in (Path(__file__),HERE/'account_reference_v2.py',HERE/'build.py')}
    for case in cases:
        folder=OUT/'accounts'/case['id'];output=destination/(case['id']+'.json')
        if not (folder/'exit.json').exists():pending.append(case['id']);continue
        assert read(folder/'exit.json')['returncode']==0
        if output.exists():
            report=read(output)
            assert report['verified'] and report['case']==case and report['source_hashes']==source_hashes
            assert all(sha(p)==h for p,h in report['hashes'].items())
        else:
            command=read(folder/'command.json');assert command['case']==case
            env=command['env'];assert env['POLONIEX_LEDGER_OUT']==str(folder/'results.jsonl')
            assert env['RESEARCH_COOLDOWN']==str(case['cooldown']) and env['RESEARCH_CYCLES']==str(case['cycles'])
            assert env['RESEARCH_VARIANT']==str(case['variant']) and env['RESEARCH_FEE']==str(case['fee']) and env['RESEARCH_DAYS']==str(case['days'])
            rows=[json.loads(l) for l in (folder/'results.jsonl').read_text().splitlines()]
            n=len(fixture['Hours']);bars=case['days']*24 if case['days'] else n
            bounds=[(fixture['Hours'][a]['TS'],fixture['Hours'][min(n,a+bars)-1]['TS']) for a in range(0,n,bars) if min(n,a+bars)-a>=168]
            assert [(r['Start'],r['End']) for r in rows]==bounds
            hashes={str(p):sha(p) for p in (folder/'command.json',folder/'exit.json',folder/'results.jsonl',folder/'output.log')}
            check=Check();results=[]
            for row in rows:
                assert row['Days']==case['days'] and row['Cooldown']==case['cooldown'] and row['WindowCycles']==case['cycles']
                assert row['Fee']==case['fee'] and row['SlotTopUp']==case['variant'] and Path(row['Ledger']).name==row['Ledger']
                ledger=folder/row['Ledger'];hashes[str(ledger)]=sha(ledger)
                result=verify(read(ledger),row,case,fixture,markets,check)
                result.update(start=row['Start'],end=row['End'],ledger=str(ledger));results.append(result)
            report=dict(verified=True,at_ns=time.time_ns(),case=case,accounts=results,comparisons=check.count,
                maximum_metric_error=str(check.maximum),hashes=hashes,source_hashes=source_hashes,recorded_intents_are_inputs=True,live_changed=False)
            save(output,report);print('POLONIEX_CASE_AUDITED',case['id'],len(results),flush=True)
        if case['phase']=='corrected':corrected.append(report)
    if complete:
        assert not pending and read(OUT/'run_complete.json')['corrected_accounts']==135
        assert len(corrected)==27 and sum(len(c['accounts']) for c in corrected)==135
        assert read(OUT/'parity.json')['verified']
        summary=summarize(corrected);summary.update(verified=True,accounts=135,groups=9,independent_holdout=False,live_changed=False)
        save(OUT/'summary.json',summary)
        hashes={str(p):sha(p) for p in (*destination.glob('*.json'),OUT/'summary.json',OUT/'run_complete.json',OUT/'run_inputs.json',OUT/'parity.json')}
        assert all(sha(p)==h for p,h in inputs.items()) and all(sha(p)==h for p,h in source_hashes.items())
        save(OUT/'verification.json',dict(verified=True,accounts=135,comparisons=sum(r['comparisons'] for r in corrected),
            maximum_metric_error=str(max(D(r['maximum_metric_error']) for r in corrected)),hashes=hashes,source_hashes=source_hashes,
            research_screen_passed=summary['research_screen_passed'],deployment_eligible=False,live_changed=False))
        print('POLONIEX_COMPLETE_SCREEN',summary['research_screen_passed'],flush=True)
    else:print('AUDIT_PROGRESS',len(cases)-len(pending),'/',len(cases),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--complete',action='store_true');main(p.parse_args().complete)
