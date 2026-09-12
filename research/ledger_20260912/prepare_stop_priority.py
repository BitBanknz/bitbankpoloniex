#!/usr/bin/env python3
"""Replay the repaired exit priority against every original baseline cell."""
import argparse
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,default=root/'data/frontier_20260912/stop-priority')
a=p.parse_args()
out=a.out.resolve()/'overlay'
out.mkdir(parents=True,exist_ok=False)
original=json.loads((root/'data/frontier_20260912/ledger/overlay.json').read_text())
replace={}
for virtual,actual in original['Replace'].items():
    source=Path(actual)
    text=source.read_text()
    if virtual.endswith('/engine.go'):
        text=(root/'internal/bot/engine.go').read_text().replace('time.Now()','replayNow()')
    if virtual.endswith('frozen_ledger_research_test.go'):
        assert text.count('[]float64{0,.4}')==1
        text=text.replace('[]float64{0,.4}','[]float64{0}')
    target=out/(Path(virtual).name+'.txt')
    target.write_text(text)
    replace[virtual]=str(target)
(out.parent/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
(out.parent/'source-hashes.json').write_text(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'internal/bot/engine.go',root/'internal/bot/stop_priority_test.go',root/'internal/bot/partial_books_test.go',*out.glob('*.txt')]},indent=2)+'\n')
