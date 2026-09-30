"""Read-only forecast-window/quote coverage, never substitutes for account replay."""
from collections import Counter
from decimal import Decimal as D
import gzip
import json
from pathlib import Path
import sys
import time
from capture import OUT,sha,save
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'quoteaware20260924'))
import receipt_rules as rules

def main():
    root=OUT/'audit';v=json.loads((root/'verification.json').read_text());assert v['verified']
    assert sha(root/'sources.jsonl')==v['output_hashes']['sources.jsonl']
    manifest=json.loads((OUT/'mirror/manifest.json').read_text());rows=[];reasons=Counter();targets=Counter();feasible=Counter()
    for line in (root/'sources.jsonl').open():
        source=json.loads(line)
        if not source.get('rank_available'):continue
        name=f"unguarded/batch_{source['index']:05d}.input.json.gz";path=OUT/'mirror'/name
        assert sha(path)==manifest[name]['sha256'];packet=json.loads(gzip.decompress(path.read_bytes()))['packet']
        now=packet['NowNS'];responses=packet['Responses'];markets={m['symbol']:m for m in responses['/markets']['Body']}
        tickers={t['symbol']:t for t in responses['/markets/ticker24h']['Body']};eligible=[];quotes={}
        for symbol,value in source['rank_scores'].items():
            m=markets.get(symbol);t=tickers.get(symbol)
            if not m or not t:continue
            if m['state']!='NORMAL' or m['quoteCurrencyName']!='USDT' or D(t['amount'])<100000 or not rules.fresh(t['ts'],now,300):continue
            eligible.append(symbol);response=responses.get('/markets/'+symbol+'/orderBook',{})
            if response.get('Status')!=200:quotes[symbol]=dict(quote_feasible=False,reasons=['book_unavailable']);continue
            try:quotes[symbol]=rules.feasibility(m,t,response['Body'],now)
            except (AssertionError,KeyError,ValueError):quotes[symbol]=dict(quote_feasible=False,reasons=['invalid_book_or_limits'])
        ordered=sorted(eligible,key=lambda s:(-D(source['rank_scores'][s]),s));top=ordered[:3]
        alternative=[s for s in ordered if quotes[s]['quote_feasible']][:3]
        for s in top:
            targets[s]+=1
            if quotes[s]['quote_feasible']:feasible[s]+=1
            else:reasons.update(quotes[s]['reasons'])
        rows.append(dict(index=source['index'],rank_targets=top,hypothetical_flat_quote_aware_targets=alternative,quote_checks=quotes,
            account_gates_checked=False,assumed_spend_usdt='49'))
    result=dict(at_ns=time.time_ns(),verified_source_audit_sha256=sha(root/'verification.json'),diagnostic_sha256=sha(Path(__file__)),
        valid_forecast_minutes=len(rows),rank_target_counts=dict(targets),feasible_rank_target_counts=dict(feasible),
        rank_target_rejection_counts=dict(reasons),flat_selection_different_minutes=sum(x['rank_targets']!=x['hypothetical_flat_quote_aware_targets'] for x in rows),
        account_gates_checked=False,performance_evidence=False,rows=rows)
    save(root/'signal_quote_diagnostic.json',result)
    print(json.dumps({k:x for k,x in result.items() if k!='rows'}),flush=True)

if __name__=='__main__':main()
