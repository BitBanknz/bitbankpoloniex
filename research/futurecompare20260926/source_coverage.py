"""Full frozen public-source coverage and cross-batch chronology; no accounts."""
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
import gzip
import json
from pathlib import Path
import time
from capture import OUT,HERE,END,sha,save
from audit import Bound,source_protocol,capture,rules

def main():
    output=OUT/'source_coverage';output.mkdir(exist_ok=False)
    inputs=[Path(__file__),HERE/'audit.py',HERE/'capture.py',Path(rules.__file__),OUT/'capture.verified.json']
    hashes={str(p):sha(p) for p in inputs};save(output/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,through_index=END))
    bound=Bound();p=source_protocol(bound);status=json.loads((bound.root/'remote_status.json').read_text())
    previous=None;requests=0;unusable=0;rank_minutes=0;clock_counts=Counter();endpoint_errors=Counter();top_targets=Counter();feasible_targets=Counter();rejections=Counter();window_counts=Counter();last=None
    with (output/'minutes.jsonl').open('x') as log:
      for index in range(38,END+1):
        packet,proof,metadata=capture(bound,index,p,status['complete_ns']);requests+=metadata['requests']
        receipt_name=f'source/minute_{index:05d}.receipt.json';receipt=bound.json(receipt_name) if receipt_name in bound.manifest else None
        if receipt is not None:
            if receipt['first_request_ns'] is not None:
                assert previous is None or receipt['first_request_ns']>=previous,'cross-batch source clock reversal'
            previous=receipt['complete_after_ns'];last=previous
        row=dict(index=index,**metadata)
        if packet is None:
            unusable+=1;row['source_unusable_reason']=proof['reason'];log.write(json.dumps(row,sort_keys=True)+'\n');continue
        now=packet['NowNS'];responses=packet['Responses'];utc=datetime.fromtimestamp(now//1_000_000_000,timezone.utc)
        key=utc.strftime('%Y-%m-%d')
        if utc.hour==1:window_counts[key]+=1
        for endpoint,code in proof['statuses'].items():
            if code!=200:endpoint_errors[str((endpoint,code))]+=1
        clock_counts[json.dumps([metadata.get('rank_endpoint_status'),metadata.get('rank_body_available'),metadata.get('rank_issued_at'),metadata.get('rank_execution_hour'),metadata.get('rank_available')])]+=1
        if metadata['rank_available']:
            rank_minutes+=1;markets={m['symbol']:m for m in responses['/markets']['Body']};tickers={t['symbol']:t for t in responses['/markets/ticker24h']['Body']}
            eligible=[];quotes={}
            for s,score in metadata['rank_scores'].items():
                m=markets.get(s);t=tickers.get(s)
                if not m or not t or m['state']!='NORMAL' or m['quoteCurrencyName']!='USDT' or D(t['amount'])<100000 or not rules.fresh(t['ts'],now,300):continue
                eligible.append(s);r=responses.get('/markets/'+s+'/orderBook',{})
                if r.get('Status')!=200:quotes[s]=dict(quote_feasible=False,reasons=['book_unavailable']);continue
                try:quotes[s]=rules.feasibility(m,t,r['Body'],now)
                except (AssertionError,KeyError,ValueError):quotes[s]=dict(quote_feasible=False,reasons=['invalid_book_or_limits'])
            ordered=sorted(eligible,key=lambda s:(-D(metadata['rank_scores'][s]),s));targets=ordered[:3]
            for s in targets:
                top_targets[s]+=1
                if quotes[s]['quote_feasible']:feasible_targets[s]+=1
                else:rejections.update(quotes[s]['reasons'])
            row.update(rank_targets=targets,hypothetical_flat_quote_aware_targets=[s for s in ordered if quotes[s]['quote_feasible']][:3],quote_checks=quotes,account_gates_checked=False)
        log.write(json.dumps(row,sort_keys=True)+'\n')
        if index%500==0:print(json.dumps(dict(source_index=index,valid_forecast_minutes=rank_minutes)),flush=True)
    assert all(sha(path)==h for path,h in hashes.items())
    result=dict(at_ns=time.time_ns(),verified=True,first_index=38,through_index=END,source_requests=requests,source_batches=END-38+1,
        unusable_source_batches=unusable,cross_batch_receipt_chronology_verified=True,last_source_complete_ns=last,
        observed_execution_window_minutes=dict(window_counts),valid_forecast_minutes=rank_minutes,rank_payload_clock_counts=dict(clock_counts),
        non_200_endpoints=dict(endpoint_errors),rank_target_counts=dict(top_targets),feasible_rank_target_counts=dict(feasible_targets),
        rank_target_rejections=dict(rejections),performance_evidence=False,hashes=hashes,minutes_sha256=sha(output/'minutes.jsonl'))
    save(output/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='hashes'}),flush=True)

if __name__=='__main__':main()
