"""Causal native fixtures for protective clock correction, without faster sells."""
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
sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native
sys.path.insert(0,str(REPO/'research/futurecompare20260926'))
from reference import transition

MINUTE=60_000_000_000
HOUR=60*MINUTE
SEED=BASE/'poloniex_quote_aware_v1/stop_refill_probe_v2/stop_refill_0_0.json'

def iso(ns):return datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat().replace('+00:00','Z')
def stamp(value):return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1e9)

def causal(request,state):
    if state is None:return
    now=request['NowNS']
    assert stamp(state['LastCycle'])<=now
    assert all(stamp(mark['At'])<=now for mark in state['Equity'])
    assert all(stamp(position['Entered'])<=now for position in state['Holdings'].values())
    times=[stamp(fill['At']) for fill in state['Fills'] or []]
    assert times==sorted(times) and all(value<=now for value in times)

def fresh(request,now):
    request['NowNS']=now
    for path,response in request['Responses'].items():
        if path.endswith('/orderBook') and response['Status']==200:response['Body']['ts']=now//1_000_000
        if path=='/markets/ticker24h':
            for ticker in response['Body']:ticker['ts']=now//1_000_000

def seed(fee,clock,offset=0):
    request=deepcopy(read(SEED)['input']);now=request['NowNS']+offset
    request['Config'].update(FeeRate=fee,Slots=1,ProtectiveActualHour=clock)
    request['Before']['LastCycle']=iso(now-MINUTE)
    request['Before']['Day']=iso(now)[:10]
    request['Before']['Equity']=[dict(At=iso(now//HOUR*HOUR),Value='495')]
    fresh(request,now);causal(request,request['Before']);return request

def main():
    root=OUT/'regressions';root.mkdir(exist_ok=False)
    fixture=BASE/'poloniex_quote_aware_v1/paired_replay_v2/cycles.jsonl.gz'
    bound={str(p):sha(p) for p in [Path(__file__),SEED,fixture,OUT/'observed/engine.test',OUT/'observed/engine_race.test',
                                 PARENT/'observed/engine.test',REPO/'research/futurecompare20260926/reference.py']}
    save(root/'registration.json',dict(at_ns=time.time_ns(),hashes=bound,all_fixture_clocks_must_be_causal=True))
    temp=Path(tempfile.mkdtemp(prefix='protective-clock-tests-',dir='/dev/shm'))
    prior_tmp=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    candidate=Native(OUT/'observed/engine.test');baseline=Native(PARENT/'observed/engine.test')
    records=[];cases=[]
    output=gzip.open(root/'cycles.jsonl.gz','wt')
    def apply(request,label):
        causal(request,request['Before'])
        answer=candidate.apply(request);causal(request,answer['State'])
        money=transition(request['Before'],answer['State'],request['Config']['FeeRate'],request['Responses'],request['NowNS'],True)
        row=dict(label=label,input=deepcopy(request),output=answer,accounting=money)
        records.append(row);output.write(json.dumps(row,sort_keys=True)+'\n');output.flush()
        return answer,money
    try:
        rows=[json.loads(line) for line in gzip.decompress(fixture.read_bytes()).splitlines()]
        rows=[r for r in rows if not r['input']['Config']['QuoteAwareEntry']]
        old=BASE/'poloniex_stop_topup_guard_v1/regressions'
        rows.extend(read(p) for p in sorted(old.glob('*.json')) if p.name!='verification.json')
        assert len(rows)==30
        for row in rows:
            request=deepcopy(row['input']);request['Config']['ProtectiveActualHour']=False
            actual,_=apply(request,'default_off');expected=baseline.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):assert actual[key]==expected[key]==row['output'][key]
            assert sorted(actual['Paths'])==sorted(expected['Paths'])
        cases.append(dict(name='default_off_full_output',cycles=30))
        for fee in ('.003','.004','.006'):
            for clock in (False,True):
                request=seed(fee,clock,-HOUR);start=request['NowNS'];counts=[]
                for step,offset in enumerate((0,MINUTE,MINUTE+10_000_000_000,4*MINUTE,5*MINUTE,64*MINUTE,124*MINUTE)):
                    fresh(request,start+offset);request['ID']=f'hour_boundary_{fee}_{clock}_{step}'
                    answer,money=apply(request,'hour_boundary_no_extra_minute_sells')
                    counts.append(len(money['new_fills']));request['Before']=answer['State']
                assert counts==([1,0,0,1,0,1,0] if clock else [1,0,0,0,0,1,1]),counts
                assert not answer['State']['Holdings']
                expected_exit=start+(64 if clock else 124)*MINUTE
                assert answer['State']['Cooldown']['AAA_USDT']==iso(expected_exit+120*HOUR)
                cases.append(dict(name='hour_boundary_no_extra_minute_sells',fee=fee,clock=clock,fills=counts))

                request=seed(fee,clock,-HOUR);start=request['NowNS'];prediction=deepcopy(request['Responses']['/prediction']);counts=[]
                for step in range(4):
                    fresh(request,start+step*10_000_000_000);request['ID']=f'forecast_switch_{fee}_{clock}_{step}'
                    request['Responses']['/prediction']=deepcopy(prediction) if step%2==0 else dict(Status=503,Body={})
                    answer,money=apply(request,'forecast_loss_and_recovery');counts.append(len(money['new_fills']));request['Before']=answer['State']
                assert counts==([1,0,0,0] if clock else [1,1,0,0]),counts
                cases.append(dict(name='forecast_loss_and_recovery',fee=fee,clock=clock,fills=counts))

                request=seed(fee,clock);day=request['NowNS']//(24*HOUR)*(24*HOUR)
                start=day+23*HOUR+59*MINUTE
                request['Before']['LastCycle']=iso(start-MINUTE)
                request['Before']['Equity']=[dict(At=iso(start//HOUR*HOUR),Value='495')]
                request['Before']['OrdersToday']=11
                request['Responses']['/prediction']=dict(Status=503,Body={})
                counts=[];orders=[]
                for step,offset in enumerate((0,10_000_000_000,MINUTE,2*MINUTE)):
                    fresh(request,start+offset);request['ID']=f'day_boundary_{fee}_{clock}_{step}'
                    answer,money=apply(request,'day_boundary');counts.append(len(money['new_fills']))
                    orders.append(answer['State']['OrdersToday']);request['Before']=answer['State']
                assert counts==[1,0,1,0] and orders==[12,12,1,1],(counts,orders)
                cases.append(dict(name='day_boundary',fee=fee,clock=clock,fills=counts,orders=orders))

                for name in ('wide','stale','unavailable','day_cap','last_allowance','shallow','risk_halt','other_missing','imported','recovered','ordinary_rotation'):
                    request=seed(fee,clock);start=request['NowNS']
                    if name=='day_cap':request['Before']['OrdersToday']=12
                    if name=='last_allowance':request['Before']['OrdersToday']=11
                    if name=='risk_halt':request['Before']['Halted']='drawdown or daily loss limit; operator review required'
                    if name=='other_missing':
                        request['Before']['Holdings']['BBB_USDT']=dict(Quantity='1',Peak='10',Entered='2026-09-20T00:00:00Z',Imported=False)
                        request['Before']['Cash']='385'
                    if name=='imported':request['Before']['Holdings']['AAA_USDT']['Imported']=True
                    if name=='ordinary_rotation':
                        request['Before']['Holdings']['AAA_USDT']['Peak']='10'
                        request['Responses']['/prediction']['Body']['rank_scores']['AAAUSDT']=-1
                    counts=[]
                    for step in range(2):
                        fresh(request,start+step*MINUTE);request['ID']=f'{name}_{fee}_{clock}_{step}'
                        book=request['Responses']['/markets/AAA_USDT/orderBook']
                        if name=='wide':book['Body']['asks']=['11','1000']
                        if name=='stale':book['Body']['ts']-=60_000
                        if name=='unavailable':book['Status']=503
                        if name=='shallow':book['Body']['bids']=['10','1']
                        if name=='other_missing':request['Responses']['/markets/BBB_USDT/orderBook']=dict(Status=503,Body={})
                        if name=='recovered' and step:
                            book['Body'].update(bids=['11','1000'],asks=['11.01','1000'])
                            request['Responses']['/prediction']=dict(Status=503,Body={})
                        answer,money=apply(request,name);counts.append(len(money['new_fills']))
                        expected=baseline.apply({**request,'Config':{k:v for k,v in request['Config'].items() if k!='ProtectiveActualHour'}})
                        for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==expected[key],(name,key)
                        assert all(f['Order']['side']=='SELL' for f in money['new_fills'])
                        if name=='shallow':assert all(D(f['Quantity'])<=D('.1') for f in money['new_fills'])
                        if name in ('stale','unavailable','other_missing'):assert money['equity'] is None
                        if name=='risk_halt':assert answer['State']['Halted']==request['Before']['Halted']
                        request['Before']=answer['State']
                    assert counts==([0,0] if name in ('wide','stale','unavailable','day_cap') else [1,0]),(name,clock,counts)
                    cases.append(dict(name=name,fee=fee,clock=clock,fills=counts))

        # A fresh process must respect the persisted actual-hour decision key.
        request=seed('.003',True,-HOUR);request['ID']='restart_first'
        first,_=apply(request,'restart');request['Before']=first['State'];request['ID']='restart_duplicate'
        expected,money=apply(request,'restart');assert not money['new_fills']
        restarted=Native(OUT/'observed/engine.test')
        try:
            actual=restarted.apply(request)
            for key in ('ID','State','Report','Paused','CycleError'):assert actual[key]==expected[key]
        finally:restarted.close()
        cases.append(dict(name='restart_duplicate',verified=True))
    finally:
        output.close();candidate.close();baseline.close()
    race=Native(OUT/'observed/engine_race.test')
    try:
        for row in records:
            answer=race.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==row['output'][key]
            assert sorted(answer['Paths'])==sorted(row['output']['Paths'])
    finally:
        race.close()
        if prior_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=prior_tmp
        shutil.rmtree(temp)
    assert all(sha(path)==h for path,h in bound.items())
    save(root/'verification.json',dict(verified=True,at_ns=time.time_ns(),native_money_checks=len(records),native_race_cases=len(records),
        default_off_full_output_cases=30,all_fixture_clocks_causal=True,one_sell_per_actual_hour_verified=True,
        cases=cases,cycles_sha256=sha(root/'cycles.jsonl.gz'),registration_sha256=sha(root/'registration.json'),
        live_changed=False,performance_evidence=False))
    print(json.dumps(dict(verified=True,native_money_checks=len(records),native_race_cases=len(records),cases=len(cases))),flush=True)

if __name__=='__main__':main()
