"""Decimal reconstruction from frozen books and recorded fills; no native code.

Checks every minute-cycle cash/position transition, hourly marks, dust removal,
fees, order limits, executed-entry eligibility and top-up trigger. Recorded
intents are inputs; this does not prove that every possible order was emitted.
"""
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal as D,ROUND_CEILING,ROUND_FLOOR,ROUND_HALF_UP,getcontext
import hashlib
import json
from pathlib import Path

getcontext().prec=80
ZERO=D(0);BUDGET=D(495);RESERVE=D(198);TARGET=D(99);MAX_ORDER=D(49)


def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def iso(ts):return datetime.fromtimestamp(ts,timezone.utc).isoformat().replace('+00:00','Z')
def div(a,b):return (a/b).quantize(D('1e-16'),rounding=ROUND_HALF_UP)
def floor(q,scale):return q.quantize(D(1).scaleb(-scale),rounding=ROUND_FLOOR)


class Check:
    def __init__(self):self.count=0;self.maximum=ZERO
    def exact(self,actual,expected,label):
        actual=D(actual);expected=D(expected)
        assert actual==expected,(label,str(actual),str(expected))
        self.count+=1
    def metric(self,actual,expected,label):
        error=abs(D(str(actual))-expected)
        assert error<=D('1e-10'),(label,str(actual),str(expected),str(error))
        self.count+=1;self.maximum=max(self.maximum,error)


def verify(state,row,case,fixture,markets,check,require_stop_guard=False, actual_stop_hour=False, max_orders_day=12, exit_order_reserve=0):
    assert 0<=exit_order_reserve<=max_orders_day
    assert state['Schema']=='poloniex-bot-v1' and state['Mode']=='paper' and state['AccountBacked'] is False
    assert state['Pending'] is None
    check.exact(state['Budget'],BUDGET,'budget')
    symbols=[p.removesuffix('USDT')+'_USDT' for p in fixture['Pairs']]
    lookup={s:i for i,s in enumerate(symbols)}
    contracts={m['symbol']:m for m in markets}
    hours=[h for h in fixture['Hours'] if row['Start']<=h['TS']<=row['End']]
    assert hours and len(hours)>=168 and all(b['TS']-a['TS']==3600 for a,b in zip(hours,hours[1:]))
    assert hours[0]['TS']==row['Start'] and hours[-1]['TS']==row['End']
    fee=D(str(case['fee']));fraction=D('.25') if case['variant']==2 else ZERO
    below_stop_buys=[]
    fills=state['Fills'] or [];groups=defaultdict(list)
    assert [stamp(f['At']) for f in fills]==sorted(stamp(f['At']) for f in fills)
    for f in fills:groups[stamp(f['At'])].append(f)
    positions={};cash=BUDGET;high=BUDGET;day_start=BUDGET;day=None;daily_orders=0
    cooldown={};processed={};values=[];dust=[];fees=ZERO;topups=0;halted=False;last_ts=None;stop_rebuys=0
    peak_limit,day_limit=(D('.1'),D('.03')) if case['variant']==0 else (D('.25'),D('.08'))
    for hi,h in enumerate(hours):
        prices={s:D(format(h['Open'][j]*.9995,'.14f')) for j,s in enumerate(symbols)}
        assert all(v>0 for v in prices.values())
        hour=h['TS'];count=case['cycles'] if datetime.fromtimestamp(hour,timezone.utc).hour==1 else 1
        times=[hour+45+c*60 for c in range(count)]
        if hi==len(hours)-1:times.append(times[-1]) # Original final idempotent observation.
        for ts in times:
            last_ts=ts;equity=cash
            for s,p in list(positions.items()):
                value=p['quantity']*prices[s];equity+=value
                minimum=max(D(1),D(contracts[s]['symbolTradeLimit']['minAmount']))
                if value<minimum:
                    dust.append(dict(at=iso(ts),symbol=s,quantity=str(p['quantity']),mark=str(prices[s]),value=str(value)))
                    del positions[s]
                else:p['peak']=max(p['peak'],prices[s])
            high=max(high,equity)
            thisday=iso(ts)[:10]
            if thisday!=day:day=thisday;day_start=equity;daily_orders=0
            if equity<high*(1-peak_limit) or equity<day_start*(1-day_limit):halted=True
            marked=equity
            sold_this_cycle=set()
            for fill in groups.pop(ts,[]):
                order=fill['Order'];s=order['symbol'];side=order['side'];j=lookup[s]
                assert fill['Mode']=='paper' and side in ('BUY','SELL') and not fill.get('ExchangeTrades')
                assert order['type']=='LIMIT' and order['timeInForce']=='IOC' and order['accountType']=='SPOT' and not order['allowBorrow']
                limits=contracts[s]['symbolTradeLimit'];ps,qs=limits['priceScale'],limits['quantityScale']
                raw=D(format(h['Open'][j]*(1.0005 if side=='BUY' else .9995),'.14f'))
                price=raw.quantize(D(1).scaleb(-ps),rounding=ROUND_CEILING if side=='BUY' else ROUND_FLOOR)
                check.exact(order['price'],price,'book and tick price')
                qty=D(fill['Quantity']);check.exact(order['quantity'],qty,'order quantity')
                assert qty>0 and qty==floor(qty,qs)
                amount=qty*price;cost=amount*fee
                check.exact(fill['Amount'],amount,'fill amount');check.exact(fill['Fee'],cost,'fill fee')
                assert daily_orders<max_orders_day,('total_order_budget',daily_orders,max_orders_day)
                assert amount<=MAX_ORDER
                for key,actual,maximum in (('minQuantity',qty,False),('minAmount',amount,False),('maxQuantity',qty,True),('maxAmount',amount,True)):
                    bound=D(limits[key]);assert (bound==0 or actual<=bound) if maximum else actual>=bound
                depth=D(format(h['PriorTurnover'][j]/h['Open'][j]*.1,'.14f'))*D('.1')
                assert qty<=depth
                held=s in positions;suffix='';protective_clock=False
                if side=='BUY':
                    assert daily_orders<max_orders_day-exit_order_reserve,('buy_order_budget',daily_orders,max_orders_day,exit_order_reserve)
                    if held and prices[s]<=positions[s]['peak']*D('.9'):
                        below_stop_buys.append(dict(at=iso(ts),symbol=s,bid=str(prices[s]),peak=str(positions[s]['peak']),quantity=str(qty),same_cycle_sell=s in sold_this_cycle))
                        assert not require_stop_guard,('buy while below protective stop',s,ts)
                    assert datetime.fromtimestamp(ts,timezone.utc).hour==1 and not halted
                    ranks=fixture['Ranks'][str(hour//86400*86400)]
                    eligible=[sym for sym,k in lookup.items() if contracts[sym]['state']=='NORMAL' and contracts[sym]['quoteCurrencyName']=='USDT' and h['Volume24'][k]>=100000]
                    targets=sorted(eligible,key=lambda sym:(-ranks[lookup[sym]],sym))[:3]
                    assert s in targets
                    spend=min(MAX_ORDER,div(cash-RESERVE,1+fee))
                    if held:
                        assert case['variant']>0
                        gap=TARGET-positions[s]['quantity']*prices[s]
                        assert gap>=max(D('12.25'),TARGET*fraction),('top-up below deadband',s,ts,str(gap))
                        spend=min(spend,gap);suffix=f'|topup-{daily_orders}';topups+=1
                        if s in sold_this_cycle:stop_rebuys+=1
                    else:
                        assert len(positions)<3 and ts>=cooldown.get(s,0)
                    wanted=floor(min(div(spend,price),depth),qs)
                    check.exact(qty,wanted,'capped buy quantity')
                    cash-=amount+cost
                    assert cash>=RESERVE
                    if held:positions[s]['quantity']+=qty
                    else:positions[s]=dict(quantity=qty,peak=price,entered=ts)
                else:
                    assert held and qty<=positions[s]['quantity']
                    protective_clock=actual_stop_hour and prices[s]<=positions[s]['peak']*D('.9')
                    wanted=floor(min(positions[s]['quantity'],depth,floor(div(MAX_ORDER,price),qs)),qs)
                    check.exact(qty,wanted,'capped sell quantity')
                    cash+=amount-cost;positions[s]['quantity']-=qty;sold_this_cycle.add(s)
                    if positions[s]['quantity']==0:
                        del positions[s];cooldown[s]=ts+case['cooldown']*3600
                decision_hour=hour//86400*86400+3600 if not halted and datetime.fromtimestamp(hour,timezone.utc).hour<=1 and str(hour//86400*86400) in fixture['Ranks'] else hour
                if protective_clock:decision_hour=ts//3600*3600
                key=f'{iso(decision_hour)}|{s}|{side}'+suffix
                assert key not in processed
                expected_id='bbp-'+hashlib.sha256(('paper|'+key).encode()).hexdigest()[:40]
                assert order['clientOrderId']==expected_id,(key,order['clientOrderId'],expected_id)
                processed[key]=True;daily_orders+=1;fees+=cost
        values.append(dict(at=hour,value=marked))
    assert not groups,('unprocessed fill clocks',list(groups))
    assert len(values)==len(state['Equity'])
    for actual,expected in zip(state['Equity'],values):
        assert stamp(actual['At'])==expected['at'];check.exact(actual['Value'],expected['value'],'hourly equity')
    check.exact(state['Cash'],cash,'terminal cash');check.exact(state['HighWater'],high,'high water');check.exact(state['DayStart'],day_start,'day start')
    assert state['Day']==day and state['OrdersToday']==daily_orders and stamp(state['LastCycle'])==last_ts
    assert state['Processed']==processed and {s:stamp(t) for s,t in state['Cooldown'].items()}==cooldown
    assert set(state['Holdings'])==set(positions)
    for s,p in positions.items():
        native=state['Holdings'][s];assert native['Imported'] is False and stamp(native['Entered'])==p['entered']
        check.exact(native['Quantity'],p['quantity'],'terminal quantity');check.exact(native['Peak'],p['peak'],'held peak')
    assert bool(state['Halted'])==halted
    if halted:assert state['Halted']=='drawdown or daily loss limit; operator review required'
    peak=values[0]['value'];dd=ZERO;budget_peak=BUDGET;budget_dd=ZERO
    for v in values:
        peak=max(peak,v['value']);budget_peak=max(budget_peak,v['value'])
        dd=max(dd,div(peak-v['value'],peak)*100);budget_dd=max(budget_dd,div(budget_peak-v['value'],budget_peak)*100)
    total=div(values[-1]['value']-BUDGET,BUDGET)*100
    report=row['Report'];check.exact(report['Equity'],values[-1]['value'],'reported equity');check.exact(report['Budget'],BUDGET,'reported budget')
    check.exact(report['HighWater'],high,'reported high water');check.metric(report['ReturnPct'],total,'return');check.metric(report['MaxDrawdownPct'],dd,'drawdown')
    assert report['Points']==len(values) and report['Fills']==len(fills) and report['Holdings']==len(positions)
    assert stamp(report['First'])==row['Start'] and stamp(report['Last'])==row['End'] and report['Halted']==state['Halted']
    return dict(verified=True,hours=len(hours),fills=len(fills),topups=topups,fees=str(fees),dust=dust,below_stop_buys=below_stop_buys,
        same_cycle_sell_then_topup=stop_rebuys,return_pct=str(total),max_drawdown_pct=str(dd),initial_budget_drawdown_pct=str(budget_dd),
        final_equity=str(values[-1]['value']),final_cash=str(cash),holdings=len(positions),halted=halted)
