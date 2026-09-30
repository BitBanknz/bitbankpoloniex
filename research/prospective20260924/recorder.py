"""Bounded public-only Poloniex/BitBank receipt archive; no trading interfaces."""
import argparse
import base64
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
import urllib.error
import urllib.request

MINUTE=60_000_000_000
SYMBOLS=('BNB_USDT','ETC_USDT','ETH_USDT','PEPE_USDT','SUI_USDT','TRX_USDT','XRP_USDT','ZEC_USDT')
MAX_BODY=2<<20
MAX_BATCH=16<<20


def endpoints():
    return [('ranks','http://127.0.0.1:8745/api/trading-bot/rotation-signals'),
            ('markets','https://api.poloniex.com/markets'),('ticker24h','https://api.poloniex.com/markets/ticker24h')]+[
        ('book_'+s,'https://api.poloniex.com/markets/'+s+'/orderBook?limit=5') for s in SYMBOLS]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def fsync_dir(p):
    fd=os.open(p,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish(path,raw):
    path=Path(path)
    temporary=path.with_name(path.name+'.partial')
    if path.exists():raise RuntimeError('refusing to overwrite evidence')
    with temporary.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.link(temporary,path);temporary.unlink();fsync_dir(path.parent)


def heartbeat(root,value):
    temp=root/'heartbeat.tmp';temp.write_bytes(encode(value));os.replace(temp,root/'heartbeat.json')


def validate_protocol(p):
    assert p['format']=='poloniex-public-receipts-v1'
    assert p['symbols']==list(SYMBOLS) and p['endpoints']==[list(x) for x in endpoints()]
    assert p['slots']==10080 and p['period_ns']==MINUTE and p['slot_window_ns']==45_000_000_000
    assert p['end_exclusive_ns']==p['start_ns']+p['slots']*MINUTE
    assert p['start_ns']%MINUTE==15_000_000_000
    assert p['max_bytes']==2<<30 and p['minimum_free_bytes']==20<<30
    assert p['credentials_used'] is False and p['external_orders'] is False


def slot_action(now,at):
    return 'wait' if now<at else 'capture' if now<at+45_000_000_000 else 'gap'


def fetch(opener,name,url,timeout,clock=time.time_ns,monotonic=time.monotonic_ns):
    start=clock();begin=monotonic();status=None;error=None;raw=b'';oversize=False
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'TradingResearchPublicArchive/1','Accept':'application/json'},method='GET')
        try:response=opener.open(request,timeout=timeout)
        except urllib.error.HTTPError as exc:response=exc
        with response:
            status=response.status
            raw=response.read(MAX_BODY+1)
            if len(raw)>MAX_BODY:oversize=True;raw=raw[:MAX_BODY]
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    end=clock();finish=monotonic()
    stable=end>=start and abs((end-start)-(finish-begin))<=5_000_000_000
    return dict(name=name,url=url,method='GET',credentials_used=False,request_started_ns=start,response_received_ns=end,
        monotonic_started_ns=begin,monotonic_received_ns=finish,wall_clock_stable=stable,status=status,error=error,
        body_b64=base64.b64encode(raw).decode(),body_sha256=hashlib.sha256(raw).hexdigest(),body_bytes=len(raw),body_truncated=oversize)


def write_capture(root,index,scheduled,records,reason):
    name=f'minute_{index:05d}'
    raw=b''.join(encode(r) for r in records)
    archive=root/(name+'.jsonl.gz');publish(archive,gzip.compress(raw,mtime=0))
    receipt=dict(index=index,scheduled_ns=scheduled,archive=archive.name,archive_sha256=sha(archive),
        planned_requests=len(endpoints()),attempted_requests=len(records),complete=len(records)==len(endpoints()),
        all_responses_successful=len(records)==len(endpoints()) and all(r['status']==200 and r['error'] is None and r['wall_clock_stable'] and not r['body_truncated'] for r in records),
        complete_after_ns=time.time_ns(),reason=reason,
        first_request_ns=min((r['request_started_ns'] for r in records),default=None),
        last_receipt_ns=max((r['response_received_ns'] for r in records),default=None),
        request_receipt_times_are_observations=True,atomic_exchange_snapshot=False,credentials_used=False,external_orders=False)
    publish(root/(name+'.receipt.json'),encode(receipt))
    return receipt


def run(root,expected_protocol_sha):
    root=Path(root);protocol=root/'protocol.json'
    assert sha(protocol)==expected_protocol_sha
    p=json.loads(protocol.read_text());validate_protocol(p)
    source=Path(__file__).resolve()
    assert sha(source)==p['recorder_sha256']
    lock=(root/'lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (root/'started.json').exists():raise RuntimeError('archive already started; do not overwrite or silently restart')
    stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
    publish(root/'started.json',encode(dict(at_ns=time.time_ns(),pid=os.getpid(),protocol_sha256=expected_protocol_sha,recorder_sha256=sha(source))))
    used=sum(f.stat().st_size for f in root.iterdir() if f.is_file());reason='bounded_end';captures=gaps=0
    for index in range(p['slots']):
        scheduled=p['start_ns']+index*MINUTE
        while not stop.is_set() and time.time_ns()<scheduled:
            heartbeat(root,dict(at_ns=time.time_ns(),pid=os.getpid(),next_index=index,captures=captures,gaps=gaps,status='waiting'))
            stop.wait(min(20,max(0,(scheduled-time.time_ns())/1e9)))
        if stop.is_set():reason='signal_stop';break
        if sha(source)!=p['recorder_sha256'] or sha(protocol)!=expected_protocol_sha:reason='bound_input_changed';break
        if shutil.disk_usage(root).free<p['minimum_free_bytes']:reason='free_storage_bound';break
        if used+MAX_BATCH>p['max_bytes']:reason='archive_storage_bound';break
        if slot_action(time.time_ns(),scheduled)=='gap':
            path=root/f'gap_{index:05d}.json'
            publish(path,encode(dict(index=index,scheduled_ns=scheduled,observed_ns=time.time_ns(),reason='missed_capture_window',requests_made=0)))
            used+=path.stat().st_size;gaps+=1;continue
        records=[];batch_reason='complete';bytes_read=0
        deadline=time.monotonic()+max(0,(scheduled+45_000_000_000-time.time_ns())/1e9)
        for name,url in endpoints():
            left=deadline-time.monotonic()
            if stop.is_set():batch_reason='signal_stop';break
            if left<.25:batch_reason='capture_deadline';break
            r=fetch(opener,name,url,min(10,left));records.append(r);bytes_read+=r['body_bytes']
            heartbeat(root,dict(at_ns=time.time_ns(),pid=os.getpid(),next_index=index,captures=captures,gaps=gaps,status='capturing',requests=len(records)))
            if r['status'] in (418,429):batch_reason=reason='rate_limited';stop.set();break
            if not r['wall_clock_stable']:batch_reason=reason='wall_clock_discontinuity';stop.set();break
            if r['body_truncated'] or bytes_read>=MAX_BATCH:batch_reason=reason='response_size_bound';stop.set();break
            stop.wait(min(.5,max(0,deadline-time.monotonic())))
        write_capture(root,index,scheduled,records,batch_reason);captures+=1
        used=sum(f.stat().st_size for f in root.iterdir() if f.is_file())
        if stop.is_set():
            if reason=='bounded_end':reason='signal_stop'
            break
    publish(root/'stopped.json',encode(dict(at_ns=time.time_ns(),reason=reason,captures=captures,gaps=gaps,external_orders=False)))
    heartbeat(root,dict(at_ns=time.time_ns(),pid=os.getpid(),captures=captures,gaps=gaps,status='stopped',reason=reason))
    lock.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--protocol-sha',required=True)
    args=parser.parse_args()
    try:run(args.root,args.protocol_sha)
    except BaseException:
        import traceback
        publish(args.root/('failure_'+str(time.time_ns())+'.json'),encode(dict(at_ns=time.time_ns(),error=traceback.format_exc(),external_orders=False)))
        raise
