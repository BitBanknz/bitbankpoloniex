#!/usr/bin/env python3
"""Require complete before/after baseline accounting for protective repairs."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('candidate',type=Path)
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
base=root/'data/frontier_20260912/ledger'
candidate=a.candidate.resolve()
def read(path):return [json.loads(s) for s in path.read_text().splitlines()]
def key(r):return r['Days'],r['Fee'],r['Start'],r['End']
original=[r for r in read(base/'results.jsonl') if r['Bonus']==0]
updated=read(candidate/'results.jsonl')
assert len(original)==20 and len(updated)==20
assert all(r['Bonus']==0 for r in updated)
before={key(r):r for r in original};after={key(r):r for r in updated}
assert len(before)==len(after)==20 and before.keys()==after.keys()
report_differences=[dict(key=k,before=before[k]['Report'],after=after[k]['Report']) for k in before if before[k]['Report']!=after[k]['Report']]
ledger_differences=[]
for fee in [.003,.006]:
    name=f'ledger_fee{fee:g}_bonus0.json'
    x=json.loads((base/name).read_text());y=json.loads((candidate/name).read_text())
    for field in ['Budget','Cash','HighWater','DayStart','Day','OrdersToday','Holdings','Processed','Pending','Halted','Cooldown','Equity']:
        if x.get(field)!=y.get(field):ledger_differences.append(dict(fee=fee,field=field))
    for s in [x,y]:s['Fills'].sort(key=lambda f:(f['At'],f['Order']['clientOrderId']))
    if x['Fills']!=y['Fills']:ledger_differences.append(dict(fee=fee,field='fills_after_same_hour_order_normalization'))
result=dict(status='COMPLETE',rows=20,reports_exact=not report_differences,continuous_accounts_and_equity_paths_exact=not ledger_differences,report_differences=report_differences,ledger_differences=ledger_differences,passes=not report_differences and not ledger_differences,sha256={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [base/'results.jsonl',candidate/'results.jsonl']})
(candidate/'baseline-parity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','rows','reports_exact','continuous_accounts_and_equity_paths_exact','passes']}))
assert result['passes'],'baseline accounting changed; inspect before promotion'
