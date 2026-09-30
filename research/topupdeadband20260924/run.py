"""Run the fixed matrix with four isolated, CPU-limited loopback processes."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from build import ROOT,HERE,OUT,read,save,sha


def main():
    replay=OUT/'replay';validation=read(replay/'verification.json')
    assert validation['verified'] and sha(replay/'engine_replay.test')==validation['binary_sha256']
    inputs=read(replay/'inputs.json')
    inputs.update({str(p):sha(p) for p in [Path(__file__),OUT/'registration.json',OUT/'validation.json',OUT/'live_health.json',replay/'verification.json',replay/'engine_replay.test',ROOT/'docs/2026-09-24-topup-deadband-prereg.md']})
    save(OUT/'run_inputs.json',inputs)
    cases=read(replay/'cases.json');completed=[]
    def check():
        assert all(sha(p)==h for p,h in inputs.items())
        assert shutil.disk_usage(OUT).free>40<<30
    def run(case):
        check();folder=OUT/'accounts'/case['id'];folder.mkdir(parents=True,exist_ok=False)
        temporary=Path(tempfile.mkdtemp(prefix='poloniex_deadband_',dir='/dev/shm'))
        env=dict(PATH='/usr/local/go/bin:/usr/bin:/bin',GOMAXPROCS='1',TMPDIR=str(temporary),
            POLONIEX_LEDGER_FIXTURE=str(ROOT/'data/frontier_20260912/ledger/fixture.json'),
            POLONIEX_LEDGER_MARKETS=str(ROOT/'data/frontier_20260912/ledger/markets.json'),POLONIEX_LEDGER_OUT=str(folder/'results.jsonl'),
            RESEARCH_DAYS=str(case['days']),RESEARCH_VARIANT=str(case['variant']),RESEARCH_COOLDOWN=str(case['cooldown']),RESEARCH_CYCLES=str(case['cycles']),RESEARCH_FEE=str(case['fee']))
        argv=[str(replay/'engine_replay.test'),'-test.run','^TestFrozenLedgerReplay$','-test.v','-test.timeout=0']
        save(folder/'command.json',dict(argv=argv,env=env,cwd=str(OUT/'source'),case=case))
        with (folder/'output.log').open('x') as log:
            process=subprocess.Popen(argv,cwd=OUT/'source',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
            save(folder/'launch.json',dict(pid=process.pid,at_ns=time.time_ns()))
            code=process.wait()
        save(folder/'exit.json',dict(returncode=code,at_ns=time.time_ns()));assert code==0,folder
        temporary.rmdir()
        rows=[__import__('json').loads(l) for l in (folder/'results.jsonl').read_text().splitlines()]
        expected={0:1,28:9,56:5}[case['days']]
        assert len(rows)==expected
        assert all(r['Cooldown']==case['cooldown'] and r['WindowCycles']==case['cycles'] and r['SlotTopUp']==case['variant'] and r['Fee']==case['fee'] for r in rows)
        check();return case,rows
    for phase in ('parity','corrected'):
        phase_results=[]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(run,c) for c in cases if c['phase']==phase]
            for future in as_completed(futures):
                case,rows=future.result();phase_results.append((case,rows));completed.append(case['id'])
                tmp=OUT/'heartbeat.tmp'
                with tmp.open('w') as f:__import__('json').dump(dict(at_ns=time.time_ns(),pid=os.getpid(),phase=phase,completed=completed,total_cases=len(cases)),f)
                os.replace(tmp,OUT/'heartbeat.json')
                print('REPLAY_CASE_DONE',case['id'],len(rows),flush=True)
        if phase=='parity':
            proofs=[]
            for case,rows in phase_results:
                p=OUT/'accounts'/case['id']/rows[0]['Ledger']
                old=Path('/tmp/claude-1000/topup0924')/f"ledger_fee{case['fee']}_bonus{case['variant']}.json"
                assert p.read_bytes()==old.read_bytes(),('original ledger parity',case['id'])
                proofs.append(dict(case=case['id'],path=str(p),original=str(old),sha256=sha(p)))
            save(OUT/'parity.json',dict(verified=True,accounts=4,byte_identical_complete_ledgers=proofs,completed_ns=time.time_ns()))
            print('ORIGINAL_PARITY_PASSED',4,flush=True)
        else:
            assert sum(len(rows) for _,rows in phase_results)==135
    check()
    save(OUT/'run_complete.json',dict(verified=True,at_ns=time.time_ns(),cases=len(cases),parity_accounts=4,corrected_accounts=135,
        input_manifest_sha256=sha(OUT/'run_inputs.json'),independent_audit_pending=True,live_changed=False,deployment_eligible=False))


if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        save(OUT/('run_failure_'+str(time.time_ns())+'.json'),dict(at_ns=time.time_ns(),error=traceback.format_exc()))
        raise
