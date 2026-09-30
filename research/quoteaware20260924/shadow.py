"""Frozen future-data replay; observed-book paper fills, not submitted orders.

Logical cycles run at source-batch availability. They may be computed later.
This worker does not claim contemporaneous order decisions or actual IOC fills.
"""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import threading
import time
from decimal import Decimal,getcontext
from native import Native
import receipt_rules as rules

getcontext().prec=70
D=Decimal
MINUTE=60_000_000_000


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def read(p):return json.loads(Path(p).read_bytes())
def publish(p,raw):
    p=Path(p);temp=p.with_name(p.name+'.partial')
    with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.link(temp,p);temp.unlink()
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
def heartbeat(root,**v):
    temp=root/'heartbeat.tmp';temp.write_bytes(encode(dict(at_ns=time.time_ns(),pid=os.getpid(),**v)));os.replace(temp,root/'heartbeat.json')


def load_capture(source,index,p):
    receipt_path=source/f'minute_{index:05d}.receipt.json';r=read(receipt_path)
    scheduled=p['source_start_ns']+index*MINUTE
    assert r['index']==index and r['scheduled_ns']==scheduled and r['archive']==f'minute_{index:05d}.jsonl.gz'
    archive=source/r['archive'];assert sha(archive)==r['archive_sha256']
    records=[json.loads(line) for line in gzip.decompress(archive.read_bytes()).splitlines()]
    assert r['attempted_requests']==len(records) and r['planned_requests']==11
    if not r['complete'] or len(records)!=11:return None,dict(reason='incomplete_source_capture',receipt=r)
    previous=scheduled;responses={};statuses={}
    for record,endpoint in zip(records,rules.ENDPOINTS):
        assert scheduled<=record['request_started_ns']<scheduled+45_000_000_000
        value=rules.decode_record(record,endpoint,previous);previous=record['response_received_ns']
        if not record['wall_clock_stable']:return None,dict(reason='unstable_source_clock',receipt=r)
        name=record['name'];statuses[name]=record['status']
        path='/prediction' if name=='ranks' else record['url'].split('api.poloniex.com',1)[1].split('?',1)[0]
        if value is None:responses[path]=dict(Status=503,Body={})
        else:responses[path]=dict(Status=record['status'],Body=value)
    assert r['first_request_ns']==records[0]['request_started_ns'] and r['last_receipt_ns']==previous
    assert previous<=r['complete_after_ns']<=time.time_ns()
    if responses['/markets']['Status']!=200 or responses['/markets/ticker24h']['Status']!=200:return None,dict(reason='market_metadata_unavailable',receipt=r)
    ranks=responses['/prediction']
    if ranks['Status']==200:
        scores=rules.ranks_at(ranks['Body'],r['complete_after_ns'])
        if scores and not set(scores)<=set(rules.SYMBOLS):raise RuntimeError('rank universe changed outside frozen book coverage')
    provenance=dict(receipt_sha256=sha(receipt_path),archive_sha256=sha(archive),source_index=index,scheduled_ns=scheduled,
        available_at_ns=r['complete_after_ns'],statuses=statuses,actual_decision_commit_claimed=False)
    return dict(NowNS=r['complete_after_ns'],Responses=responses),provenance


def check_money(before,after,fee,responses,now):
    old=(before or {}).get('Fills') or [];fills=after['Fills'] or [];assert fills[:len(old)]==old
    cash=D((before or {}).get('Cash','495'));quantities={s:D(v['Quantity']) for s,v in (before or {}).get('Holdings',{}).items()}
    markets={m['symbol']:m for m in responses['/markets']['Body']};dust=[]
    for symbol,q in list(quantities.items()):
        book=responses.get('/markets/'+symbol+'/orderBook',{}).get('Body',{})
        if symbol not in after['Holdings'] and book.get('bids') and rules.fresh(book.get('ts',0),now,30):
            threshold=max(D(1),D(markets[symbol]['symbolTradeLimit']['minAmount']))
            if q*D(book['bids'][0])<threshold and not any(f['Order']['symbol']==symbol for f in fills[len(old):]):
                quantities.pop(symbol);dust.append(symbol)
    for f in fills[len(old):]:
        order=f['Order'];q=D(f['Quantity']);amount=D(f['Amount']);cost=D(f['Fee']);symbol=order['symbol']
        assert f['Mode']=='paper' and amount==q*D(order['price']) and q>0 and cost==amount*D(fee) and amount<=49
        assert order['type']=='LIMIT' and order['timeInForce']=='IOC' and order['accountType']=='SPOT' and not order['allowBorrow']
        if order['side']=='BUY':
            cash-=amount+cost;quantities[symbol]=quantities.get(symbol,D(0))+q;assert cash>=198
        else:
            assert order['side']=='SELL';cash+=amount-cost;quantities[symbol]=quantities.get(symbol,D(0))-q
    assert cash==D(after['Cash']) and cash>=0 and after['Pending'] is None and after['OrdersToday']<=12
    actual={s:D(v['Quantity']) for s,v in after['Holdings'].items()}
    assert {s:q for s,q in quantities.items() if q!=0}==actual
    return dict(new_fills=len(fills)-len(old),dust_drops=dust,cash=str(cash))


def post_mark(state,responses,now):
    value=D(state['Cash'])
    for symbol,position in state['Holdings'].items():
        r=responses.get('/markets/'+symbol+'/orderBook',{})
        b=r.get('Body',{})
        if r.get('Status')!=200 or not b.get('bids') or not rules.fresh(b.get('ts',0),now,30):return None
        try:
            bids=rules.levels(b['bids'],False);asks=rules.levels(b['asks'],True)
            if bids[0][0]>asks[0][0]:return None
        except (AssertionError,ValueError,KeyError):return None
        value+=D(position['Quantity'])*bids[0][0]
    return str(value)


def run(root,expected):
    protocol=root/'protocol.json';assert sha(protocol)==expected;p=read(protocol)
    assert p['format']=='poloniex-fixed-future-replay-v1' and p['external_orders'] is False
    assert p['mode']=='observed_book_paper_replay' and p['actual_decision_commit_claimed'] is False
    assert p['registered_at_ns']<p['source_start_ns']+p['first_index']*MINUTE
    assert time.time_ns()<p['source_start_ns']+p['first_index']*MINUTE,'must launch before first future capture'
    assert 0<=p['first_index']<=p['last_index']<10080 and len(p['accounts'])==6
    source=Path(p['source_root']);assert sha(source/'protocol.json')==p['source_protocol_sha256']
    for name,h in p['files'].items():assert sha(root/name)==h
    lock=(root/'lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (root/'started.json').exists():raise RuntimeError('no silent restart or account reset')
    stop=threading.Event();signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    publish(root/'started.json',encode(dict(at_ns=time.time_ns(),pid=os.getpid(),protocol_sha256=expected)))
    native=Native(root/'observed_cycle.test');states={};previous=expected;reason='bounded_end';processed=0;gaps=0
    try:
        for index in range(p['first_index'],p['last_index']+1):
            scheduled=p['source_start_ns']+index*MINUTE;rp=source/f'minute_{index:05d}.receipt.json';gp=source/f'gap_{index:05d}.json'
            while not stop.is_set() and not rp.exists() and not gp.exists() and time.time_ns()<scheduled+180_000_000_000:
                heartbeat(root,next_index=index,processed=processed,gaps=gaps,status='waiting');stop.wait(10)
            if stop.is_set():reason='signal_stop';break
            assert sha(protocol)==expected and sha(source/'protocol.json')==p['source_protocol_sha256']
            for name,h in p['files'].items():assert sha(root/name)==h
            if shutil.disk_usage(root).free<20<<30:reason='free_storage_bound';break
            if sum(x.stat().st_size for x in root.glob('batch_*'))+(32<<20)>4<<30:reason='archive_storage_bound';break
            started=time.time_ns();proposals=[];packet=None
            if rp.exists():packet,provenance=load_capture(source,index,p)
            else:provenance=dict(reason='source_gap' if gp.exists() else 'source_not_published_within_180_seconds',source_index=index,scheduled_ns=scheduled)
            if packet is not None:
                packet['Accounts']=[dict(ID=a['id'],Config=a['config'],Before=states.get(a['id'])) for a in p['accounts']]
                for account in packet['Accounts']:
                    request={**account,'NowNS':packet['NowNS'],'Responses':packet['Responses']}
                    answer=native.apply(request)
                    if answer['CycleError'] not in ('','BitBank unavailable and no accepted fallback; entries paused'):raise RuntimeError(answer['CycleError'])
                    answer['MoneyCheck']=check_money(account['Before'],answer['State'],str(account['Config']['FeeRate']),packet['Responses'],packet['NowNS'])
                    answer['PostCycleBidEquity']=post_mark(answer['State'],packet['Responses'],packet['NowNS'])
                    proposals.append(answer)
            else:gaps+=1
            name=f'batch_{index:05d}';input_path=root/(name+'.input.json.gz');output_path=root/(name+'.output.json.gz')
            publish(input_path,gzip.compress(encode(dict(packet=packet,provenance=provenance)),mtime=0))
            publish(output_path,gzip.compress(encode(proposals),mtime=0))
            receipt=dict(source_index=index,previous_sha256=previous,input_sha256=sha(input_path),output_sha256=sha(output_path),computed_started_ns=started,
                computed_complete_ns=time.time_ns(),logical_ns=packet['NowNS'] if packet else None,source_available_before_compute=packet is None or packet['NowNS']<=started,
                actual_decision_commit_claimed=False,external_orders=False)
            assert receipt['source_available_before_compute']
            path=root/(name+'.receipt.json');publish(path,encode(receipt));previous=sha(path)
            for answer in proposals:states[answer['ID']]=answer['State']
            processed+=1;heartbeat(root,next_index=index+1,processed=processed,gaps=gaps,status='committed')
        publish(root/'stopped.json',encode(dict(at_ns=time.time_ns(),reason=reason,processed=processed,gaps=gaps,last_receipt_sha256=previous)))
        heartbeat(root,status='stopped',reason=reason,processed=processed,gaps=gaps)
    finally:native.close();lock.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--protocol-sha',required=True)
    args=parser.parse_args()
    try:run(args.root,args.protocol_sha)
    except BaseException:
        import traceback
        publish(args.root/('failure_'+str(time.time_ns())+'.json'),encode(dict(at_ns=time.time_ns(),error=traceback.format_exc(),external_orders=False)))
        raise
