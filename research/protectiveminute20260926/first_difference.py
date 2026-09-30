"""Explain the first economic divergence; do not attribute the whole PnL change."""
from collections import Counter
from decimal import Decimal as D
import hashlib
from pathlib import Path
import time

from build import OUT, read, save, sha
from account_reference import stamp
from attribution import economic_fills


def decision_keys(state):
    return {'bbp-'+hashlib.sha256(('paper|'+key).encode()).hexdigest()[:40]:key for key in state['Processed']}

def main():
    root=OUT/'historical_accounts';proof=read(root/'verification.json');assert proof['verified']
    assert sha(root/'accounts.json')==proof['accounts_sha256']
    result=[]
    for pair in read(root/'accounts.json'):
        states={}
        for arm,binding in pair['bindings'].items():
            assert sha(binding['path'])==binding['sha256'];states[arm]=read(binding['path'])
        a,b=(states[arm] for arm in ('control','repeat'))
        left,right=economic_fills(a),economic_fills(b)
        if left==right:continue
        index=next((i for i,(x,y) in enumerate(zip(left,right)) if x!=y),min(len(left),len(right)))
        assert index>0 and index<len(left) and index<len(right)
        prior=a['Fills'][index-1];first=b['Fills'][index]
        control_keys=decision_keys(a);repeat_keys=decision_keys(b)
        prior_key=control_keys[prior['Order']['clientOrderId']]
        first_key=repeat_keys[first['Order']['clientOrderId']]
        key_hour=stamp(prior_key.split('|')[0]);prior_hour=stamp(prior['At'])//3600*3600
        first_hour=stamp(first['At'])//3600*3600
        assert prior['Order']['side']==first['Order']['side']=='SELL'
        assert prior['Order']['symbol']==first['Order']['symbol']
        assert key_hour==prior_hour+3600==first_hour
        assert first_key.startswith(prior_key+'|protective-minute-')
        assert sum(f['Order']['symbol']==first['Order']['symbol'] and f['Order']['side']=='SELL' and stamp(f['At'])//3600*3600==first_hour for f in a['Fills'])==0
        result.append(dict(case=pair['case'],start=pair['start'],first_different_fill_index=index,
                           shared_prior_sell=prior,shared_prior_control_key=prior_key,
                           first_candidate_different_fill=first,first_candidate_key=first_key,
                           first_control_different_fill=a['Fills'][index],
                           initial_divergence_is_future_forecast_hour_key_collision=True,
                           full_return_change_not_isolated_to_this_cause=True))
    assert len(result)==12
    episodes=Counter((r['shared_prior_sell']['At'],r['shared_prior_sell']['Order']['symbol']) for r in result)
    save(root/'first_difference.json',dict(verified=True,at_ns=time.time_ns(),changed_accounts=12,
        unique_initial_event_times_and_symbols=len(episodes),
        initial_events=[dict(at=key[0],symbol=key[1],account_comparisons=count) for key,count in sorted(episodes.items())],
        rows=result,diagnostic_after_outcomes=True,does_not_isolate_total_treatment_effect=True,
        hashes={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('attribution.py'),root/'verification.json',root/'accounts.json']}))
    print({'verified':True,'changed_accounts':12,'unique_initial_events':len(episodes)},flush=True)


if __name__=='__main__':main()
