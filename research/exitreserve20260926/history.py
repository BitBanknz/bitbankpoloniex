"""All 135 registered native historical accounts with independent financial audit."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from decimal import Decimal as D
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from build import BASE,HERE,OUT,PARENT,REPO,ARMS,read,save,sha
from account_reference import Check,verify


def main():
    root=OUT/'historical_accounts';root.mkdir(exist_ok=False)
    parent=BASE/'poloniex_stop_topup_guard_v1'
    prior=read(parent/'run_inputs.json');assert all(sha(p)==h for p,h in prior.items())
    assert read(OUT/'regressions_v3/verification.json')['verified']
    parity=read(PARENT/'parity/verification.json');assert parity['verified']
    for proof in parity['proofs']:assert sha(proof['actual'])==sha(proof['reference'])==proof['sha256']
    cases=read(parent/'cases.json');assert len(cases)==9
    fixture_path=REPO/'data/frontier_20260912/ledger/fixture.json'
    markets_path=REPO/'data/frontier_20260912/ledger/markets.json'
    paths=[Path(__file__),HERE/'account_reference.py',HERE/'reference_derivation.json',
           parent/'cases.json',parent/'run_inputs.json',PARENT/'parity/verification.json',
           OUT/'regressions_v3/verification.json',OUT/'historical/engine.test',OUT/'historical/verification.json',
           fixture_path,markets_path]
    hashes={str(p):sha(p) for p in paths}
    save(root/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,cases=cases,arms=ARMS,historical_reuse=True))

    def run(case,arm):
        folder=root/arm/case['id'];folder.mkdir(parents=True,exist_ok=False)
        temp=Path(tempfile.mkdtemp(prefix='exit-reserve-history-',dir='/dev/shm'))
        env=dict(PATH='/usr/local/go/bin:/usr/bin:/bin',GOMAXPROCS='1',TMPDIR=str(temp),
                 POLONIEX_LEDGER_FIXTURE=str(fixture_path),POLONIEX_LEDGER_MARKETS=str(markets_path),
                 POLONIEX_LEDGER_OUT=str(folder/'results.jsonl'),RESEARCH_DAYS=str(case['days']),
                 RESEARCH_VARIANT='1',RESEARCH_COOLDOWN='120',RESEARCH_CYCLES='60',
                 RESEARCH_FEE=str(case['fee']),RESEARCH_ARM=arm)
        argv=[str(OUT/'historical/engine.test'),'-test.run=^TestFrozenLedgerReplay$','-test.timeout=0']
        save(folder/'command.json',dict(argv=argv,env=env,case=case,arm=arm))
        with (folder/'output.log').open('x') as log:
            process=subprocess.Popen(argv,cwd=OUT/'source',env=env,stdout=log,stderr=subprocess.STDOUT)
            save(folder/'launch.json',dict(pid=process.pid,at_ns=time.time_ns()))
            result=process.wait()
        save(folder/'exit.json',dict(returncode=result,at_ns=time.time_ns()));assert result==0,(case['id'],arm)
        temp.rmdir()
        rows=[json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()]
        assert len(rows)=={0:1,28:9,56:5}[case['days']]
        if arm=='baseline':
            expected=PARENT/'parity'/case['id']
            assert (folder/'results.jsonl').read_bytes()==(expected/'results.jsonl').read_bytes()
            for row in rows:assert (folder/row['Ledger']).read_bytes()==(expected/row['Ledger']).read_bytes()
        return dict(case=case['id'],arm=arm,accounts=len(rows))

    completed=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for task in as_completed([pool.submit(run,case,arm) for case in cases for arm in ARMS]):
            report=task.result();completed.append(report)
            temporary=root/'heartbeat.tmp';temporary.write_text(json.dumps(dict(at_ns=time.time_ns(),completed=completed,total_jobs=27)))
            os.replace(temporary,root/'heartbeat.json')
            print('EXIT_RESERVE_HISTORY',report,flush=True)
    fixture,markets=read(fixture_path),read(markets_path);check=Check();accounts=[];rejected={}
    for case in cases:
        reports={arm:[json.loads(line) for line in (root/arm/case['id']/'results.jsonl').read_text().splitlines()] for arm in ARMS}
        for triple in zip(*(reports[arm] for arm in ARMS),strict=True):
            assert len({(row['Start'],row['End']) for row in triple})==1
            account=dict(case=case['id'],start=triple[0]['Start'],end=triple[0]['End'],arms={},bindings={})
            states={}
            for arm,row in zip(ARMS,triple):
                path=root/arm/case['id']/row['Ledger'];state=read(path);states[arm]=state
                maximum,reserve=ARMS[arm]
                account['arms'][arm]=verify(state,row,case,fixture,markets,check,require_stop_guard=True,
                                            max_orders_day=maximum,exit_order_reserve=reserve)
                account['bindings'][arm]=dict(path=str(path),sha256=sha(path))
                if arm=='baseline':
                    for name,limit,held in [('total_order_budget',9,0),('buy_order_budget',12,3)]:
                        if name in rejected:continue
                        try:verify(state,row,case,fixture,markets,Check(),require_stop_guard=True,max_orders_day=limit,exit_order_reserve=held)
                        except AssertionError as error:
                            assert error.args and isinstance(error.args[0],tuple) and error.args[0][0]==name,error
                            rejected[name]=dict(case=case['id'],start=row['Start'])
                if 'corrupted_id' not in rejected and state['Fills']:
                    changed=deepcopy(state);changed['Fills'][0]['Order']['clientOrderId']='bbp-corrupted'
                    try:verify(changed,row,case,fixture,markets,Check(),require_stop_guard=True,max_orders_day=maximum,exit_order_reserve=reserve)
                    except AssertionError:rejected['corrupted_id']=dict(case=case['id'],arm=arm,start=row['Start'])
                    else:raise AssertionError('corrupted decision ID accepted')
            accounts.append(account)
    assert len(accounts)==45 and set(rejected)=={'total_order_budget','buy_order_budget','corrupted_id'}
    assert all(sha(p)==h for p,h in hashes.items())
    save(root/'accounts.json',accounts)
    save(root/'verification.json',dict(verified=True,at_ns=time.time_ns(),accounts_per_arm=45,total_accounts=135,
        baseline_reports_and_ledgers_byte_exact=True,exact_comparisons=check.count,maximum_metric_error=str(check.maximum),
        budget_and_id_rejections=rejected,accounts_sha256=sha(root/'accounts.json'),registration_sha256=sha(root/'registration.json'),
        historical_reuse=True,full_policy_oracle=False,live_changed=False,deployment_qualified=False))
    print('EXIT_RESERVE_HISTORY_VERIFIED',135,check.count,flush=True)


if __name__=='__main__':main()
