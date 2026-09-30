"""Same full native/account checks; two independent studies run concurrently."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import getcontext,setcontext
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
from decimal import Decimal as D
from capture import HERE,OUT,END,sha,save
from reference import transition,rules
from transport import ReplayNative as Native,encode
from replay_v2 import config
from trace_evidence import TraceEvidence,TRACE

BASE=OUT.parent
BINARIES={
 'unguarded':(BASE/'poloniex_quote_aware_v1/driver/candidate/observed_cycle.test',BASE/'poloniex_quote_aware_v1/driver/original/observed_cycle.test'),
 'guarded':(BASE/'poloniex_stop_topup_guard_v1/observed/engine.test',BASE/'poloniex_stop_topup_guard_v1/release_candidate/observed/engine.test')}
BUILD_PROOFS=[BASE/'poloniex_quote_aware_v1/driver/verification.json',BASE/'poloniex_stop_topup_guard_v1/observed/verification.json',BASE/'poloniex_stop_topup_guard_v1/release_candidate/observed/verification.json']
PROTOCOL_HASHES={'source':'f6c627405f80ade06457c6d659a031834e3b6f50acf17b7317d2cf39538b23c4',
 'unguarded':'a1ad7dbfd6a5fc8d72102ea78c5bb1833ae90e4c5250c2facaca155f6bf569ca',
 'guarded':'62cd81e7cbe73206e8fcca841c98c268bcc18e523b9e9379866f81f71fce9e10'}
read=lambda p:json.loads(Path(p).read_bytes())

class Bound:
    def __init__(self):
        self.root=OUT/'mirror';v=read(OUT/'capture.verified.json');assert v['verified']
        version=v.get('transport_version',1)
        registration=OUT/(f'capture_v{version}_registration.json' if version>1 else 'registration.json')
        archive=OUT/(f'capture_v{version}.tar.zst' if version>1 else 'capture.tar')
        assert sha(registration)==v['registration_sha256'] and sha(archive)==v['archive_sha256']
        assert sha(self.root/'manifest.json')==v['manifest_sha256'] and sha(self.root/'remote_status.json')==v['remote_status_sha256']
        self.manifest=read(self.root/'manifest.json');self.checked=set()
    def raw(self,name):
        raw=(self.root/name).read_bytes();v=self.manifest[name]
        assert len(raw)==v['bytes'] and hashlib.sha256(raw).hexdigest()==v['sha256'],name
        self.checked.add(name);return raw
    def json(self,name):return json.loads(self.raw(name))
    def gz(self,name):return json.loads(gzip.decompress(self.raw(name)))
    def digest(self,name):return hashlib.sha256(self.raw(name)).hexdigest()

def source_protocol(bound):
    p=bound.json('source/protocol.json');v=bound.json('source/validation.json');s=bound.json('source/started.json');launch=bound.json('source/launch.json')
    assert bound.digest('source/protocol.json')==PROTOCOL_HASHES['source']
    assert p['format']=='poloniex-public-receipts-v1' and p['symbols']==list(rules.SYMBOLS)
    assert p['endpoints']==[list(x) for x in rules.ENDPOINTS] and p['slots']==10080 and p['period_ns']==rules.MINUTE and p['slot_window_ns']==45_000_000_000
    assert not p['credentials_used'] and not p['external_orders']
    assert p['end_exclusive_ns']==p['start_ns']+10080*rules.MINUTE
    assert s['protocol_sha256']==launch['protocol_sha256']==bound.digest('source/protocol.json')
    assert s['recorder_sha256']==p['recorder_sha256']==bound.digest('source/recorder.py')
    assert bound.digest('source/PROTOCOL.md')==p['protocol_document_sha256']
    assert v['verified'] and v['tests']==11 and v['at_ns']<s['at_ns']<p['start_ns']
    for path,h in v['hashes'].items():assert bound.digest('source/'+Path(path).name)==h
    return p

def capture(bound,index,p,transfer_ns):
    scheduled=p['start_ns']+index*rules.MINUTE;stem='source/minute_'+f'{index:05d}'
    if stem+'.receipt.json' not in bound.manifest:
        name='source/gap_'+f'{index:05d}'+'.json'
        if name in bound.manifest:
            g=bound.json(name);assert g['index']==index and g['scheduled_ns']==scheduled and g['requests_made']==0
            assert g['observed_ns']>=scheduled+45_000_000_000
            return None,dict(reason='source_gap',source_index=index,scheduled_ns=scheduled),dict(requests=0)
        return None,dict(reason='source_not_published_within_180_seconds',source_index=index,scheduled_ns=scheduled),dict(requests=0)
    receipt=bound.json(stem+'.receipt.json');archive='source/'+receipt['archive']
    assert receipt['archive']==f'minute_{index:05d}.jsonl.gz' and receipt['index']==index and receipt['scheduled_ns']==scheduled
    raw=bound.raw(archive);assert hashlib.sha256(raw).hexdigest()==receipt['archive_sha256']
    records=[json.loads(x) for x in gzip.decompress(raw).splitlines()]
    assert receipt['attempted_requests']==len(records)<=11 and receipt['planned_requests']==11 and receipt['complete']==(len(records)==11)
    assert not receipt['credentials_used'] and not receipt['external_orders'] and not receipt['atomic_exchange_snapshot']
    responses={};statuses={};previous=scheduled
    for record,endpoint in zip(records,rules.ENDPOINTS):
        assert scheduled<=record['request_started_ns']<scheduled+45_000_000_000
        value=rules.decode_record(record,endpoint,previous);previous=record['response_received_ns']
        path='/prediction' if record['name']=='ranks' else record['url'].split('api.poloniex.com',1)[1].split('?',1)[0]
        responses[path]=dict(Status=record['status'],Body=value) if value is not None else dict(Status=503,Body={})
        statuses[record['name']]=record['status']
    assert receipt['first_request_ns']==min((x['request_started_ns'] for x in records),default=None)
    assert receipt['last_receipt_ns']==max((x['response_received_ns'] for x in records),default=None)
    assert previous<=receipt['complete_after_ns']<=transfer_ns
    successful=len(records)==11 and all(x['status']==200 and x['error'] is None and x['wall_clock_stable'] and not x['body_truncated'] for x in records)
    assert receipt['all_responses_successful']==successful
    reason=None
    if len(records)!=11:reason='incomplete_source_capture'
    elif not all(x['wall_clock_stable'] for x in records):reason='unstable_source_clock'
    elif any(responses[x]['Status']!=200 for x in ('/markets','/markets/ticker24h')):reason='market_metadata_unavailable'
    metadata=dict(requests=len(records),successful=successful,rank_available=False,rank_scores=None)
    if reason:return None,dict(reason=reason,receipt=receipt),metadata
    scores=rules.ranks_at(responses['/prediction']['Body'],receipt['complete_after_ns']) if responses['/prediction']['Status']==200 else None
    assert not scores or set(scores)<=set(rules.SYMBOLS)
    rank_response=responses['/prediction'];rank_body=rank_response['Body']
    metadata.update(rank_available=bool(scores),rank_scores=None if not scores else {s:str(v) for s,v in scores.items()},
        rank_endpoint_status=rank_response['Status'],rank_body_available=rank_body.get('available'),
        rank_issued_at=rank_body.get('issued_at'),rank_execution_hour=rank_body.get('execution_hour'))
    proof=dict(receipt_sha256=bound.digest(stem+'.receipt.json'),archive_sha256=receipt['archive_sha256'],source_index=index,
        scheduled_ns=scheduled,available_at_ns=receipt['complete_after_ns'],statuses=statuses,actual_decision_commit_claimed=False)
    return dict(NowNS=receipt['complete_after_ns'],Responses=responses),proof,metadata

def study_protocol(bound,label,source):
    path=label+'/';p=bound.json(path+'protocol.json');v=bound.json(path+'validation.json');s=bound.json(path+'started.json');launch=bound.json(path+'launch.json')
    digest=bound.digest(path+'protocol.json')
    assert digest==PROTOCOL_HASHES[label]
    assert s['protocol_sha256']==v['protocol_sha256']==launch['protocol_sha256']==digest
    count=50 if label=='unguarded' else 55
    assert v['verified'] and v['remote_native_cycles']==count and v['independent_money_cycles']==count
    assert p['registered_at_ns']<=s['at_ns']<p['first_scheduled_ns']==source['start_ns']+p['first_index']*rules.MINUTE
    assert p['first_index']==(38 if label=='unguarded' else 78) and p['last_index']==10079
    assert not p['external_orders'] and not p['actual_decision_commit_claimed'] and p['mode']=='observed_book_paper_replay'
    assert p['source_protocol_sha256']==bound.digest('source/protocol.json') and p['source_start_ns']==source['start_ns']
    for name,h in p['files'].items():assert bound.digest(path+name)==h
    assert p['files']['observed_cycle.test']==sha(BINARIES[label][0])
    for name,h in v['files'].items():assert bound.digest(path+name)==h
    expected=[]
    for fee in ('.003','.004','.006'):
        for aware in (False,True):expected.append(dict(id=('quote_aware' if aware else 'control')+'_fee'+str(round(float(fee)*10000)),config=config(aware,fee)))
    assert p['accounts']==expected
    return p,digest

def metric_init():
    return dict(cycles=0,marked=0,unmarked=0,held_cycles=0,fees=D(0),turnover=D(0),fills=0,dust_count=0,dust_value=D(0),
         below_stop_buys=0,peak=D(495),max_drawdown_pct=D(0),last_equity=None,max_gross_fraction=D(0),unmarked_indices=[])

def metric_add(m,v,state,index):
    m['cycles']+=1;m['held_cycles']+=bool(state['Holdings']);m['fills']+=len(v['new_fills']);m['fees']+=D(v['fees']);m['turnover']+=D(v['turnover'])
    m['dust_count']+=len(v['dust']);m['dust_value']+=sum((D(x['value']) for x in v['dust']),D(0));m['below_stop_buys']+=len(v['below_stop_buys'])
    m['last_equity']=v['equity']
    if v['equity'] is None:
        m['unmarked']+=1;m['unmarked_indices'].append(index);return
    e=D(v['equity']);m['marked']+=1;m['peak']=max(m['peak'],e);m['max_drawdown_pct']=max(m['max_drawdown_pct'],(1-e/m['peak'])*100)
    m['max_gross_fraction']=max(m['max_gross_fraction'],(e-D(state['Cash']))/e)

def main(through=END,output=OUT/'completed_v2/audit'):
    assert 78<=through<=END
    output.mkdir(parents=True,exist_ok=False)
    inputs=[Path(__file__),HERE/'capture.py',HERE/'capture_v2.py',HERE/'capture_v3.py',HERE/'reference.py',HERE/'test_reference.py',Path(rules.__file__),Path(sys.modules['native'].__file__),Path(sys.modules['replay_v2'].__file__),OUT/'registration.json',OUT/'capture_v3_registration.json',OUT/'transfer_v3.receipt.json',OUT/'capture.verified.json']+[p for pair in BINARIES.values() for p in pair]
    inputs+=BUILD_PROOFS+[HERE/'transport.py',HERE/'test_transport.py',HERE/'trace_evidence.py',HERE/'test_trace_evidence.py',TRACE/'verification.json',OUT/'recorded_trace_inventory.json',HERE.parents[1]/'docs/2026-09-26-native-trace-reconstruction-protocol.md']
    hashes={str(p):sha(p) for p in inputs};save(output/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,through_index=through))
    pinned={}
    for proof in BUILD_PROOFS:
        v=read(proof);assert v['verified'];pinned.update(v['hashes'])
    for pair in BINARIES.values():
        for binary in pair:assert pinned[str(binary)]==sha(binary)
    trace_evidence=TraceEvidence(output)
    bound=Bound();source=source_protocol(bound);status=read(bound.root/'remote_status.json');protocols={};previous={};states={'unguarded':{},'guarded':{}}
    for label in states:protocols[label],previous[label]=study_protocol(bound,label,source)
    natives={label:tuple(Native(p) for p in pair) for label,pair in BINARIES.items()}
    metrics={label:{a['id']:metric_init() for a in p['accounts']} for label,p in protocols.items()}
    cycles={label:0 for label in states};controls=cycles.copy();gaps=cycles.copy();requests=rank_minutes=successful_sources=0;first_diff={};max_compute_lag_ns=0
    def process_study(label,p,index,packet,proof):
        rows=[];current={};lag=0
        if index<p['first_index']:return [],{},0
        stem=label+'/batch_'+f'{index:05d}';r=bound.json(stem+'.receipt.json');stored=bound.gz(stem+'.input.json.gz');answers=bound.gz(stem+'.output.json.gz')
        assert r['source_index']==index and r['previous_sha256']==previous[label]
        assert r['input_sha256']==bound.digest(stem+'.input.json.gz') and r['output_sha256']==bound.digest(stem+'.output.json.gz')
        assert not r['external_orders'] and not r['actual_decision_commit_claimed'] and r['source_available_before_compute']
        assert r['computed_started_ns']<=r['computed_complete_ns']<=status['complete_ns']
        assert stored['provenance']==proof
        previous[label]=bound.digest(stem+'.receipt.json')
        if packet is None:
            assert stored['packet'] is None and answers==[] and r['logical_ns'] is None;gaps[label]+=1
            if proof['reason']=='source_not_published_within_180_seconds':assert r['computed_started_ns']>=proof['scheduled_ns']+180_000_000_000
            for a in p['accounts']:
                m=metrics[label][a['id']];m['unmarked']+=1;m['unmarked_indices'].append(index);m['last_equity']=None
            return rows,current,lag
        assert r['logical_ns']==packet['NowNS']<=r['computed_started_ns']
        lag=max(lag,r['computed_complete_ns']-packet['NowNS'])
        expected={**packet,'Accounts':[dict(ID=a['id'],Config=a['config'],Before=states[label].get(a['id'])) for a in p['accounts']]}
        assert stored['packet']==expected and len(answers)==6
        for spec,account,answer in zip(p['accounts'],expected['Accounts'],answers):
            aid=spec['id'];assert answer['ID']==aid
            request={**account,'NowNS':packet['NowNS'],'Responses':packet['Responses']}
            reproduced=natives[label][0].apply(request)
            for k in ('ID','State','Report','Paused','CycleError'):assert reproduced[k]==answer[k],(label,index,aid,k)
            trace_evidence.verify(reproduced,answer,request,label,index,aid,'candidate');cycles[label]+=1
            if not spec['config']['QuoteAwareEntry']:
                original=natives[label][1].apply(request)
                for k in ('ID','State','Report','Paused','CycleError'):assert original[k]==answer[k],(label,index,aid,'baseline',k)
                trace_evidence.verify(original,answer,request,label,index,aid,'baseline');controls[label]+=1
            v=transition(account['Before'],answer['State'],spec['config']['FeeRate'],packet['Responses'],packet['NowNS'],label=='guarded')
            assert (None if v['equity'] is None else D(v['equity']))==(None if answer['PostCycleBidEquity'] is None else D(answer['PostCycleBidEquity']))
            mc=answer['MoneyCheck'];assert mc['new_fills']==len(v['new_fills']) and D(mc['cash'])==D(v['cash']) and sorted(mc['dust_drops'])==sorted(x['symbol'] for x in v['dust'])
            states[label][aid]=answer['State'];metric_add(metrics[label][aid],v,answer['State'],index)
            rows.append(dict(study=label,account=aid,index=index,now_ns=packet['NowNS'],**v))
            current[label,aid]=v
            if index<=77:assert answer['State']['Cash']=='495' and not answer['State']['Holdings'] and not answer['State']['Fills'] and answer['State']['Pending'] is None
        return rows,current,lag

    decimal_context=getcontext().copy()
    pool=ThreadPoolExecutor(max_workers=2,initializer=lambda:setcontext(decimal_context.copy()))
    with (output/'paths.jsonl').open('x') as paths,(output/'sources.jsonl').open('x') as sources:
      try:
        for index in range(38,through+1):
            packet,proof,source_meta=capture(bound,index,source,status['complete_ns'])
            if packet is not None:
                encoded=encode(packet['Responses'])
                for pair in natives.values():
                    for native in pair:native.set_responses(packet['Responses'],encoded)
            sources.write(json.dumps(dict(index=index,**source_meta),sort_keys=True)+'\n')
            requests+=source_meta['requests'];rank_minutes+=source_meta.get('rank_available',False);successful_sources+=source_meta.get('successful',False)
            current={}
            futures=[pool.submit(process_study,label,p,index,packet,proof) for label,p in protocols.items()]
            for future in futures:
                rows,accounting,lag=future.result()
                for row in rows:paths.write(json.dumps(row,sort_keys=True)+'\n')
                current.update(accounting);max_compute_lag_ns=max(max_compute_lag_ns,lag)
            if index>=78:
                for aid in states['guarded']:
                    a=current.get(('unguarded',aid));b=current.get(('guarded',aid))
                    if a!=b and aid not in first_diff:first_diff[aid]=index
            if packet is not None:assert encoded==encode(packet['Responses']),'public input mutated during audit'
            if index%100==0:print(json.dumps(dict(index=index,native_cycles=sum(cycles.values()),baseline_cycles=sum(controls.values()),peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)),flush=True)
      finally:
        pool.shutdown(wait=True)
        for pair in natives.values():
            for native in pair:native.close()
    summary={}
    for label,accounts in metrics.items():
        summary[label]={}
        for aid,m in accounts.items():
            m.update(final_cash=states[label][aid]['Cash'],final_holdings=states[label][aid]['Holdings'],halted=states[label][aid]['Halted'])
            e=m['last_equity'];m['return_pct']=None if e is None else (D(e)/495-1)*100
            m['complete_marked_path']=m['unmarked']==0 and gaps[label]==0
            summary[label][aid]={k:str(v) if isinstance(v,D) else v for k,v in m.items()}
    save(output/'summary.json',summary);save(output/'final_states.json',states)
    assert all(sha(p)==h for p,h in hashes.items()),'audit inputs changed'
    # Include every transfer file, even prelaunch fixtures not needed by replay.
    for name in bound.manifest:
        if name not in bound.checked:bound.raw(name)
    result=dict(verified=True,at_ns=time.time_ns(),trace_reconstructions=trace_evidence.records,first_index=38,common_first_index=78,through_index=through,native_cycles=cycles,baseline_cycles=controls,
        gaps=gaps,source_requests=requests,fully_successful_sources=successful_sources,source_rank_available_minutes=rank_minutes,
        first_guard_accounting_difference=first_diff,max_computation_lag_ns=max_compute_lag_ns,files_checked=len(bound.checked),
        registered_before_capture=True,unguarded_flat_through_77=True,study_complete=False,profitability_established=False,deployment_qualified=False,
        actual_decision_commit_claimed=False,external_orders=False,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,workers_at_capture=status['workers'],hashes=hashes,
        output_hashes={p.name:sha(p) for p in output.iterdir() if p.is_file()})
    save(output/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('hashes','output_hashes')}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--through',type=int,default=END);parser.add_argument('--output',type=Path,default=OUT/'completed_v2/audit');args=parser.parse_args();main(args.through,args.output)
