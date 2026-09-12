#!/usr/bin/env python3
"""Rebase fixed research variants on the validated protective-exit repairs."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('study',choices=['ledger','ledger_dust','ledger_extended']);a=p.parse_args()
root=Path(__file__).resolve().parents[2];source=root/'data/frontier_20260912'/a.study
if a.study=='ledger_extended':
    passed=json.loads((source.with_name('ledger_rebased')/'comparison.json').read_text())
    assert passed['status']=='COMPLETE' and passed['qualifies_for_further_research']
out=source.with_name(a.study+'_rebased')/'overlay';out.mkdir(parents=True,exist_ok=False)
oldbase=root/'data/frontier_20260912/stop-priority/engine.before.go.txt'
current=root/'internal/bot/engine.go'
original=json.loads((source/'overlay.json').read_text());replace={}
for virtual,actual in original['Replace'].items():
    text=Path(actual).read_text()
    if virtual.endswith('/engine.go'):
        with tempfile.TemporaryDirectory() as tmp:
            modified=Path(tmp)/'variant.go';modified.write_text(text.replace('replayNow()','time.Now()'))
            result=subprocess.run(['git','merge-file','-p',str(current),str(oldbase),str(modified)],capture_output=True,text=True)
            assert result.returncode==0,result.stdout+result.stderr
            text=result.stdout.replace('time.Now()','replayNow()')
    target=out/(Path(virtual).name+'.txt');target.write_text(text);replace[virtual]=str(target)
(out.parent/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
(out.parent/'rebase.json').write_text(json.dumps(dict(study=a.study,only_change='merge final protective priority/partial-book/day-recovery engine; frozen variant and driver otherwise retained',sha256={str(q.relative_to(root)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [current,oldbase,source/'overlay.json',*out.glob('*.txt')]}),indent=2)+'\n')
print(out.parent)
