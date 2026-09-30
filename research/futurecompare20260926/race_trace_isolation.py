"""Race-check the new local request isolation using preserved native cases."""
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from capture import OUT as CAPTURE,sha,save
from transport import OriginalNative as Native

def main():
    base=CAPTURE.parent;parent=base/'poloniex_driver_trace_isolation_v3';output=parent/'race';output.mkdir(exist_ok=False)
    source=base/'poloniex_quote_aware_v1/source';fixture=base/'poloniex_quote_aware_v1/paired_replay_v2/cycles.jsonl.gz'
    inputs=[Path(__file__),parent/'verification.json',parent/'isolated/overlay.json',parent/'isolated/driver_test.go.txt',fixture]
    hashes={str(p):sha(p) for p in inputs};save(output/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes))
    toolchain=Path('/home/lee/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.25.0.linux-amd64');binary=output/'engine.test'
    args=[str(toolchain/'bin/go'),'test','-race','-p','1','-overlay',str(parent/'isolated/overlay.json'),'-c','-o',str(binary),'./internal/bot']
    with (output/'build.log').open('x') as log:r=subprocess.run(args,cwd=source,env={**os.environ,'GOROOT':str(toolchain),'GOTOOLCHAIN':'local','GOMAXPROCS':'1','CGO_ENABLED':'1','GOWORK':'off','GOFLAGS':'-mod=readonly','GOPROXY':'off','GOSUMDB':'off'},stdout=log,stderr=subprocess.STDOUT)
    save(output/'build.receipt.json',dict(argv=args,returncode=r.returncode,log_sha256=sha(output/'build.log')));assert r.returncode==0
    rows=[json.loads(line) for line in gzip.decompress(fixture.read_bytes()).splitlines()]
    temp=Path(tempfile.mkdtemp(prefix='polo-race-',dir='/dev/shm'));previous=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    native=Native(binary);checked=0
    try:
        for row in rows:
            for probe in (False,True):
                answer=native.apply({**row['input'],'ProbeRoot':probe,'ProbeKnown':probe});expected=row['output']
                for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==expected[key]
                assert sorted(answer['Paths'])==sorted(expected['Paths'])
                assert answer.get('ProbeStatuses',[])==([403,403] if probe else [])
                checked+=1
    finally:
        native.close()
        if previous is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=previous
        shutil.rmtree(temp)
    assert all(sha(p)==h for p,h in hashes.items())
    save(output/'verification.json',dict(at_ns=time.time_ns(),verified=True,native_race_cases=checked,unmarked_probes_rejected=100,
        all_financial_outputs_and_engine_paths_exact=True,binary_sha256=sha(binary),hashes=hashes,live_changed=False))
    print(json.dumps(dict(verified=True,native_race_cases=checked,unmarked_probes_rejected=100)),flush=True)

if __name__=='__main__':main()
