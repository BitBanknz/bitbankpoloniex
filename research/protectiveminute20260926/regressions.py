"""Native behavior and Decimal accounting checks; synthetic paths are not alpha."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal as D
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

from build import BASE, HERE, OUT, PARENT, REPO, read, save, sha
sys.path.insert(0, str(REPO/'research/quoteaware20260924'))
from native import Native
sys.path.insert(0, str(REPO/'research/futurecompare20260926'))
from reference import transition

MINUTE = 60_000_000_000
SEED = BASE/'poloniex_quote_aware_v1/stop_refill_probe_v2/stop_refill_0_0.json'

def iso(ns):
    return datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat().replace('+00:00','Z')

def fresh(request, now):
    request['NowNS']=now
    for path,response in request['Responses'].items():
        if path.endswith('/orderBook') and response['Status']==200:
            response['Body']['ts']=now//1_000_000
        if path=='/markets/ticker24h':
            for ticker in response['Body']:ticker['ts']=now//1_000_000

def seed(fee,repeat):
    request=deepcopy(read(SEED)['input'])
    request['Config'].update(FeeRate=fee,Slots=1,RepeatProtectiveMinute=repeat)
    request['Before']['LastCycle']=iso(request['NowNS']-MINUTE)
    return request

def main():
    folder=OUT/'regressions';folder.mkdir(exist_ok=False)
    assert read(OUT/'observed/verification.json')['verified']
    fixture=BASE/'poloniex_quote_aware_v1/paired_replay_v2/cycles.jsonl.gz'
    bound={str(p):sha(p) for p in [Path(__file__),SEED,fixture,OUT/'observed/engine.test',
                                 OUT/'observed/engine_race.test',PARENT/'observed/engine.test',
                                 REPO/'research/futurecompare20260926/reference.py']}
    save(folder/'registration.json',dict(at_ns=time.time_ns(),hashes=bound))
    temp=Path(tempfile.mkdtemp(prefix='protective-minute-tests-',dir='/dev/shm'))
    previous_tmp=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    candidate=Native(OUT/'observed/engine.test');baseline=Native(PARENT/'observed/engine.test')
    records=[];race_inputs=[];cases=[]
    def apply(worker,request,label):
        answer=worker.apply(request)
        accounting=transition(request['Before'],answer['State'],request['Config']['FeeRate'],request['Responses'],request['NowNS'],True)
        records.append(dict(label=label,input=deepcopy(request),output=answer,accounting=accounting))
        if worker is candidate:race_inputs.append((deepcopy(request),answer))
        return answer,accounting
    try:
        original=[json.loads(line) for line in gzip.decompress(fixture.read_bytes()).splitlines()]
        original=[row for row in original if not row['input']['Config']['QuoteAwareEntry']]
        guard=BASE/'poloniex_stop_topup_guard_v1/regressions'
        original.extend(read(p) for p in sorted(guard.glob('*.json')) if p.name!='verification.json')
        assert len(original)==30
        for row in original:
            request=deepcopy(row['input']);request['Config']['RepeatProtectiveMinute']=False
            answer,_=apply(candidate,request,'default_off')
            expected=baseline.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):
                assert answer[key]==expected[key]==row['output'][key],(request['ID'],key)
            assert sorted(answer['Paths'])==sorted(expected['Paths'])
        cases.append(dict(name='default_off',cycles=30))

        for fee in ('.003','.004','.006'):
            for repeat in (False,True):
                request=seed(fee,repeat);start=request['NowNS'];counts=[];last=None
                for step,offset in enumerate((0,0,20_000_000_000,MINUTE,2*MINUTE)):
                    fresh(request,start+offset);request['ID']=f'duplicate_{fee}_{repeat}_{step}'
                    answer,money=apply(candidate,request,'duplicate_and_complete_exit')
                    counts.append(len(money['new_fills']));request['Before']=answer['State'];last=answer
                assert counts==([1,0,0,1,1] if repeat else [1,0,0,0,0]),counts
                if repeat:
                    assert not last['State']['Holdings']
                    assert last['State']['Cooldown']['AAA_USDT']==iso(start+2*MINUTE+120*3600*1_000_000_000)
                else:assert last['State']['Holdings']['AAA_USDT']['Quantity']=='5.1'
                cases.append(dict(name='duplicate_and_complete_exit',fee=fee,repeat=repeat,fills=counts))

                for name in ('wide','stale','unavailable','day_cap','last_allowance','shallow','risk_halt','other_missing','imported','recovered'):
                    request=seed(fee,repeat);start=request['NowNS']
                    if name=='day_cap':request['Before']['OrdersToday']=12
                    if name=='last_allowance':request['Before']['OrdersToday']=11
                    if name=='risk_halt':request['Before']['Halted']='drawdown or daily loss limit; operator review required'
                    if name=='other_missing':
                        request['Before']['Holdings']['BBB_USDT']=dict(Quantity='1',Peak='10',Entered='2026-09-20T00:00:00Z',Imported=False)
                        request['Before']['Cash']='385'
                    if name=='imported':request['Before']['Holdings']['AAA_USDT']['Imported']=True
                    counts=[]
                    for step in range(2):
                        fresh(request,start+step*MINUTE);request['ID']=f'{name}_{fee}_{repeat}_{step}'
                        book=request['Responses']['/markets/AAA_USDT/orderBook']
                        if name=='wide':book['Body']['asks']=['11','1000']
                        if name=='stale':book['Body']['ts']-=60_000
                        if name=='unavailable':book['Status']=503
                        if name=='shallow':book['Body']['bids']=['10','1']
                        if name=='other_missing':request['Responses']['/markets/BBB_USDT/orderBook']=dict(Status=503,Body={})
                        if name=='recovered' and step:
                            book['Body'].update(bids=['11','1000'],asks=['11.01','1000'])
                            request['Responses']['/prediction']=dict(Status=503,Body={})
                        answer,money=apply(candidate,request,name);counts.append(len(money['new_fills']))
                        assert all(f['Order']['side']=='SELL' for f in money['new_fills'])
                        if name=='shallow':assert all(D(f['Quantity'])<=D('.1') for f in money['new_fills'])
                        if name=='risk_halt':assert answer['State']['Halted']==request['Before']['Halted']
                        if name in ('stale','unavailable','other_missing'):assert money['equity'] is None
                        request['Before']=answer['State']
                    expected=([0,0] if name in ('wide','stale','unavailable','day_cap') else
                              [1,0] if name in ('last_allowance','imported','recovered') or not repeat else [1,1])
                    assert counts==expected,(name,repeat,counts,expected)
                    cases.append(dict(name=name,fee=fee,repeat=repeat,fills=counts))

                # Prediction sets decisionHour=01:00 even before execution;
                # losing it in the same 00:56 minute must not create a second
                # protective decision in the treatment.
                request=seed(fee,repeat);start=request['NowNS']-3600*1_000_000_000
                counts=[]
                for step in range(2):
                    fresh(request,start+step*10_000_000_000);request['ID']=f'forecast_clock_{fee}_{repeat}_{step}'
                    if step:request['Responses']['/prediction']=dict(Status=503,Body={})
                    answer,money=apply(candidate,request,'forecast_clock_change');counts.append(len(money['new_fills']))
                    request['Before']=answer['State']
                assert counts==([1,0] if repeat else [1,1]),counts
                cases.append(dict(name='forecast_clock_change',fee=fee,repeat=repeat,fills=counts))

        synthetic=[]
        for name,prices in [('falling',('10','9','8','7')),('rebounding',('10','10','12','13'))]:
            for fee in ('.003','.004','.006'):
                for repeat in (False,True):
                    request=seed(fee,repeat);request['Responses']['/prediction']=dict(Status=503,Body={})
                    start=request['NowNS'];curve=[];fees=D(0);fills=0
                    for step,bid in enumerate(prices):
                        fresh(request,start+step*MINUTE);request['ID']=f'{name}_{fee}_{repeat}_{step}'
                        request['Responses']['/markets/AAA_USDT/orderBook']['Body'].update(bids=[bid,'1000'],asks=[str(D(bid)+D('.01')),'1000'])
                        answer,money=apply(candidate,request,'synthetic_'+name)
                        curve.append(money['equity']);fees+=D(money['fees']);fills+=len(money['new_fills']);request['Before']=answer['State']
                    synthetic.append(dict(path=name,fee=fee,repeat=repeat,post_cycle_equity=curve,fees=str(fees),fills=fills,
                                          holdings=answer['State']['Holdings'],performance_evidence=False))
    finally:
        candidate.close();baseline.close()
    race=Native(OUT/'observed/engine_race.test')
    try:
        for request,expected in race_inputs:
            answer=race.apply(request)
            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==expected[key]
            assert sorted(answer['Paths'])==sorted(expected['Paths'])
    finally:
        race.close()
        if previous_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=previous_tmp
        shutil.rmtree(temp)
    with gzip.open(folder/'cycles.jsonl.gz','wt') as f:
        for record in records:f.write(json.dumps(record,sort_keys=True)+'\n')
    assert all(sha(path)==h for path,h in bound.items())
    save(folder/'verification.json',dict(verified=True,at_ns=time.time_ns(),default_off_cycles=30,
        native_money_checks=len(records),native_race_cycles=len(race_inputs),cases=cases,synthetic=synthetic,
        registration_sha256=sha(folder/'registration.json'),cycles_sha256=sha(folder/'cycles.jsonl.gz'),
        live_changed=False,profitability_established=False))
    print(json.dumps(dict(verified=True,native_money_checks=len(records),native_race_cycles=len(race_inputs),cases=len(cases))),flush=True)

if __name__=='__main__':main()
