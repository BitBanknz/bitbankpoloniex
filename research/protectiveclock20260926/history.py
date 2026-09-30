"""Run all fixed historical controls/treatments and independently audit each."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from decimal import Decimal as D
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from build import BASE, HERE, OUT, PARENT, REPO, read, save, sha
from account_reference import Check, verify


def main():
    root=OUT/'historical_accounts';root.mkdir(exist_ok=False)
    parent=BASE/'poloniex_stop_topup_guard_v1'
    original_inputs=read(parent/'run_inputs.json')
    assert all(sha(path)==h for path,h in original_inputs.items())
    assert read(OUT/'regressions/verification.json')['verified']
    parity=read(PARENT/'parity/verification.json');assert parity['verified']
    for proof in parity['proofs']:
        assert sha(proof['actual'])==sha(proof['reference'])==proof['sha256']
    cases=read(parent/'cases.json');assert len(cases)==9
    fixture_path=REPO/'data/frontier_20260912/ledger/fixture.json'
    markets_path=REPO/'data/frontier_20260912/ledger/markets.json'
    inputs=[Path(__file__),HERE/'account_reference.py',HERE/'reference_derivation.json',
            parent/'cases.json',parent/'run_inputs.json',PARENT/'parity/verification.json',
            OUT/'regressions/verification.json',OUT/'historical/engine.test',
            OUT/'historical/verification.json',fixture_path,markets_path]
    hashes={str(p):sha(p) for p in inputs}
    save(root/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,cases=cases,arms=[0,1],historical_reuse=True))

    def run(case,clock):
        folder=root/('clock' if clock else 'control')/case['id']
        folder.mkdir(parents=True,exist_ok=False)
        temp=Path(tempfile.mkdtemp(prefix='protective-clock-history-',dir='/dev/shm'))
        env=dict(PATH='/usr/local/go/bin:/usr/bin:/bin',GOMAXPROCS='1',TMPDIR=str(temp),
                 POLONIEX_LEDGER_FIXTURE=str(fixture_path),POLONIEX_LEDGER_MARKETS=str(markets_path),
                 POLONIEX_LEDGER_OUT=str(folder/'results.jsonl'),RESEARCH_DAYS=str(case['days']),
                 RESEARCH_VARIANT='1',RESEARCH_COOLDOWN='120',RESEARCH_CYCLES='60',
                 RESEARCH_FEE=str(case['fee']),RESEARCH_CLOCK=str(int(clock)))
        argv=[str(OUT/'historical/engine.test'),'-test.run=^TestFrozenLedgerReplay$','-test.timeout=0']
        save(folder/'command.json',dict(argv=argv,env=env,case=case,clock=clock))
        with (folder/'output.log').open('x') as log:
            process=subprocess.Popen(argv,cwd=OUT/'source',env=env,stdout=log,stderr=subprocess.STDOUT)
            save(folder/'launch.json',dict(pid=process.pid,at_ns=time.time_ns()))
            result=process.wait()
        save(folder/'exit.json',dict(returncode=result,at_ns=time.time_ns()));assert result==0,(case['id'],clock)
        temp.rmdir()
        rows=[json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()]
        assert len(rows)=={0:1,28:9,56:5}[case['days']]
        if not clock:
            expected=PARENT/'parity'/case['id']
            assert (folder/'results.jsonl').read_bytes()==(expected/'results.jsonl').read_bytes()
            for row in rows:assert (folder/row['Ledger']).read_bytes()==(expected/row['Ledger']).read_bytes()
        return case['id'],clock,len(rows)

    finished=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(run,case,clock) for case in cases for clock in (False,True)]
        for task in as_completed(tasks):
            name,clock,count=task.result();finished.append(dict(case=name,clock=clock,accounts=count))
            tmp=root/'heartbeat.tmp';tmp.write_text(json.dumps(dict(at_ns=time.time_ns(),completed=finished,total_jobs=18)))
            os.replace(tmp,root/'heartbeat.json')
            print('CLOCK_HISTORY',name,clock,count,flush=True)

    fixture=read(fixture_path);markets=read(markets_path);check=Check();groups=[];all_pairs=[]
    rejected_bad_id=False
    for case in cases:
        folders={arm:root/arm/case['id'] for arm in ('control','clock')}
        reports={arm:[json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()] for arm,folder in folders.items()}
        pairs=[]
        for original,candidate in zip(reports['control'],reports['clock']):
            assert original['Start']==candidate['Start'] and original['End']==candidate['End']
            states={};metrics={};bindings={}
            for arm,row in [('control',original),('clock',candidate)]:
                path=folders[arm]/row['Ledger'];states[arm]=read(path)
                metrics[arm]=verify(states[arm],row,case,fixture,markets,check,require_stop_guard=True,actual_stop_hour=arm=='clock')
                bindings[arm]=dict(path=str(path),sha256=sha(path))
            if not rejected_bad_id:
                mutated=deepcopy(states['clock'])
                targets=[f for f in mutated['Fills'] or [] if f['Order']['side']=='SELL']
                if targets:
                    targets[0]['Order']['clientOrderId']='bbp-corrupted'
                    try:verify(mutated,candidate,case,fixture,markets,Check(),require_stop_guard=True,actual_stop_hour=True)
                    except AssertionError:rejected_bad_id=True
                    else:raise AssertionError('corrupted decision ID accepted')
            difference={key:str(D(metrics['clock'][key])-D(metrics['control'][key]))
                        for key in ('return_pct','max_drawdown_pct','initial_budget_drawdown_pct','final_equity','fees')}
            pair=dict(case=case['id'],start=original['Start'],end=original['End'],control=metrics['control'],
                      clock=metrics['clock'],difference=difference,bindings=bindings)
            pairs.append(pair);all_pairs.append(pair)
        def statistics(arm):
            values=[p[arm] for p in pairs]
            return dict(mean_return_pct=str(sum(D(x['return_pct']) for x in values)/len(values)),
                        worst_return_pct=str(min(D(x['return_pct']) for x in values)),
                        maximum_drawdown_pct=str(max(D(x['max_drawdown_pct']) for x in values)),
                        fees=str(sum(D(x['fees']) for x in values)),fills=sum(x['fills'] for x in values))
        groups.append(dict(case=case,accounts=len(pairs),control=statistics('control'),clock=statistics('clock')))
    assert len(all_pairs)==45 and rejected_bad_id
    assert all(sha(path)==digest for path,digest in hashes.items())
    save(root/'accounts.json',all_pairs)
    result=dict(verified=True,at_ns=time.time_ns(),accounts_per_arm=45,default_off_complete_ledger_parity=True,
                exact_comparisons=check.count,maximum_metric_error=str(check.maximum),corrupted_decision_id_rejected=True,
                higher_return=sum(D(p['difference']['return_pct'])>0 for p in all_pairs),
                lower_return=sum(D(p['difference']['return_pct'])<0 for p in all_pairs),
                equal_return=sum(D(p['difference']['return_pct'])==0 for p in all_pairs),
                lower_drawdown=sum(D(p['difference']['max_drawdown_pct'])<0 for p in all_pairs),
                higher_drawdown=sum(D(p['difference']['max_drawdown_pct'])>0 for p in all_pairs),
                groups=groups,registration_sha256=sha(root/'registration.json'),accounts_sha256=sha(root/'accounts.json'),
                historical_reuse=True,synthetic_hourly_books=True,minute_liquidity_replenishment_established=False,
                independent_holdout=False,live_changed=False,deployment_qualified=False)
    save(root/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='groups'}),flush=True)

if __name__=='__main__':main()
