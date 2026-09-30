"""All registered comparisons; no winner selection or retuning."""
from collections import Counter
from decimal import Decimal as D
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from capture import OUT,sha,save

def read(p):return json.loads(p.read_text())
def difference(a,b):return None if a is None or b is None else str(D(a)-D(b))

def main():
    root=OUT/'audit';verification=read(root/'verification.json');assert verification['verified']
    assert all(sha(root/name)==h for name,h in verification['output_hashes'].items())
    summary=read(root/'summary.json');pairs=[]
    metrics=('last_equity','return_pct','max_drawdown_pct','fees','turnover','dust_value','max_gross_fraction')
    for study in ('unguarded','guarded'):
        for fee in (30,40,60):
            a=summary[study]['quote_aware_fee'+str(fee)];b=summary[study]['control_fee'+str(fee)]
            pairs.append(dict(comparison='quote_aware_minus_control',study=study,fee_bps=fee,
                differences={k:difference(a[k],b[k]) for k in metrics},fill_difference=a['fills']-b['fills'],
                complete_marked_paths=a['complete_marked_path'] and b['complete_marked_path']))
    for name,b in summary['unguarded'].items():
        a=summary['guarded'][name]
        pairs.append(dict(comparison='guarded_minus_unguarded',account=name,
            differences={k:difference(a[k],b[k]) for k in metrics},fill_difference=a['fills']-b['fills'],
            complete_marked_paths=a['complete_marked_path'] and b['complete_marked_path']))
    sources=Counter();signals=Counter()
    for line in (root/'sources.jsonl').open():
        v=json.loads(line);sources[str(v.get('rank_endpoint_status'))]+=1
        signals[json.dumps([v.get('rank_body_available'),v.get('rank_issued_at'),v.get('rank_execution_hour'),v.get('rank_available')])]+=1
    fill_events=[];first_selection_diff={};last={}
    for line in (root/'paths.jsonl').open():
        row=json.loads(line);study=row['study'];aid=row['account'];last[study,aid]=row
        if row['new_fills']:fill_events.append(dict(study=study,account=aid,index=row['index'],now_ns=row['now_ns'],fills=row['new_fills']))
        if aid.startswith('quote_aware_'):
            baseline=last.get((study,aid.replace('quote_aware_','control_')))
            if baseline is not None and baseline['index']==row['index']:
                key=study+'/'+aid
                if key not in first_selection_diff and any(row[k]!=baseline[k] for k in ('cash','equity','new_fills','dust','marks')):first_selection_diff[key]=row['index']
    result=dict(at_ns=time.time_ns(),verification_sha256=sha(root/'verification.json'),summarizer_sha256=sha(Path(__file__)),
        interim_only=True,deployment_qualified=False,comparisons=pairs,rank_endpoint_status_counts=dict(sources),
        rank_payload_clock_counts=dict(signals),first_selection_accounting_difference=first_selection_diff,
        fill_event_batches=len(fill_events),all_accounts=summary)
    save(root/'comparison.json',result);save(root/'fill_events.json',fill_events)
    print(json.dumps(dict(comparisons=pairs,rank_endpoint_status_counts=dict(sources),rank_payload_clock_counts=dict(signals),first_selection_accounting_difference=first_selection_diff,fill_event_batches=len(fill_events))),flush=True)

if __name__=='__main__':main()
