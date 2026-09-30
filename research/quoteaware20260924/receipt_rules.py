"""Independent receipt audit v2: unstable response clocks never authorize data.

No imports from the collector, no network, no orders, no forward-filled ranks.
Hypothetical sizes assume 49 USDT spend; account/cooldown/risk gates are unknown.
"""
import argparse
import base64
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_UP, getcontext
import gzip
import hashlib
import json
from pathlib import Path
import time

getcontext().prec=70
D=Decimal
MINUTE=60_000_000_000
HOUR=60*MINUTE
SYMBOLS=('BNB_USDT','ETC_USDT','ETH_USDT','PEPE_USDT','SUI_USDT','TRX_USDT','XRP_USDT','ZEC_USDT')
ENDPOINTS=[('ranks','http://127.0.0.1:8745/api/trading-bot/rotation-signals'),('markets','https://api.poloniex.com/markets'),('ticker24h','https://api.poloniex.com/markets/ticker24h')]+[('book_'+s,'https://api.poloniex.com/markets/'+s+'/orderBook?limit=5') for s in SYMBOLS]


def digest(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_bytes())
def decimal(x):
    v=D(str(x));assert v.is_finite(),'nonfinite number';return v
def timestamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())*1_000_000_000
def fresh(ms,now,age):return 0<int(ms)<=now//1_000_000+5000 and int(ms)>=now//1_000_000-age*1000


def decode_record(r,expected,previous_receipt):
    assert (r['name'],r['url'])==expected,'endpoint identity'
    assert r['method']=='GET' and r['credentials_used'] is False
    raw=base64.b64decode(r['body_b64'],validate=True)
    assert len(raw)==r['body_bytes'] and digest(raw)==r['body_sha256'],'body integrity'
    assert r['request_started_ns']>=previous_receipt,'request ordering'
    wall=r['response_received_ns']-r['request_started_ns']
    mono=r['monotonic_received_ns']-r['monotonic_started_ns']
    stable=wall>=0 and mono>=0 and abs(wall-mono)<=5_000_000_000
    assert r['wall_clock_stable']==stable,'clock stability flag'
    assert len(raw)<=2<<20
    if stable and r['status']==200 and not r['body_truncated'] and r['error'] is None:
        return json.loads(raw)
    return None


def ranks_at(value,now):
    if not value or value.get('available') is not True:return None
    assert value['venue']=='POLONIEX' and value['mode']=='research_rank_forecast'
    issued=timestamp(value['issued_at']);execution=timestamp(value['execution_hour'])
    assert issued%(24*HOUR)==0 and execution==issued+HOUR
    scores={}
    for symbol,score in value['rank_scores'].items():
        assert symbol.endswith('USDT') and not any(c in symbol for c in '/ ._-?')
        scores[symbol[:-4]+'_USDT']=decimal(score)
    assert scores
    if not execution<=now<execution+HOUR:return None
    return scores


def levels(flat,ascending):
    assert len(flat)>=2 and len(flat)%2==0,'incomplete book levels'
    result=[(decimal(flat[i]),decimal(flat[i+1])) for i in range(0,len(flat),2)]
    assert all(p>0 and q>=0 for p,q in result),'invalid book level'
    prices=[p for p,_ in result]
    assert prices==sorted(prices,reverse=not ascending),'unsorted book'
    return result


def feasibility(market,ticker,book,now):
    asks=levels(book['asks'],True);bids=levels(book['bids'],False)
    ask=asks[0][0];bid=bids[0][0];assert ask>=bid,'crossed book'
    spread=(ask-bid)/bid
    reasons=[]
    market_ok=market['state']=='NORMAL' and market['quoteCurrencyName']=='USDT'
    volume_ok=decimal(ticker['amount'])>=100000 and fresh(ticker['ts'],now,300)
    if not market_ok:reasons.append('market_state')
    if not volume_ok:reasons.append('volume_or_ticker_age')
    if not fresh(book['ts'],now,30):reasons.append('book_age')
    # Native decimal division rounds to sixteen places before its float compare.
    if float(spread.quantize(D('1e-16'),rounding=ROUND_HALF_UP))>.003:reasons.append('spread')
    limit=market['symbolTradeLimit'];ps=limit['priceScale'];qs=limit['quantityScale']
    assert 0<=ps<=18 and 0<=qs<=18
    executable=[(p,q) for p,q in asks if p<=ask*D('1.001')]
    price=max(p for p,_ in executable).quantize(D(1).scaleb(-ps),rounding=ROUND_CEILING)
    depth=sum(q for _,q in executable)
    quote_quantity=(D(49)/price).quantize(D('1e-16'),rounding=ROUND_HALF_UP)
    quantity=min(quote_quantity,depth*D('.1')).quantize(D(1).scaleb(-qs),rounding=ROUND_FLOOR)
    amount=quantity*price
    if depth<=0 or quantity<=0:reasons.append('zero_size')
    for key,actual,is_maximum in [('minQuantity',quantity,False),('minAmount',amount,False),('maxQuantity',quantity,True),('maxAmount',amount,True)]:
        bound=decimal(limit[key]);assert bound>=0
        if (is_maximum and bound>0 and actual>bound) or (not is_maximum and actual<bound):reasons.append(key)
    return dict(symbol=market['symbol'],spread_bps=str(spread*10000),bid=str(bid),ask=str(ask),
        book_age_ms=now//1_000_000-int(book['ts']),universe_eligible=market_ok and volume_ok,
        quote_feasible=not reasons,reasons=reasons,hypothetical_buy_price=str(price),hypothetical_buy_quantity=str(quantity),hypothetical_buy_amount=str(amount),
        assumed_spend_usdt='49',account_gates_checked=False)


def audit(root,through):
    mirror=root/'mirror';transfer=read(root/'transfer.json');tr=read(root/'transfer.receipt.json')
    assert tr['through']==through and tr['returncode']==0 and tr['request_ns']<=tr['received_ns']
    assert digest((root/'transfer.json').read_bytes())==tr['transfer_sha256']
    for name,record in transfer['files'].items():
        assert Path(name).name==name
        raw=(mirror/name).read_bytes()
        assert raw==base64.b64decode(record['body_b64'],validate=True)
        assert digest(raw)==record['sha256'] and len(raw)==record['bytes']
    p=read(mirror/'protocol.json');started=read(mirror/'started.json');launch=read(mirror/'launch.json');validation=read(mirror/'validation.json')
    ph=digest((mirror/'protocol.json').read_bytes())
    assert started['protocol_sha256']==launch['protocol_sha256']==ph
    assert started['recorder_sha256']==p['recorder_sha256']==digest((mirror/'recorder.py').read_bytes())
    assert p['protocol_document_sha256']==digest((mirror/'PROTOCOL.md').read_bytes())
    assert p['format']=='poloniex-public-receipts-v1' and p['symbols']==list(SYMBOLS)
    assert p['endpoints']==[list(v) for v in ENDPOINTS]
    assert p['period_ns']==MINUTE and p['slots']==10080 and p['slot_window_ns']==45_000_000_000
    assert p['end_exclusive_ns']==p['start_ns']+10080*MINUTE and p['start_ns']%MINUTE==15_000_000_000
    assert p['credentials_used'] is False and p['external_orders'] is False
    assert started['at_ns']<p['start_ns'] and validation['at_ns']<started['at_ns']
    assert validation['verified'] is True and validation['tests']==11
    for path,expected in validation['hashes'].items():assert digest((mirror/Path(path).name).read_bytes())==expected
    assert 'Ran 11 tests' in (mirror/'remote_tests.log').read_text() and '\nOK\n' in (mirror/'remote_tests.log').read_text()
    summaries=[];gaps=[];previous=p['start_ns'];responses=0
    for index in range(through+1):
        scheduled=p['start_ns']+index*MINUTE;stem=f'minute_{index:05d}'
        rp=mirror/(stem+'.receipt.json')
        if not rp.exists():
            gap=read(mirror/f'gap_{index:05d}.json')
            assert gap['index']==index and gap['scheduled_ns']==scheduled and gap['requests_made']==0
            assert gap['observed_ns']>=scheduled+p['slot_window_ns'];gaps.append(gap);continue
        receipt=read(rp);archive=mirror/(stem+'.jsonl.gz')
        assert receipt['index']==index and receipt['scheduled_ns']==scheduled and receipt['archive']==archive.name
        assert receipt['archive_sha256']==digest(archive.read_bytes())
        records=[json.loads(line) for line in gzip.decompress(archive.read_bytes()).splitlines()]
        assert len(records)==receipt['attempted_requests']<=11 and receipt['planned_requests']==11
        assert receipt['complete']==(len(records)==11)
        assert receipt['credentials_used'] is False and receipt['external_orders'] is False and receipt['atomic_exchange_snapshot'] is False
        values={};statuses={}
        for j,r in enumerate(records):
            assert scheduled<=r['request_started_ns']<scheduled+p['slot_window_ns'],'request outside capture window'
            values[r['name']]=decode_record(r,ENDPOINTS[j],previous)
            statuses[r['name']]=r['status'];previous=r['response_received_ns'];responses+=1
        assert receipt['first_request_ns']==min((r['request_started_ns'] for r in records),default=None)
        assert receipt['last_receipt_ns']==max((r['response_received_ns'] for r in records),default=None)
        now=receipt['complete_after_ns'];assert now>=previous and now<=transfer['at_ns']
        successful=len(records)==11 and all(r['status']==200 and r['error'] is None and r['wall_clock_stable'] and not r['body_truncated'] for r in records)
        assert receipt['all_responses_successful']==successful
        row=dict(index=index,scheduled_ns=scheduled,complete_after_ns=now,statuses=statuses,complete=receipt['complete'],all_responses_successful=successful,books=[],targets=None)
        if values.get('markets') and values.get('ticker24h'):
            markets={m['symbol']:m for m in values['markets']};tickers={t['symbol']:t for t in values['ticker24h']}
            assert len(markets)==len(values['markets']) and len(tickers)==len(values['ticker24h'])
            for symbol in SYMBOLS:
                book=values.get('book_'+symbol)
                if book and symbol in markets and symbol in tickers:
                    row['books'].append(feasibility(markets[symbol],tickers[symbol],book,now))
            scores=ranks_at(values.get('ranks'),now)
            if scores:
                eligible={b['symbol'] for b in row['books'] if b['universe_eligible']}
                ordered=sorted((s for s in scores if s in eligible),key=lambda s:(-scores[s],s))
                row['targets']=ordered[:3]
                row['feasible_targets']=[s for s in row['targets'] if next(b for b in row['books'] if b['symbol']==s)['quote_feasible']]
        summaries.append(row)
    return dict(verified=True,through=through,captures=len(summaries),gaps=gaps,responses=responses,summaries=summaries,
        protocol_sha256=ph,process_alive_at_transfer=transfer['process_alive'],recorder_failures_at_transfer=transfer['failures'],
        atomic_exchange_snapshot=False,performance_evidence=False,account_gates_checked=False,external_orders=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--through',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.root,args.through);args.output.mkdir(parents=True,exist_ok=False)
    result['verified_at_ns']=time.time_ns();result['auditor_sha256']=digest(Path(__file__).read_bytes())
    result['input_hashes']={str(p):digest(p.read_bytes()) for p in sorted(args.root.rglob('*')) if p.is_file()}
    (args.output/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('summaries','input_hashes')}))
