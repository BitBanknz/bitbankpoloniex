#!/usr/bin/env python3
"""Resume whole completed cells without changing the ledger experiment."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('study',choices=['ledger','ledger_dust'])
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
source=root/'data/frontier_20260912'/a.study
out=source/'resume_overlay'
out.mkdir(exist_ok=False)
results=source/'results.jsonl'
rows=[json.loads(s) for s in results.read_text().splitlines()]
skip={}
for r in rows:
    mode=str(r['DustMode']).lower() if a.study=='ledger_dust' else f"{r['Bonus']:g}"
    key=f"{r['Days']}|{r['Fee']:g}|{mode}|{r['Start']}|{r['End']}"
    assert key not in skip
    skip[key]=True
(out/'completed.json').write_text(json.dumps(skip)+'\n')
(out/'results.before.jsonl').write_bytes(results.read_bytes())
original=json.loads((source/'overlay.json').read_text());replace={}
for virtual,actual in original['Replace'].items():
    text=Path(actual).read_text()
    if virtual.endswith('frozen_ledger_research_test.go'):
        text=text.replace('os.O_CREATE|os.O_WRONLY|os.O_TRUNC','os.O_CREATE|os.O_WRONLY|os.O_APPEND')
        needle='var f replayFixture;replayRead(t,fixturePath,&f)'
        assert text.count(needle)==1
        text=text.replace(needle,needle+'\n var completed map[string]bool;replayRead(t,os.Getenv("POLONIEX_LEDGER_COMPLETED"),&completed)')
        needle='cfg:=DefaultConfig();cfg.StateDir=t.TempDir()'
        assert text.count(needle)==1
        mode,verb=('dustMode','%t') if a.study=='ledger_dust' else ('bonus','%g')
        before=f'key:=fmt.Sprintf("%d|%g|{verb}|%d|%d",days,fee,{mode},f.Hours[a].TS,f.Hours[b-1].TS);if completed[key] {{continue}}\n '
        text=text.replace(needle,before+needle)
    target=out/(Path(virtual).name+'.txt');target.write_text(text);replace[virtual]=str(target)
(out/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
(out/'receipt.json').write_text(json.dumps(dict(completed_cells=len(rows),
    source_results_sha256=hashlib.sha256(results.read_bytes()).hexdigest(),
    change='Skip only whole completed cells; append remaining results. Same model, prices, fees, Engine and order logic. Temporary state moves to tmpfs to remove disk sync latency.'),indent=2)+'\n')
print('Retained',len(rows),'whole completed cells; remaining cells use identical logic.')
