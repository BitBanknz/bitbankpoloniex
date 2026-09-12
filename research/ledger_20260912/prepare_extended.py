#!/usr/bin/env python3
"""Prepare 56/84-day confirmations only after the fixed initial gates pass."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('study', choices=['ledger','ledger_dust'])
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
source=root/'data/frontier_20260912'/a.study
report=json.loads((source/'comparison.json').read_text())
assert report['status']=='COMPLETE' and report['qualifies_for_further_research'], 'initial progression gate has not passed'
original=json.loads((source/'overlay.json').read_text())
out=source.with_name(a.study+'_extended')/'overlay'
out.mkdir(parents=True,exist_ok=False)
replace={}
for virtual,actual in original['Replace'].items():
    text=Path(actual).read_text()
    if virtual.endswith('frozen_ledger_research_test.go'):
        assert text.count('[]int{0,28}')==1
        text=text.replace('[]int{0,28}','[]int{56,84}')
    target=out/(Path(virtual).name+'.txt')
    target.write_text(text)
    replace[virtual]=str(target)
(out.parent/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
(out.parent/'progression.json').write_text(json.dumps(dict(source_comparison=str(source/'comparison.json'),
    sha256=hashlib.sha256((source/'comparison.json').read_bytes()).hexdigest(),
    geometries_days=[56,84],tmpdir='RAM-backed ephemeral state; actual Engine/Save/Load and order logic unchanged'),indent=2)+'\n')
print(out.parent)
