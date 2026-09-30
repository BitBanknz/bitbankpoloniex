"""Bounded local offline pipeline; no worker restarts, credentials or live orders."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from capture import OUT,HERE,sha,save

def main():
    save(OUT/'offline_pipeline_started.json',dict(at_ns=time.time_ns(),pid=os.getpid(),pipeline_sha256=sha(Path(__file__)),deadline_seconds=3600))
    deadline=time.monotonic()+3600
    while not (OUT/'capture.verified.json').exists():
        assert time.monotonic()<deadline,'capture did not finish within bounded wait'
        time.sleep(1)
    json.loads((OUT/'capture.verified.json').read_bytes())
    temp=Path(tempfile.mkdtemp(prefix='poloniex-prefix-audit-',dir='/dev/shm'))
    try:
        for name in ('audit.py','summarize.py','diagnose_signals.py'):
            print('START',name,time.time_ns(),flush=True)
            result=subprocess.run([sys.executable,str(HERE/name)],env={**os.environ,'TMPDIR':str(temp)},cwd=HERE.parents[1])
            assert result.returncode==0,(name,result.returncode)
            print('DONE',name,time.time_ns(),flush=True)
    finally:shutil.rmtree(temp)
    save(OUT/'offline_pipeline_finished.json',dict(at_ns=time.time_ns(),verified=True,pipeline_sha256=sha(Path(__file__))))

if __name__=='__main__':main()
