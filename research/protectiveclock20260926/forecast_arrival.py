"""Causal unavailable-to-available forecast transition before execution time."""
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from build import OUT, read, save, sha
from regressions import HOUR, MINUTE, Native, causal, fresh, iso, seed, transition


def main():
    root=OUT/'forecast_arrival';root.mkdir(exist_ok=False)
    assert read(OUT/'regressions/verification.json')['verified']
    paths=[Path(__file__),Path(__file__).with_name('regressions.py'),OUT/'regressions/verification.json',
           OUT/'observed/engine.test',OUT/'observed/engine_race.test']
    hashes={str(p):sha(p) for p in paths}
    save(root/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,synthetic_only=True,
        rationale='Source study showed unavailable early minutes followed by a published but not yet executable forecast. Test the reverse transition as well as forecast loss.',
        modeled_times=['00:04:45','00:05:15','00:05:45','01:00:15']))
    temp=Path(tempfile.mkdtemp(prefix='protective-clock-arrival-',dir='/dev/shm'))
    prior=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    native=Native(OUT/'observed/engine.test');records=[];cases=[]
    try:
        for fee in ('.003','.004','.006'):
            for clock in (False,True):
                request=seed(fee,clock);start=request['NowNS']//(24*HOUR)*(24*HOUR)+4*MINUTE+45_000_000_000
                request['Before']['LastCycle']=iso(start-MINUTE)
                request['Before']['Equity']=[dict(At=iso(start//HOUR*HOUR),Value='495')]
                prediction=deepcopy(request['Responses']['/prediction']);counts=[]
                for i,offset in enumerate((0,30_000_000_000,60_000_000_000,55*MINUTE+30_000_000_000)):
                    fresh(request,start+offset);request['ID']=f'arrival_{fee}_{clock}_{i}'
                    request['Responses']['/prediction']=dict(Status=503,Body={}) if i==0 else deepcopy(prediction)
                    causal(request,request['Before']);answer=native.apply(request);causal(request,answer['State'])
                    money=transition(request['Before'],answer['State'],fee,request['Responses'],request['NowNS'],True)
                    records.append(dict(input=deepcopy(request),output=answer,accounting=money))
                    counts.append(len(money['new_fills']));request['Before']=answer['State']
                assert counts==([1,0,0,1] if clock else [1,1,0,0]),counts
                cases.append(dict(fee=fee,clock=clock,fills=counts))
    finally:native.close()
    race=Native(OUT/'observed/engine_race.test')
    try:
        for row in records:
            result=race.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):assert result[key]==row['output'][key]
            assert sorted(result['Paths'])==sorted(row['output']['Paths'])
    finally:
        race.close()
        if prior is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=prior
        shutil.rmtree(temp)
    assert len(records)==24 and all(sha(path)==h for path,h in hashes.items())
    with gzip.open(root/'cycles.jsonl.gz','wt') as f:
        for row in records:f.write(json.dumps(row,sort_keys=True)+'\n')
    save(root/'verification.json',dict(verified=True,at_ns=time.time_ns(),native_money_checks=24,native_race_cases=24,
        cases=cases,all_fixture_clocks_causal=True,synthetic_only=True,performance_evidence=False,
        registration_sha256=sha(root/'registration.json'),cycles_sha256=sha(root/'cycles.jsonl.gz')))
    print(dict(verified=True,native_money_checks=24,native_race_cases=24),flush=True)


if __name__=='__main__':main()
