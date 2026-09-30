"""Independent Decimal accounting and public-book marks, not a planner oracle."""
from copy import deepcopy
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, getcontext
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'quoteaware20260924'))
import receipt_rules as rules
getcontext().prec=80

def bid_book(responses,symbol,now):
    r=responses.get('/markets/'+symbol+'/orderBook',{})
    b=r.get('Body',{})
    if r.get('Status')!=200 or not rules.fresh(b.get('ts',0),now,30):return None
    try:
        bids=rules.levels(b['bids'],False);asks=rules.levels(b['asks'],True)
        if bids[0][0]>asks[0][0]:return None
    except (AssertionError,ValueError,KeyError):return None
    return bids,asks

def mark(state,responses,now):
    total=D(state['Cash']);missing=[];marks={}
    for s,p in state['Holdings'].items():
        book=bid_book(responses,s,now)
        if book is None:missing.append(s);continue
        marks[s]=str(book[0][0][0]);total+=D(p['Quantity'])*book[0][0][0]
    return (None if missing else total),sorted(missing),marks

def transition(before,after,fee,responses,now,guarded):
    before=before or dict(Cash='495',Holdings={},Fills=[])
    previous=before.get('Fills') or [];fills=after.get('Fills') or []
    assert fills[:len(previous)]==previous
    new=fills[len(previous):]
    assert after['Schema']=='poloniex-bot-v1' and after['Mode']=='paper' and not after['AccountBacked']
    assert after['Budget']=='495' and after['Pending'] is None and after['OrdersToday']<=12
    contracts={m['symbol']:m for m in responses['/markets']['Body']}
    positions=deepcopy(before['Holdings']);cash=D(before['Cash']);dust=[];stops=set()
    for s,p in list(positions.items()):
        book=bid_book(responses,s,now)
        if book is None:continue
        bid=book[0][0][0];q=D(p['Quantity'])
        if q*bid<max(D(1),D(contracts[s]['symbolTradeLimit']['minAmount'])):
            dust.append(dict(symbol=s,quantity=str(q),bid=str(bid),value=str(q*bid)));del positions[s];continue
        p['Peak']=str(max(D(p['Peak']),bid))
        if bid<=D(p['Peak'])*D('.9'):stops.add(s)
    fee_total=D(0);turnover=D(0);conflicts=[]
    for f in new:
        o=f['Order'];s=o['symbol'];side=o['side'];q=D(f['Quantity']);a=D(f['Amount']);cost=D(f['Fee']);price=D(o['price'])
        assert f['Mode']=='paper' and not f.get('ExchangeTrades')
        assert side in ('BUY','SELL') and a==q*price and cost==a*D(fee) and q>0 and a<=49
        assert D(o['quantity'])==q and o['type']=='LIMIT' and o['timeInForce']=='IOC' and o['accountType']=='SPOT' and not o['allowBorrow']
        book=bid_book(responses,s,now);assert book is not None
        bids,asks=book;levels=asks if side=='BUY' else bids;anchor=levels[0][0]
        assert float(((asks[0][0]-bids[0][0])/bids[0][0]).quantize(D('1e-16'),rounding=ROUND_HALF_UP))<=.003
        executable=[(v,size) for v,size in levels if (v<=anchor*D('1.001') if side=='BUY' else v>=anchor*D('.999'))]
        limits=contracts[s]['symbolTradeLimit'];ps=limits['priceScale'];qs=limits['quantityScale']
        worst=(max if side=='BUY' else min)(v for v,_ in executable)
        expected=worst.quantize(D(1).scaleb(-ps),rounding=ROUND_CEILING if side=='BUY' else ROUND_FLOOR)
        assert price==expected and q==q.quantize(D(1).scaleb(-qs),rounding=ROUND_FLOOR)
        assert q<=sum(size for _,size in executable)*D('.1')
        for name,actual,maximum in [('minQuantity',q,False),('minAmount',a,False),('maxQuantity',q,True),('maxAmount',a,True)]:
            v=D(limits[name]);assert (v==0 or actual<=v) if maximum else actual>=v
        if side=='BUY':
            if s in stops:
                conflicts.append(dict(symbol=s,quantity=str(q),price=str(price)));assert not guarded,('buy below stop',s,now)
            cash-=a+cost;assert cash>=198
            if s in positions:positions[s]['Quantity']=str(D(positions[s]['Quantity'])+q)
            else:positions[s]=dict(Imported=False,Quantity=str(q),Peak=str(price),Entered=f['At'])
        else:
            assert s in positions and q<=D(positions[s]['Quantity'])
            cash+=a-cost;remaining=D(positions[s]['Quantity'])-q
            if remaining:positions[s]['Quantity']=str(remaining)
            else:del positions[s]
        fee_total+=cost;turnover+=a
    assert cash==D(after['Cash']) and cash>=0
    assert set(positions)==set(after['Holdings'])
    for s,p in positions.items():
        actual=after['Holdings'][s]
        assert D(actual['Quantity'])==D(p['Quantity']) and D(actual['Peak'])==D(p['Peak'])
        assert actual['Imported']==p['Imported'] and actual['Entered']==p['Entered']
    equity,missing,marks=mark(after,responses,now)
    return dict(new_fills=new,cash=str(cash),fees=str(fee_total),turnover=str(turnover),dust=dust,
        below_stop_buys=conflicts,equity=None if equity is None else str(equity),unpriced=missing,marks=marks)
