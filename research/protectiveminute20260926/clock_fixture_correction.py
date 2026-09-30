"""Correct the seed chronology of the twelve forecast-clock test executions.

The original fixture moved NowNS back an hour without moving the prior state's
LastCycle/equity mark. Retain it as a failed fixture, then use a causal seed.
The trading rule, expected sell counts, money checks, and tolerances are unchanged.
"""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from build import OUT, read, save, sha
from regressions import MINUTE, Native, fresh, iso, seed, transition


def stamp(value):
    return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1e9)

def causal(request):
    now=request['NowNS'];before=request['Before']
    assert stamp(before['LastCycle'])<=now, 'prior cycle is in the future'
    assert all(stamp(mark['At'])<=now for mark in before['Equity']), 'prior equity mark is in the future'
    assert all(stamp(p['Entered'])<=now for p in before['Holdings'].values())


def main():
    folder=OUT/'clock_fixture_correction';folder.mkdir(exist_ok=False)
    old=read(OUT/'regressions/verification.json');assert old['verified']
    assert sha(OUT/'regressions/cycles.jsonl.gz')==old['cycles_sha256']
    rows=[json.loads(line) for line in gzip.decompress((OUT/'regressions/cycles.jsonl.gz').read_bytes()).splitlines()]
    superseded=[row for row in rows if row['label']=='forecast_clock_change']
    assert len(superseded)==12
    rejected=0
    for row in superseded:
        try:causal(row['input'])
        except AssertionError:rejected+=1
    assert rejected==12
    hashes={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('regressions.py'),
                                   OUT/'regressions/verification.json',OUT/'observed/engine.test',OUT/'observed/engine_race.test']}
    save(folder/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,prior_clock_inputs_rejected=rejected,
                                       expected_counts_unchanged=True,financial_tolerances_unchanged=True))
    tmp=Path(tempfile.mkdtemp(prefix='protective-clock-',dir='/dev/shm'))
    previous=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(tmp)
    native=Native(OUT/'observed/engine.test');corrected=[];cases=[]
    try:
        for fee in ('.003','.004','.006'):
            for repeat in (False,True):
                request=seed(fee,repeat);start=request['NowNS']-3600*1_000_000_000
                request['Before']['LastCycle']=iso(start-MINUTE)
                request['Before']['Equity']=[dict(At=iso(start//(3600*1_000_000_000)*(3600*1_000_000_000)),Value='495')]
                counts=[]
                for step in range(2):
                    fresh(request,start+step*10_000_000_000);request['ID']=f'causal_clock_{fee}_{repeat}_{step}'
                    if step:request['Responses']['/prediction']=dict(Status=503,Body={})
                    causal(request)
                    answer=native.apply(request)
                    money=transition(request['Before'],answer['State'],fee,request['Responses'],request['NowNS'],True)
                    causal({**request,'Before':answer['State']})
                    corrected.append(dict(input=deepcopy(request),output=answer,accounting=money))
                    counts.append(len(money['new_fills']));request['Before']=answer['State']
                assert counts==([1,0] if repeat else [1,1]),counts
                cases.append(dict(fee=fee,repeat=repeat,new_fill_counts=counts))
    finally:native.close()
    race=Native(OUT/'observed/engine_race.test')
    try:
        for row in corrected:
            answer=race.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==row['output'][key]
            assert sorted(answer['Paths'])==sorted(row['output']['Paths'])
    finally:
        race.close()
        if previous is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=previous
        shutil.rmtree(tmp)
    save(folder/'cycles.json',corrected)
    assert all(sha(path)==h for path,h in hashes.items())
    save(folder/'verification.json',dict(verified=True,at_ns=time.time_ns(),superseded_invalid_clock_executions=12,
        corrected_native_money_checks=12,corrected_native_race_checks=12,all_state_clocks_causal=True,
        cases=cases,cycles_sha256=sha(folder/'cycles.json'),registration_sha256=sha(folder/'registration.json'),
        trading_implementation_unchanged=True,financial_expectations_unchanged=True,live_changed=False))
    print(json.dumps(dict(verified=True,corrected_clock_cases=12,all_state_clocks_causal=True)),flush=True)


if __name__=='__main__':main()
