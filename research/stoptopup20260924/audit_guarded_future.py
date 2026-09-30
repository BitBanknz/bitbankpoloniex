"""Read and independently replay a fixed, already committed remote study prefix."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time
from build import OUT,HERE,sha,save,REPO
import sys
sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native
from replay_v2 import config,money

REMOTE='/nvme0n1-disk/code/bitbank-poloniex/data/quote_aware_guarded_future_20260924_v1'


def main(count,output):
    assert 1<=count<=120
    output.mkdir(exist_ok=False)
    script='''import base64,hashlib,json,os,time
from pathlib import Path
root=Path(REMOTE);p=json.loads((root/'protocol.json').read_text());source=Path(p['source_root'])
study=['protocol.json','validation.json','launch.json','started.json','shadow.py','native.py','receipt_rules.py','PROTOCOL.md']
sources=['protocol.json']
for index in range(p['first_index'],p['first_index']+COUNT):
    study.extend([f'batch_{index:05d}'+suffix for suffix in ['.input.json.gz','.output.json.gz','.receipt.json']])
    if (source/f'minute_{index:05d}.receipt.json').exists():sources.extend([f'minute_{index:05d}.receipt.json',f'minute_{index:05d}.jsonl.gz'])
    else:sources.append(f'gap_{index:05d}.json')
def copy(folder,names):
    result={}
    for name in names:
        raw=(folder/name).read_bytes();result[name]=dict(body_b64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
    return result
paired=Path('/nvme0n1-disk/code/bitbank-poloniex/data/quote_aware_future_20260924_v1')
paired_stem=f"batch_{p['first_index']-1:05d}"
hb=json.loads((root/'heartbeat.json').read_text())
try:os.kill(hb['pid'],0);alive=True
except ProcessLookupError:alive=False
print(json.dumps(dict(study_files=copy(root,study),source_files=copy(source,sources),paired_files=copy(paired,['protocol.json',paired_stem+'.receipt.json',paired_stem+'.output.json.gz']),binary_sha256=hashlib.sha256((root/'observed_cycle.test').read_bytes()).hexdigest(),at_ns=time.time_ns(),heartbeat=hb,alive=alive,failures=[p.name for p in root.glob('failure_*.json')],stopped=(root/'stopped.json').exists())))
'''.replace('REMOTE',repr(REMOTE)).replace('COUNT',str(count))
    (output/'remote_read.py.txt').write_text(script)
    before=time.time_ns();r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','administrator@93.127.141.100','python3','-'],input=script.encode(),capture_output=True,timeout=60);after=time.time_ns()
    (output/'transfer.json').write_bytes(r.stdout);(output/'stderr.txt').write_bytes(r.stderr)
    save(output/'transfer.receipt.json',dict(request_ns=before,received_ns=after,returncode=r.returncode,transfer_sha256=hashlib.sha256(r.stdout).hexdigest()))
    assert r.returncode==0,r.stderr.decode();transfer=json.loads(r.stdout)
    for kind in ('study','source','paired'):
        folder=output/kind;folder.mkdir()
        for name,v in transfer[kind+'_files'].items():
            assert Path(name).name==name;raw=base64.b64decode(v['body_b64'],validate=True);assert hashlib.sha256(raw).hexdigest()==v['sha256'];(folder/name).write_bytes(raw)
    root=output/'study';source=output/'source';p=json.loads((root/'protocol.json').read_text());first=p['first_index'];previous=sha(root/'protocol.json')
    started=json.loads((root/'started.json').read_text());validation=json.loads((root/'validation.json').read_text());launch=json.loads((root/'launch.json').read_text())
    assert started['protocol_sha256']==launch['protocol_sha256']==validation['protocol_sha256']==previous
    assert validation['verified'] and validation['remote_native_cycles']==55 and validation['independent_money_cycles']==55
    assert p['registered_at_ns']<=started['at_ns']<p['first_scheduled_ns']
    assert p['actual_decision_commit_claimed'] is False and p['external_orders'] is False and p['mode']=='observed_book_paper_replay'
    assert sha(source/'protocol.json')==p['source_protocol_sha256']
    for name,h in p['files'].items():
        if name=='observed_cycle.test':assert h==transfer['binary_sha256']==sha(OUT/'observed/engine.test')
        else:assert h==sha(root/name)
    expected_accounts=[]
    for fee in ('.003','.004','.006'):
        for aware in (False,True):expected_accounts.append(dict(id=('quote_aware' if aware else 'control')+'_fee'+str(round(float(fee)*10000)),config=config(aware,fee)))
    assert p['accounts']==expected_accounts
    paired=output/'paired';stem=f"batch_{first-1:05d}";pr=json.loads((paired/(stem+'.receipt.json')).read_text());po=paired/(stem+'.output.json.gz')
    assert pr['source_index']==first-1 and pr['output_sha256']==sha(po)
    ps=json.loads(gzip.decompress(po.read_bytes()));assert len(ps)==6
    assert all(a['State']['Cash']=='495' and not a['State']['Fills'] and not a['State']['Holdings'] and a['State']['Pending'] is None for a in ps)

    import receipt_rules as rules
    candidate=Native(OUT/'observed/engine.test');original=Native(OUT/'release_candidate/observed/engine.test')
    states={};native_cycles=original_cycles=0;new_fills=0
    try:
        for index in range(first,first+count):
            stem=f'batch_{index:05d}';receipt_path=root/(stem+'.receipt.json');receipt=json.loads(receipt_path.read_text())
            ip=root/(stem+'.input.json.gz');op=root/(stem+'.output.json.gz')
            assert receipt['source_index']==index and receipt['previous_sha256']==previous and receipt['input_sha256']==sha(ip) and receipt['output_sha256']==sha(op)
            assert receipt['actual_decision_commit_claimed'] is False and receipt['external_orders'] is False
            value=json.loads(gzip.decompress(ip.read_bytes()));answers=json.loads(gzip.decompress(op.read_bytes()));packet=value['packet'];proof=value['provenance']
            assert packet is not None,'this initial-prefix audit requires complete source batches'
            sr=source/f'minute_{index:05d}.receipt.json';sc=json.loads(sr.read_text());archive=source/sc['archive']
            assert proof['receipt_sha256']==sha(sr) and proof['archive_sha256']==sc['archive_sha256']==sha(archive)
            assert packet['NowNS']==sc['complete_after_ns']==receipt['logical_ns'] and packet['NowNS']<=receipt['computed_started_ns']<=receipt['computed_complete_ns']<=transfer['at_ns']
            records=[json.loads(line) for line in gzip.decompress(archive.read_bytes()).splitlines()]
            assert len(records)==11 and sc['complete']
            expected_responses={};last=sc['scheduled_ns']
            for record,endpoint in zip(records,rules.ENDPOINTS):
                raw_value=rules.decode_record(record,endpoint,last);last=record['response_received_ns']
                path='/prediction' if record['name']=='ranks' else record['url'].split('api.poloniex.com',1)[1].split('?',1)[0]
                expected_responses[path]=dict(Status=record['status'],Body=raw_value) if raw_value is not None else dict(Status=503,Body={})
            assert packet['Responses']==expected_responses and last<=packet['NowNS']
            assert len(packet['Accounts'])==len(answers)==6
            for spec,account,answer in zip(p['accounts'],packet['Accounts'],answers):
                assert account==dict(ID=spec['id'],Config=spec['config'],Before=states.get(spec['id'])) and answer['ID']==spec['id']
                request={**account,'NowNS':packet['NowNS'],'Responses':packet['Responses']};reproduced=candidate.apply(request)
                for key in ('ID','State','Report','Paused','CycleError'):assert reproduced[key]==answer[key],(index,spec['id'],key)
                assert sorted(reproduced['Paths'])==sorted(answer['Paths']);native_cycles+=1
                if not spec['config']['QuoteAwareEntry']:
                    reference=original.apply(request)
                    for key in ('ID','State','Report','Paused','CycleError'):assert reference[key]==answer[key]
                    original_cycles+=1
                new_fills+=money(account['Before'],answer['State'],spec['config']['FeeRate']);states[spec['id']]=answer['State']
            previous=sha(receipt_path)
    finally:candidate.close();original.close()
    assert all(s['Cash']=='495' and not s['Fills'] and not s['Holdings'] for s in states.values()),'initial off-window prefix unexpectedly traded'
    report=dict(verified=True,at_ns=time.time_ns(),first_index=first,through_index=first+count-1,source_batches=count,native_cycles=native_cycles,release_guard_control_cycles=original_cycles,
        fills=new_fills,accounts=len(states),all_cash_per_account='495',raw_sources_and_hash_chain_verified=True,registered_and_started_before_first_capture=True,unguarded_reference_flat_at_common_start=True,reference_preceding_index=first-1,
        actual_decision_commit_claimed=False,prospective_profitability_established=False,remote_heartbeat=transfer['heartbeat'],remote_alive=transfer['alive'],remote_failures=transfer['failures'],remote_stopped=transfer['stopped'],
        hashes={str(f):sha(f) for f in [Path(__file__),output/'transfer.json',output/'transfer.receipt.json',OUT/'validation.json',REPO/'research/quoteaware20260924/replay_v2.py',REPO/'research/quoteaware20260924/receipt_rules.py']})
    save(output/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='hashes'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();main(args.count,args.output)
