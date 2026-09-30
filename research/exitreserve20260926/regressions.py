"""Three-arm native money/clock witnesses, each repeated with the race build."""
from copy import deepcopy
from decimal import Decimal as D
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from build import BASE,HERE,OUT,PARENT,REPO,ARMS,read,save,sha
from checks import causal,daily_budget,fresh,iso,ns,MINUTE,HOUR,DAY
sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native
sys.path.insert(0,str(REPO/'research/futurecompare20260926'))
from reference import transition

SEED=BASE/'poloniex_quote_aware_v1/stop_refill_probe_v2/stop_refill_0_0.json'


def initial(fee,arm):
    request=deepcopy(read(SEED)['input'])
    maximum,reserve=ARMS[arm]
    request['Config'].update(FeeRate=fee,MaxOrdersDay=maximum,ExitOrderReserve=reserve)
    request['Config'].pop('QuoteAwareEntry',None)
    request['Before']=None
    fresh(request,ns('2026-09-24T01:00:45Z'),True)
    for path,response in request['Responses'].items():
        if path.endswith('/orderBook'):response['Body']['asks']=['10.01','8']
    return request


def stop(request,now,bid='8.9',ask='8.91',depth='1000'):
    fresh(request,now)
    request['Responses']['/prediction']=dict(Status=503,Body={})
    for path,response in request['Responses'].items():
        if path.endswith('/orderBook'):
            response['Status']=200
            response['Body'].update(bids=[bid,depth],asks=[ask,'1000'],ts=now//1_000_000)


def main():
    root=OUT/'regressions';root.mkdir(exist_ok=False)
    paths=[Path(__file__),HERE/'checks.py',SEED,OUT/'observed/engine.test',OUT/'observed/engine_race.test',
           PARENT/'observed/engine.test',REPO/'research/futurecompare20260926/reference.py',
           REPO/'research/futureworker20260926/outcomes.py']
    fixture=BASE/'poloniex_quote_aware_v1/paired_replay_v2/cycles.jsonl.gz';paths.append(fixture)
    hashes={str(p):sha(p) for p in paths}
    save(root/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,arms=ARMS))
    temp=Path(tempfile.mkdtemp(prefix='exit-reserve-regressions-',dir='/dev/shm'))
    old_tmp=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    native=Native(OUT/'observed/engine.test');baseline=Native(PARENT/'observed/engine.test')
    records=[];examples=[];buy_states={};stream=gzip.open(root/'cycles.jsonl.gz','wt')

    def apply(request,label):
        causal(request['Before'],request['NowNS'])
        answer=native.apply(request);causal(answer['State'],request['NowNS'])
        money=transition(request['Before'],answer['State'],request['Config']['FeeRate'],request['Responses'],request['NowNS'],True)
        budget=daily_budget(request['Before'],answer['State'],request['Config'],request['NowNS'])
        row=dict(label=label,input=deepcopy(request),output=answer,accounting=money,budget=budget)
        records.append(row);stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush()
        return answer,money

    try:
        old_rows=[json.loads(line) for line in gzip.decompress(fixture.read_bytes()).splitlines()]
        old_rows=[r for r in old_rows if not r['input']['Config']['QuoteAwareEntry']]
        prior=BASE/'poloniex_stop_topup_guard_v1/regressions'
        old_rows.extend(read(p) for p in sorted(prior.glob('*.json')) if p.name!='verification.json')
        assert len(old_rows)==30
        for i,row in enumerate(old_rows):
            request=deepcopy(row['input']);request['Config']['ExitOrderReserve']=0
            answer,_=apply(request,'default_off')
            expected=baseline.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==expected[key]==row['output'][key]
            assert sorted(answer['Paths'])==sorted(expected['Paths'])
        for fee in ('.003','.004','.006'):
            states={}
            for arm in ARMS:
                request=initial(fee,arm);start=request['NowNS'];counts=[]
                for step in range(5):
                    fresh(request,start+step*MINUTE);request['ID']=f'buys_{fee}_{arm}_{step}'
                    answer,money=apply(request,'shallow_buys');counts.append(len(money['new_fills']))
                    request['Before']=answer['State']
                assert counts==([3,3,3,3,0] if arm=='baseline' else [3,3,3,0,0]),(arm,counts)
                states[arm]=deepcopy(answer['State']);buy_states[fee,arm]=deepcopy(answer['State'])
                examples.append(dict(name='shallow_buys',fee=fee,arm=arm,new_fills=counts))
            assert states['cap9']==states['reserve3']
            for arm in ARMS:
                request=initial(fee,arm);start=request['NowNS'];request['Before']=deepcopy(states[arm])
                stop(request,start+HOUR);request['ID']=f'stops_{fee}_{arm}'
                answer,money=apply(request,'reserved_protective_exits')
                assert len(money['new_fills'])==(3 if arm=='reserve3' else 0)
                assert all(f['Order']['side']=='SELL' for f in money['new_fills'])
                if arm=='reserve3':
                    assert not answer['State']['Holdings'] and answer['State']['OrdersToday']==12
                    assert all(ns(v)==request['NowNS']+120*HOUR for v in answer['State']['Cooldown'].values())
                saved=deepcopy(answer['State'])
                request['Before']=saved;request['ID']=f'duplicate_{fee}_{arm}'
                duplicate,dm=apply(request,'duplicate_cycle');assert not dm['new_fills']
                assert duplicate['State']==saved
                for name,bid,ask in [('falling','7','7.01'),('rebounding','11','11.01')]:
                    request['Before']=deepcopy(saved);stop(request,start+2*HOUR,bid,ask);request['ID']=f'{name}_{fee}_{arm}'
                    answer,money=apply(request,name)
                    assert not money['new_fills']
                    examples.append(dict(name=name,fee=fee,arm=arm,equity=money['equity']))
            for arm in ARMS:
                request=initial(fee,arm);start=request['NowNS'];request['Before']=deepcopy(states[arm]);counts=[]
                for step in range(5):
                    fresh(request,start+DAY+step*MINUTE,True);request['ID']=f'day_reset_{fee}_{arm}_{step}'
                    answer,money=apply(request,'day_reset');counts.append(len(money['new_fills']));request['Before']=answer['State']
                assert sum(counts)==(12 if arm=='baseline' else 9),(arm,counts)
                assert answer['State']['OrdersToday']==sum(counts)
            for arm in ARMS:
                for name in ('wide','stale','missing','shallow','halted','total_cap','one_allowance','imported','ordinary'):
                    request=initial(fee,arm);start=request['NowNS'];request['Before']=deepcopy(states[arm])
                    stop(request,start+HOUR);request['ID']=f'{name}_{fee}_{arm}'
                    if name=='wide':
                        for path,r in request['Responses'].items():
                            if path.endswith('/orderBook'):r['Body']['asks']=['10','1000']
                    if name in ('stale','missing','shallow'):
                        for path,r in request['Responses'].items():
                            if path.endswith('/orderBook'):
                                if name=='stale':r['Body']['ts']-=60_000
                                elif name=='missing':r['Status']=503
                                else:r['Body']['bids']=['8.9','5']
                    if name=='halted':request['Before']['Halted']='drawdown or daily loss limit; operator review required'
                    if name=='total_cap':request['Before']['OrdersToday']=ARMS[arm][0]
                    if name=='one_allowance':request['Before']['OrdersToday']=ARMS[arm][0]-1
                    if name=='imported':
                        for p in request['Before']['Holdings'].values():p['Imported']=True
                    if name=='ordinary':
                        request['Responses']=deepcopy(initial(fee,arm)['Responses'])
                        fresh(request,start+5*MINUTE,True)
                        request['Responses']['/prediction']['Body']['rank_scores']['AAAUSDT']=-1
                        for p in request['Before']['Holdings'].values():p['Entered']=iso(start-4*DAY)
                    answer,money=apply(request,name)
                    expected=(1 if name=='one_allowance' else
                              0 if arm!='reserve3' or name in ('wide','stale','missing','total_cap') else
                              1 if name=='ordinary' else 3)
                    assert len(money['new_fills'])==expected,(name,arm,len(money['new_fills']),expected)
                    assert all(f['Order']['side']=='SELL' for f in money['new_fills'])
                    if name in ('stale','missing'):assert money['equity'] is None
                    if name=='shallow':assert all(D(f['Quantity'])<=D('.5') for f in money['new_fills'])
                    if name=='halted':assert answer['State']['Halted']==request['Before']['Halted']
                request=initial(fee,arm);start=request['NowNS']
                for path,r in request['Responses'].items():
                    if path.endswith('/orderBook'):r['Body']['asks']=['20','8']
                request['ID']=f'failed_buys_{fee}_{arm}'
                answer,money=apply(request,'failed_buys');assert not money['new_fills'] and answer['State']['OrdersToday']==0
                request=initial(fee,arm);request['Before']=answer['State'];fresh(request,start+MINUTE)
                request['ID']=f'recovered_buys_{fee}_{arm}'
                answer,money=apply(request,'recovered_buys');assert len(money['new_fills'])==3 and answer['State']['OrdersToday']==3
        request=initial('.003','reserve3');request['Before']=deepcopy(buy_states['.003','reserve3'])
        fresh(request,request['NowNS']+5*MINUTE);request['ID']='restart_reserved_buy'
        expected,money=apply(request,'restart_reserved_buy');assert not money['new_fills']
        restarted=Native(OUT/'observed/engine.test')
        try:
            answer=restarted.apply(request)
            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==expected[key]
        finally:restarted.close()
    finally:
        stream.close();native.close();baseline.close()
    race=Native(OUT/'observed/engine_race.test')
    try:
        for row in records:
            answer=race.apply(row['input'])
            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==row['output'][key]
            assert sorted(answer['Paths'])==sorted(row['output']['Paths'])
    finally:
        race.close()
        if old_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=old_tmp
        shutil.rmtree(temp)
    assert all(sha(p)==digest for p,digest in hashes.items())
    save(root/'examples.json',examples)
    save(root/'verification.json',dict(verified=True,at_ns=time.time_ns(),native_money_checks=len(records),
        native_race_cases=len(records),default_off_full_output_cases=30,exact_clock_causality=True,
        daily_buy_and_total_budgets_checked=True,restart_checked=True,live_changed=False,
        cycles_sha256=sha(root/'cycles.jsonl.gz'),examples_sha256=sha(root/'examples.json'),
        registration_sha256=sha(root/'registration.json')))
    print('EXIT_RESERVE_REGRESSIONS',len(records),flush=True)


if __name__=='__main__':main()
