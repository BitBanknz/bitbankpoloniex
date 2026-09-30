"""Paired stop regression and all 45 preregistered historical control ledgers."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from build import HERE,OUT,OLD,QUOTE,REPO,sha,save,read

sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native
from replay_v2 import money


def regressions():
    worker=Native(OUT/'observed/engine.test');folder=OUT/'regressions';folder.mkdir()
    rows=[json.loads(line) for line in __import__('gzip').decompress((QUOTE/'paired_replay_v2/cycles.jsonl.gz').read_bytes()).splitlines()]
    unchanged=0;cases=[]
    try:
        for row in rows:
            request=row['input'];answer=worker.apply(request)
            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==row['output'][key],(request['ID'],key)
            money(request['Before'],answer['State'],str(request['Config']['FeeRate']));unchanged+=1
        # Follow the new state, not the old buggy state, into the next cycle.
        for aware in (False,True):
            first=read(QUOTE/'stop_refill_probe_v2'/f'stop_refill_{int(aware)}_0.json')['input']
            state=deepcopy(first['Before'])
            for cycle in range(2):
                request=deepcopy(first);request['ID']=f'guard_{int(aware)}_{cycle}';request['Before']=state;request['NowNS']+=cycle*60_000_000_000
                for path,response in request['Responses'].items():
                    if path.endswith('/orderBook'):response['Body']['ts']=request['NowNS']//1_000_000
                    if path=='/markets/ticker24h':
                        for ticker in response['Body']:ticker['ts']=request['NowNS']//1_000_000
                answer=worker.apply(request);money(state,answer['State'],'.003')
                new=(answer['State']['Fills'] or [])[len(state['Fills'] or []):]
                sides=[f['Order']['side'] for f in new if f['Order']['symbol']=='AAA_USDT']
                assert sides==(['SELL'] if cycle==0 else []),sides
                assert answer['State']['Holdings']['AAA_USDT']['Quantity']=='5.1'
                save(folder/(request['ID']+'.json'),dict(input=request,output=answer));cases.append(request['ID']);state=answer['State']
        # A stop whose sell is rejected must not permit a new top-up either.
        request=read(QUOTE/'stop_refill_probe_v2/stop_refill_0_0.json')['input'];request=deepcopy(request);request['ID']='blocked_stop'
        request['Responses']['/markets/AAA_USDT/orderBook']['Body']['asks']=['11','1000']
        answer=worker.apply(request);money(request['Before'],answer['State'],'.003')
        assert not any(f['Order']['symbol']=='AAA_USDT' for f in answer['State']['Fills'] or [])
        save(folder/'blocked_stop.json',dict(input=request,output=answer));cases.append('blocked_stop')
    finally:worker.close()
    save(folder/'verification.json',dict(verified=True,unchanged_native_cycles=unchanged,protective_cases=cases,remaining_stopped_quantity='5.1',old_remaining_quantity='9.895204',sell_caps_and_ids_unchanged=True,
        hashes={str(p):sha(p) for p in folder.iterdir() if p.is_file()}))
    print('STOP_REGRESSIONS_PASSED',unchanged,len(cases),flush=True)


def main():
    assert read(OUT/'validation.json')['verified'] and read(OUT/'historical/verification.json')['verified']
    regressions()
    cases=[c for c in read(OLD/'replay/cases.json') if c['phase']=='corrected' and c['variant']==1];assert len(cases)==9
    bound={str(p):sha(p) for p in [Path(__file__),OUT/'validation.json',OUT/'historical/engine.test',OLD/'replay/cases.json',REPO/'data/frontier_20260912/ledger/fixture.json',REPO/'data/frontier_20260912/ledger/markets.json']}
    save(OUT/'run_inputs.json',bound);save(OUT/'cases.json',cases)
    completed=[];matches=[]
    def run(case):
        assert all(sha(p)==h for p,h in bound.items());folder=OUT/'accounts'/case['id'];folder.mkdir(parents=True,exist_ok=False)
        temp=Path(tempfile.mkdtemp(prefix='stop_guard_',dir='/dev/shm'))
        env=dict(PATH='/usr/local/go/bin:/usr/bin:/bin',GOMAXPROCS='1',TMPDIR=str(temp),POLONIEX_LEDGER_FIXTURE=str(REPO/'data/frontier_20260912/ledger/fixture.json'),POLONIEX_LEDGER_MARKETS=str(REPO/'data/frontier_20260912/ledger/markets.json'),POLONIEX_LEDGER_OUT=str(folder/'results.jsonl'),RESEARCH_DAYS=str(case['days']),RESEARCH_VARIANT='1',RESEARCH_COOLDOWN='120',RESEARCH_CYCLES='60',RESEARCH_FEE=str(case['fee']))
        argv=[str(OUT/'historical/engine.test'),'-test.run=^TestFrozenLedgerReplay$','-test.timeout=0']
        save(folder/'command.json',dict(argv=argv,env=env,case=case))
        with (folder/'output.log').open('x') as log:
            p=subprocess.Popen(argv,env=env,cwd=OUT/'source',stdout=log,stderr=subprocess.STDOUT);save(folder/'launch.json',dict(pid=p.pid,at_ns=time.time_ns()));code=p.wait()
        save(folder/'exit.json',dict(returncode=code,at_ns=time.time_ns()));assert code==0,case;temp.rmdir()
        old=OLD/'accounts'/case['id'];assert (folder/'results.jsonl').read_bytes()==(old/'results.jsonl').read_bytes(),('results changed',case['id'])
        rows=[json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()];assert len(rows)=={0:1,28:9,56:5}[case['days']]
        proof=[]
        for row in rows:
            new=folder/row['Ledger'];previous=old/row['Ledger'];assert new.read_bytes()==previous.read_bytes(),('ledger changed',new)
            proof.append(dict(new=str(new),previous=str(previous),sha256=sha(new)))
        return case,proof
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in as_completed([pool.submit(run,c) for c in cases]):
            case,proof=result.result();completed.append(case['id']);matches.extend(proof)
            temp=OUT/'heartbeat.tmp';temp.write_text(json.dumps(dict(at_ns=time.time_ns(),pid=os.getpid(),completed=completed,total_cases=9)));os.replace(temp,OUT/'heartbeat.json')
            print('STOP_HISTORY_DONE',case['id'],len(proof),flush=True)
    assert len(matches)==45 and all(sha(p)==h for p,h in bound.items())
    save(OUT/'historical_parity.json',dict(verified=True,at_ns=time.time_ns(),cases=9,accounts=45,all_reports_and_complete_ledgers_byte_identical=True,ledgers=matches,input_manifest_sha256=sha(OUT/'run_inputs.json'),new_alpha_established=False))

if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        save(OUT/('failure_'+str(time.time_ns())+'.json'),dict(at_ns=time.time_ns(),error=traceback.format_exc()));raise
