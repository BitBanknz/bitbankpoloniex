"""Package and test a separate future worker candidate; never starts it."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
OLD=REPO/'research/quoteaware20260924'
OUT=Path('/vfast/data/trading_research_20260924/poloniex_completed_cycle_worker_v1')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')
def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)

def main():
    OUT.mkdir(exist_ok=False);worker=OUT/'worker';worker.mkdir()
    inputs=[Path(__file__),HERE/'outcomes.py',HERE/'test_outcomes.py',REPO/'docs/2026-09-26-paper-cycle-outcomes-protocol.md',OLD/'shadow.py',OLD/'native.py',OLD/'receipt_rules.py']
    hashes={str(p):sha(p) for p in inputs}
    assert sha(OLD/'shadow.py')=='dc31ada6424eb4e6b2eccb6694cb4a5147f31ad0be09b95df4d8ee94869fa957'
    save(OUT/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,live_changed=False,existing_studies_changed=False))
    old=(OLD/'shadow.py').read_text()
    source=replace(old,'from native import Native','from native import Native\nfrom outcomes import completed_cycle')
    source=replace(source,"p['format']=='poloniex-fixed-future-replay-v1'","p['format']=='poloniex-fixed-future-replay-v2'")
    source=replace(source,"if answer['CycleError'] not in ('','BitBank unavailable and no accepted fallback; entries paused'):raise RuntimeError(answer['CycleError'])",
        "answer['CycleOutcome']=completed_cycle(account['Before'],answer,packet['Responses'],packet['NowNS'])")
    (worker/'shadow.py').write_text(source)
    for name in ('native.py','receipt_rules.py'):shutil.copyfile(OLD/name,worker/name)
    shutil.copyfile(HERE/'outcomes.py',worker/'outcomes.py')
    import difflib
    (OUT/'worker.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),source.splitlines(True),fromfile='frozen-v1/shadow.py',tofile='future-v2/shadow.py')))
    for label,argv in [('outcomes',[sys.executable,str(HERE/'test_outcomes.py'),'-v']),
                       ('inherited',[sys.executable,str(OLD/'test_shadow.py'),'-v']),
                       ('compile',[sys.executable,'-m','py_compile',*[str(p) for p in worker.glob('*.py')]])]:
        with (OUT/(label+'.log')).open('x') as log:
            result=subprocess.run(argv,cwd=worker,env={**os.environ,'PYTHONPATH':str(worker)},stdout=log,stderr=subprocess.STDOUT)
        save(OUT/(label+'.receipt.json'),dict(at_ns=time.time_ns(),argv=argv,returncode=result.returncode,log_sha256=sha(OUT/(label+'.log'))))
        assert result.returncode==0,label
    # Ensure inherited tests exercised the derived candidate, not their script directory.
    script="import sys,unittest;sys.path.insert(0,"+repr(str(OLD))+");import test_shadow;sys.path.insert(0,"+repr(str(worker))+");sys.modules.pop('shadow',None);import shadow;assert shadow.__file__=="+repr(str(worker/'shadow.py'))+";test_shadow.shadow=shadow;result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_shadow));sys.exit(not result.wasSuccessful())"
    with (OUT/'candidate_inherited.log').open('x') as log:result=subprocess.run([sys.executable,'-c',script],cwd=worker,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0,'candidate inherited tests'
    assert all(sha(p)==h for p,h in hashes.items())
    save(OUT/'verification.json',dict(at_ns=time.time_ns(),verified=True,hashes=hashes,
        worker_files={p.name:sha(p) for p in worker.glob('*.py')},test_counts=dict(outcomes=5,candidate_inherited=12),
        artifacts={p.name:sha(p) for p in OUT.iterdir() if p.is_file()},live_changed=False,existing_studies_changed=False,
        candidate_launched=False,profitability_established=False))
    print('COMPLETED_CYCLE_WORKER_VERIFIED',str(OUT),flush=True)

if __name__=='__main__':main()
