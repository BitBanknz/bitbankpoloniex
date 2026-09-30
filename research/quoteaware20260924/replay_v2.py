"""Paired native cycles from recorded quotes, plus adversarial account scenarios."""
from copy import deepcopy
from decimal import Decimal,getcontext
import base64
import gzip
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
from build import HERE,OUT,REPO,save,sha

getcontext().prec=70
D=Decimal
BASE=Path('/vfast/data/trading_research_20260924')
MIRROR=BASE/'poloniex_public_retention_first_prefix_v1/mirror'


class Native:
    def __init__(self,binary):
        self.p=subprocess.Popen([str(binary),'-test.run=^TestObservedCycleDriver$','-test.timeout=0'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,env={**os.environ,'GOMAXPROCS':'1'})
    def apply(self,request):
        self.p.stdin.write(json.dumps(request,separators=(',',':'),allow_nan=False)+'\n');self.p.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(self.p.stdout,selectors.EVENT_READ)
            if not selector.select(30):self.p.kill();raise RuntimeError('native cycle timeout')
        line=self.p.stdout.readline()
        if not line.startswith('{'):raise RuntimeError('native cycle failed: '+line+self.p.stderr.read())
        result=json.loads(line);assert result['ID']==request['ID'];return result
    def close(self):
        self.p.stdin.close();self.p.stdin=None
        stdout,stderr=self.p.communicate(timeout=10)
        assert self.p.returncode==0,(stdout,stderr)


def config(aware,fee):
    return dict(Mode='paper',Budget='495',MaxOrder='49',Slots=3,CashReserve=.4,MaxOrdersDay=12,CooldownHours=120,
        SlotTopUp=True,HaltPeakDD=.25,HaltDailyLoss=.08,FeeRate=str(fee),QuoteAwareEntry=aware)


def captured(index):
    receipt=json.loads((MIRROR/f'minute_{index:05d}.receipt.json').read_text())
    archive=MIRROR/receipt['archive'];assert sha(archive)==receipt['archive_sha256']
    responses={}
    for line in gzip.decompress(archive.read_bytes()).splitlines():
        record=json.loads(line);raw=base64.b64decode(record['body_b64']);assert __import__('hashlib').sha256(raw).hexdigest()==record['body_sha256']
        path='/prediction' if record['name']=='ranks' else record['url'].split('api.poloniex.com',1)[1].split('?',1)[0]
        responses[path]=dict(Status=record['status'],Body=json.loads(raw))
    return receipt['complete_after_ns'],responses


def money(before,after,fee):
    old=(before or {}).get('Fills') or [];new=after['Fills'] or [];assert new[:len(old)]==old
    cash=D((before or {}).get('Cash','495'));holdings={s:D(p['Quantity']) for s,p in (before or {}).get('Holdings',{}).items()}
    for f in new[len(old):]:
        q=D(f['Quantity']);a=D(f['Amount']);cost=D(f['Fee']);price=D(f['Order']['price']);symbol=f['Order']['symbol']
        assert a==q*price and cost==a*D(str(fee)) and f['Mode']=='paper' and q>0
        assert a<=49
        if f['Order']['side']=='BUY':cash-=a+cost;holdings[symbol]=holdings.get(symbol,D(0))+q
        else:cash+=a-cost;holdings[symbol]=holdings.get(symbol,D(0))-q
    assert cash==D(after['Cash']) and cash>=0 and after['Pending'] is None
    for symbol,q in holdings.items():
        assert q==D(after['Holdings'].get(symbol,{}).get('Quantity','0')),(symbol,q,after['Holdings'])
    assert after['OrdersToday']<=12
    return len(new)-len(old)


def synthetic():
    now=1790214960000000000 # 2026-09-24 01:56 UTC, deliberately a fixture clock.
    markets=[];tickers=[];responses={}
    for s in ('AAA_USDT','BBB_USDT','CCC_USDT','DDD_USDT'):
        markets.append(dict(symbol=s,baseCurrencyName=s[:-5],quoteCurrencyName='USDT',state='NORMAL',symbolTradeLimit=dict(priceScale=4,quantityScale=6,minQuantity='0.000001',minAmount='1',maxQuantity='0',maxAmount='0')))
        tickers.append(dict(symbol=s,amount='1000000',ts=now//1_000_000))
        responses['/markets/'+s+'/orderBook']=dict(Status=200,Body=dict(asks=['10.01','1000'],bids=['10','1000'],ts=now//1_000_000))
    responses['/markets']=dict(Status=200,Body=markets);responses['/markets/ticker24h']=dict(Status=200,Body=tickers)
    responses['/prediction']=dict(Status=200,Body=dict(available=True,venue='POLONIEX',mode='research_rank_forecast',issued_at='2026-09-24T00:00:00Z',execution_hour='2026-09-24T01:00:00Z',rank_scores={s.replace('_',''):4-i for i,s in enumerate(('AAA_USDT','BBB_USDT','CCC_USDT','DDD_USDT'))}))
    return now,responses


def main():
    registration=json.loads((OUT/'driver/verification.json').read_text());assert registration['verified']
    assert all(sha(p)==h for p,h in registration['hashes'].items())
    output=OUT/'paired_replay_v2';output.mkdir(exist_ok=False)
    inputs=[Path(__file__),OUT/'driver/verification.json',*MIRROR.iterdir()];save(output/'inputs.json',{str(p):sha(p) for p in inputs if p.is_file()})
    original=Native(registration['binaries']['original']);candidate=Native(registration['binaries']['candidate'])
    journal=[];states={};parity=0;checks=[]
    try:
        for index in range(5):
            now,responses=captured(index)
            for fee in ('.003','.004','.006'):
                for aware in (False,True):
                    key=f'aware{int(aware)}_fee{fee}';before=states.get(key)
                    request=dict(ID=f'{index}_{key}',NowNS=now,Config=config(aware,fee),Before=before,Responses=responses)
                    answer=candidate.apply(request);assert answer['CycleError'] in ('','BitBank unavailable and no accepted fallback; entries paused')
                    if not aware:
                        baseline=original.apply(request);assert baseline==answer,request['ID'];parity+=1
                    money(before,answer['State'],fee);states[key]=answer['State'];journal.append(dict(input=request,output=answer))
        # Complete native-cycle adversarial checks, with synthetic quotes/positions.
        for scenario in ('all_feasible','blocked_entries','held_wide','cooldown','daily_cap','cash_reserve','expired','incomplete_valuation','protective_exit','halted_protective_exit'):
            now,responses=synthetic()
            initial=original.apply(dict(ID='initialize',NowNS=now,Config=config(False,'.003'),Before=None,Responses={**responses,'/prediction':dict(Status=503,Body={})}))['State']
            before=deepcopy(initial)
            if scenario in ('blocked_entries','held_wide','daily_cap','cash_reserve'):
                responses['/markets/AAA_USDT/orderBook']['Body']['asks']=['11','1000']
                responses['/markets/BBB_USDT/orderBook']['Body']['asks']=['10.01','.1']
            if scenario=='held_wide':
                before['Cash']='475';before['Holdings']['AAA_USDT']=dict(Imported=False,Quantity='2',Peak='10',Entered='2026-09-20T00:00:00Z')
            if scenario=='cooldown':before['Cooldown']['AAA_USDT']='2026-09-25T00:00:00Z'
            if scenario=='daily_cap':before['OrdersToday']=11
            if scenario=='cash_reserve':
                before['Cash']='199';before['Holdings']['DDD_USDT']=dict(Imported=False,Quantity='29.6',Peak='10',Entered='2026-09-24T01:00:00Z')
            if scenario in ('expired','protective_exit','halted_protective_exit'):responses['/prediction']=dict(Status=503,Body={})
            if scenario in ('incomplete_valuation','protective_exit','halted_protective_exit'):
                before['Cash']='475';before['Holdings']['DDD_USDT']=dict(Imported=False,Quantity='2',Peak='10',Entered='2026-09-24T01:00:00Z')
                if scenario=='incomplete_valuation':responses['/markets/DDD_USDT/orderBook']['Body']['ts']-=60_000
                else:responses['/markets/DDD_USDT/orderBook']['Body'].update(bids=['8.9','1000'],asks=['8.9089','1000'])
            if scenario=='halted_protective_exit':before['Halted']='drawdown or daily loss limit; operator review required'
            answers=[]
            for aware in (False,True):
                request=dict(ID=f'{scenario}_{int(aware)}',NowNS=now,Config=config(aware,'.003'),Before=before,Responses=responses)
                answer=candidate.apply(request);money(before,answer['State'],'.003')
                if not aware:assert original.apply(request)==answer;parity+=1
                journal.append(dict(input=request,output=answer));answers.append(answer)
            a,b=answers;fills=b['State']['Fills'] or []
            symbols=[f['Order']['symbol'] for f in fills]
            if scenario=='all_feasible':assert a['State']==b['State'] and len(fills)==3
            if scenario=='blocked_entries':assert [f['Order']['symbol'] for f in a['State']['Fills']]==['CCC_USDT'] and symbols==['CCC_USDT','DDD_USDT']
            if scenario=='held_wide':assert all(f['Order']['side']=='BUY' for f in fills) and 'AAA_USDT' in b['State']['Holdings'] and symbols==['CCC_USDT','DDD_USDT']
            if scenario=='cooldown':assert symbols==['BBB_USDT','CCC_USDT']
            if scenario=='daily_cap':assert len(fills)==1 and b['State']['OrdersToday']==12
            if scenario in ('cash_reserve','expired','incomplete_valuation'):assert len(fills)==0
            if scenario in ('protective_exit','halted_protective_exit'):assert len(fills)==1 and fills[0]['Order']['side']=='SELL' and symbols==['DDD_USDT']
            assert D(b['State']['Cash'])>=198
            checks.append(scenario)
    finally:original.close();candidate.close()
    with gzip.open(output/'cycles.jsonl.gz','wt') as f:
        for record in journal:f.write(json.dumps(record,separators=(',',':'))+'\n')
    last_responses=captured(4)[1];summary=[]
    for key,state in states.items():
        equity=D(state['Cash'])+sum(D(p['Quantity'])*D(last_responses['/markets/'+s+'/orderBook']['Body']['bids'][0]) for s,p in state['Holdings'].items())
        summary.append(dict(account=key,fills=len(state['Fills'] or []),cash=state['Cash'],holdings=list(state['Holdings']),post_cycle_bid_equity=str(equity),post_cycle_return_pct=str((equity/D(495)-1)*100)))
    assert all(sha(p)==h for p,h in registration['hashes'].items())
    save(output/'verification.json',dict(verified=True,at_ns=time.time_ns(),original_control_exact_cycles=parity,total_saved_cycles=len(journal),synthetic_checks=checks,summary=summary,
        independent_fill_money_checks=True,discovery_replay_only=True,prospective_profitability_established=False,external_orders=False,
        hashes={str(p):sha(p) for p in (Path(__file__),output/'inputs.json',output/'cycles.jsonl.gz',OUT/'driver/verification.json')}))
    print('PAIRED_REPLAY_VERIFIED',parity,len(journal),json.dumps(summary),flush=True)

if __name__=='__main__':main()
