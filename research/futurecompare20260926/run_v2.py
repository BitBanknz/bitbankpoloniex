"""Run the fully checked replacement audit and retained comparisons offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from capture import HERE,OUT,sha,save

def main():
    root=OUT/'completed_v2';root.mkdir(exist_ok=False)
    (root/'mirror').symlink_to(OUT/'mirror',target_is_directory=True)
    save(root/'pipeline_started.json',dict(at_ns=time.time_ns(),pid=os.getpid(),hashes={str(p):sha(p) for p in [Path(__file__),HERE/'audit_parallel_v2.py',HERE/'trace_evidence.py',OUT/'trace_evidence_tests.log',OUT/'audit_v2_derivation.json']},external_orders=False))
    temp=Path(tempfile.mkdtemp(prefix='polo-prefix-v2-',dir='/dev/shm'))
    try:
        result=subprocess.run([sys.executable,'-u',str(HERE/'audit_parallel_v2.py')],cwd=HERE.parents[1],env={**os.environ,'TMPDIR':str(temp)})
        assert result.returncode==0,('audit',result.returncode)
        import summarize,diagnose_signals
        summarize.OUT=root;diagnose_signals.OUT=root
        summarize.main();diagnose_signals.main()
    finally:shutil.rmtree(temp)
    save(root/'pipeline_finished.json',dict(at_ns=time.time_ns(),verified=True,pipeline_sha256=sha(Path(__file__))))

if __name__=='__main__':main()
