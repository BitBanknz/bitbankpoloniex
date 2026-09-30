"""Exact logical clocks and independent daily allowance checks."""
from datetime import datetime, timezone
import sys
from build import REPO
sys.path.insert(0,str(REPO/'research/futureworker20260926'))
from outcomes import ns

MINUTE=60_000_000_000
HOUR=60*MINUTE
DAY=24*HOUR


def iso(value):
    seconds,fraction=divmod(value,1_000_000_000)
    suffix=('.'+f'{fraction:09d}'.rstrip('0')) if fraction else ''
    return datetime.fromtimestamp(seconds,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+suffix+'Z'


def causal(state,now):
    if state is None:return
    assert ns(state['LastCycle'])<=now
    assert all(ns(row['At'])<=now for row in state['Equity'])
    assert all(ns(p['Entered'])<=now for p in state['Holdings'].values())
    clocks=[ns(f['At']) for f in state['Fills'] or []]
    assert clocks==sorted(clocks) and all(value<=now for value in clocks)


def daily_budget(before,after,config,now):
    day=iso(now)[:10]
    start=before['OrdersToday'] if before and before['Day']==day else 0
    old=(before or {}).get('Fills') or []
    fills=(after['Fills'] or [])[len(old):]
    for fill in fills:
        assert start<config['MaxOrdersDay']
        if fill['Order']['side']=='BUY':
            assert start<config['MaxOrdersDay']-config.get('ExitOrderReserve',0)
        start+=1
    assert after['Day']==day and after['OrdersToday']==start
    return dict(orders_before=before['OrdersToday'] if before else 0,orders_after=start,
                new_orders=len(fills),daily_limit=config['MaxOrdersDay'],reserved=config.get('ExitOrderReserve',0))


def fresh(request,now,prediction=False):
    request['NowNS']=now
    for path,response in request['Responses'].items():
        if path.endswith('/orderBook') and response['Status']==200:response['Body']['ts']=now//1_000_000
        if path=='/markets/ticker24h':
            for ticker in response['Body']:ticker['ts']=now//1_000_000
    if prediction:
        body=request['Responses']['/prediction']['Body']
        body['issued_at']=iso(now//DAY*DAY)
        body['execution_hour']=iso(now//DAY*DAY+HOUR)
