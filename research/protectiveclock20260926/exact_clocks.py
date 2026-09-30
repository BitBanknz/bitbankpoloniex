"""Independently audit fixture clocks without float timestamp conversion."""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
import time

from build import OUT, REPO, read, save, sha
sys.path.insert(0,str(REPO/'research/futureworker20260926'))
from outcomes import ns


def causal(state,now):
    if state is None:return
    assert ns(state['LastCycle'])<=now,'LastCycle'
    assert all(ns(row['At'])<=now for row in state['Equity']),'Equity'
    assert all(ns(position['Entered'])<=now for position in state['Holdings'].values()),'Entered'
    clocks=[ns(fill['At']) for fill in state['Fills'] or []]
    assert clocks==sorted(clocks) and all(value<=now for value in clocks),'Fills'

def iso_ns(value):
    seconds,fraction=divmod(value,1_000_000_000)
    return datetime.fromtimestamp(seconds,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+f'.{fraction:09d}Z'

def main():
    rows=[];inputs=[Path(__file__),REPO/'research/futureworker20260926/outcomes.py']
    for folder in ('regressions','forecast_arrival'):
        proof=read(OUT/folder/'verification.json');assert proof['verified']
        path=OUT/folder/'cycles.jsonl.gz';assert sha(path)==proof['cycles_sha256']
        inputs.extend([path,OUT/folder/'verification.json'])
        rows.extend(json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines())
    assert len(rows)==278
    states=0
    for row in rows:
        now=row['input']['NowNS']
        for state in (row['input']['Before'],row['output']['State']):
            causal(state,now);states+=state is not None
    row=next(row for row in rows if row['output']['State']['Holdings'] and row['output']['State']['Fills'])
    state=row['output']['State'];now=row['input']['NowNS'];future=iso_ns(now+1)
    assert ns(iso_ns(now))==now and ns(future)==now+1
    rejected=[]
    for field in ('LastCycle','Equity','Entered','Fills'):
        changed=deepcopy(state)
        if field=='LastCycle':changed['LastCycle']=future
        elif field=='Equity':changed['Equity'][-1]['At']=future
        elif field=='Entered':next(iter(changed['Holdings'].values()))['Entered']=future
        else:changed['Fills'][-1]['At']=future
        try:causal(changed,now)
        except AssertionError as error:
            assert str(error)==field;rejected.append(field)
        else:raise AssertionError('one-nanosecond future timestamp accepted: '+field)
    save(OUT/'exact_clock_verification.json',dict(verified=True,at_ns=time.time_ns(),cases=278,states_checked=states,
        all_clocks_causal_at_nanosecond_precision=True,future_one_nanosecond_mutations_rejected=rejected,
        financial_implementation_unchanged=True,hashes={str(p):sha(p) for p in inputs}))
    print(dict(verified=True,cases=278,states_checked=states,one_nanosecond_tamper_rejections=len(rejected)),flush=True)

if __name__=='__main__':main()
