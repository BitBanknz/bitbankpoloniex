"""Verify the exact-release correction against every qualified research ledger."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from build import OUT,QUOTE,REPO,read,save,sha
sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native

def main():
    release=OUT/'release_candidate';assert read(release/'validation.json')['verified']
    output=release/'parity';output.mkdir(exist_ok=False)
    native=Native(release/'observed/engine.test');checked=0
    try:
        rows=[json.loads(line) for line in gzip.decompress((QUOTE/'paired_replay_v2/cycles.jsonl.gz').read_bytes()).splitlines()]
        rows=[r for r in rows if not r['input']['Config']['QuoteAwareEntry']]
        rows.extend(read(p) for p in (OUT/'regressions').glob('*.json') if p.name!='verification.json')
        assert len(rows)==30
        for row in rows:
            result=native.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):assert result[key]==row['output'][key],(row['input']['ID'],key)
            checked+=1
    finally:native.close()
    save(output/'cycle_parity.json',dict(verified=True,cycles=checked,binary_sha256=sha(release/'observed/engine.test')))
    cases=read(OUT/'cases.json');proofs=[]
    inputs={str(p):sha(p) for p in [Path(__file__),release/'validation.json',release/'historical/engine.test',OUT/'independent_verification.json',OUT/'cases.json']}
    save(output/'inputs.json',inputs)
    def run(case):
        folder=output/case['id'];folder.mkdir()
        temp=Path(tempfile.mkdtemp(prefix='release_guard_',dir='/dev/shm'))
        env=dict(PATH='/usr/local/go/bin:/usr/bin:/bin',GOMAXPROCS='1',TMPDIR=str(temp),POLONIEX_LEDGER_FIXTURE=str(REPO/'data/frontier_20260912/ledger/fixture.json'),POLONIEX_LEDGER_MARKETS=str(REPO/'data/frontier_20260912/ledger/markets.json'),POLONIEX_LEDGER_OUT=str(folder/'results.jsonl'),RESEARCH_DAYS=str(case['days']),RESEARCH_VARIANT='1',RESEARCH_COOLDOWN='120',RESEARCH_CYCLES='60',RESEARCH_FEE=str(case['fee']))
        argv=[str(release/'historical/engine.test'),'-test.run=^TestFrozenLedgerReplay$','-test.timeout=0']
        save(folder/'command.json',dict(argv=argv,env=env,case=case))
        with (folder/'output.log').open('x') as log:
            p=subprocess.Popen(argv,cwd=release/'source',env=env,stdout=log,stderr=subprocess.STDOUT);save(folder/'launch.json',dict(pid=p.pid,at_ns=time.time_ns()));code=p.wait()
        save(folder/'exit.json',dict(returncode=code,at_ns=time.time_ns()));assert code==0;temp.rmdir()
        reference=OUT/'accounts'/case['id'];assert (folder/'results.jsonl').read_bytes()==(reference/'results.jsonl').read_bytes()
        rows=[json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()]
        matches=[]
        for row in rows:
            actual=folder/row['Ledger'];expected=reference/row['Ledger'];assert actual.read_bytes()==expected.read_bytes()
            matches.append(dict(actual=str(actual),reference=str(expected),sha256=sha(actual)))
        return case['id'],matches
    with ThreadPoolExecutor(max_workers=3) as pool:
        for task in as_completed([pool.submit(run,c) for c in cases]):
            case,matches=task.result();proofs.extend(matches)
            p=output/'heartbeat.tmp';p.write_text(json.dumps(dict(at_ns=time.time_ns(),verified_accounts=len(proofs),total_accounts=45)));os.replace(p,output/'heartbeat.json')
            print('RELEASE_HISTORY_PARITY',case,len(matches),flush=True)
    assert len(proofs)==45 and all(sha(p)==h for p,h in inputs.items())
    save(output/'verification.json',dict(verified=True,at_ns=time.time_ns(),native_cycles=30,historical_accounts=45,all_complete_ledgers_and_reports_byte_identical=True,proofs=proofs,live_binary_sha256=sha(release/'bitbankpoloniex'),input_manifest_sha256=sha(output/'inputs.json')))

if __name__=='__main__':main()
