"""Native-engine synthetic publication test: healthy, missing quote, risk latch."""
from copy import deepcopy
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch
from build import HERE,REPO,OLD,OUT,sha,save
sys.path.insert(0,str(REPO/'research/futurecompare20260926'))
from reference import transition
from audit import BINARIES
from replay_v2 import synthetic,config

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    result_root=OUT/'integration';result_root.mkdir(exist_ok=False)
    proof=json.loads((OUT/'verification.json').read_text());assert proof['verified']
    assert all(sha(OUT/'worker'/name)==h for name,h in proof['worker_files'].items())
    save(result_root/'registration.json',dict(at_ns=time.time_ns(),script_sha256=sha(Path(__file__)),worker_verification_sha256=sha(OUT/'verification.json'),
        fixture='four logical minutes; second has unavailable AAA and observed BBB stop; third/fourth latch account risk',external_orders=False))
    now,base=synthetic();minutes=60_000_000_000
    old_module=module('old_fixture_worker',OLD/'shadow.py')
    candidate=module('candidate_fixture_worker',OUT/'worker/shadow.py')
    observed=[]
    for version,worker in [(1,old_module),(2,candidate)]:
        with tempfile.TemporaryDirectory(prefix='completed-cycle-',dir='/dev/shm') as directory:
            root=Path(directory);source=root/'public';source.mkdir();(source/'protocol.json').write_text('{"synthetic":true}\n')
            for i in range(4):(source/f'minute_{i:05d}.receipt.json').write_text('{"synthetic":true}\n')
            binary=root/'observed_cycle.test';shutil.copyfile(BINARIES['guarded'][0],binary);binary.chmod(0o700)
            accounts=[dict(id=('quote_aware' if aware else 'control')+'_fee'+str(round(float(fee)*10000)),config=config(aware,fee)) for fee in ('.003','.004','.006') for aware in (False,True)]
            p=dict(format=f'poloniex-fixed-future-replay-v{version}',external_orders=False,mode='observed_book_paper_replay',actual_decision_commit_claimed=False,
                registered_at_ns=now-180*1_000_000_000,source_start_ns=now,first_index=0,last_index=3,accounts=accounts,source_root=str(source),
                source_protocol_sha256=sha(source/'protocol.json'),files={'observed_cycle.test':sha(binary)})
            (root/'protocol.json').write_text(json.dumps(p));clock=[now-120*1_000_000_000];publish=worker.publish;packets={}
            def emit(path,raw):
                publish(path,raw)
                if path.name=='started.json':clock[0]=now+1_000_000_000
                elif path.name.startswith('batch_') and path.name.endswith('.receipt.json'):clock[0]+=minutes
            def capture(_source,index,_p):
                responses=deepcopy(base);logical=now+index*minutes
                for path,response in responses.items():
                    if path.endswith('/orderBook'):response['Body']['ts']=logical//1_000_000
                if index>0:responses['/markets/BBB_USDT/orderBook']['Body'].update(bids=['1','1000'],asks=['1.001','1000'])
                if index==1:responses['/markets/AAA_USDT/orderBook']=dict(Status=503,Body={})
                packets[index]=dict(NowNS=logical,Responses=responses)
                return packets[index],dict(synthetic=True,source_index=index)
            error=None
            with patch.object(worker.time,'time_ns',lambda:clock[0]),patch.object(worker,'publish',emit),patch.object(worker,'load_capture',capture):
                try:worker.run(root,sha(root/'protocol.json'))
                except RuntimeError as e:error=str(e)
            receipts=sorted(root.glob('batch_*.receipt.json'));expected=1 if version==1 else 4
            assert len(receipts)==expected,(version,len(receipts),error)
            if version==1:assert error=='held books unavailable (AAA_USDT); entries paused; protective stops checked'
            else:assert error is None and json.loads((root/'stopped.json').read_text())['reason']=='bounded_end'
            retained=result_root/f'worker_v{version}';retained.mkdir();states={};outcomes=[];previous=sha(root/'protocol.json');checks=0
            for path in root.iterdir():
                if path.is_file() and path.name!='observed_cycle.test':shutil.copyfile(path,retained/path.name)
            for i in range(expected):
                stem=f'batch_{i:05d}';r=json.loads((root/(stem+'.receipt.json')).read_text())
                assert r['previous_sha256']==previous and r['input_sha256']==sha(root/(stem+'.input.json.gz')) and r['output_sha256']==sha(root/(stem+'.output.json.gz'))
                previous=sha(root/(stem+'.receipt.json'))
                answers=json.loads(gzip.decompress((root/(stem+'.output.json.gz')).read_bytes()));assert len(answers)==6
                for spec,answer in zip(accounts,answers):
                    aid=spec['id'];packet=packets[i];v=transition(states.get(aid),answer['State'],spec['config']['FeeRate'],packet['Responses'],packet['NowNS'],True);checks+=1
                    states[aid]=answer['State']
                    if version==2:
                        kind=answer['CycleOutcome']['kind'];assert kind==['ready','incomplete_valuation','risk_halt','risk_halt'][i]
                        assert (answer['PostCycleBidEquity'] is None)==(i==1)
                        assert (v['equity'] is None)==(i==1)
                        outcomes.append(dict(index=i,account=aid,kind=kind,new_fills=len(v['new_fills']),equity=v['equity']))
            observed.append(dict(worker_version=version,committed_batches=len(receipts),account_money_checks=checks,error=error,outcomes=outcomes))
    save(result_root/'verification.json',dict(verified=True,at_ns=time.time_ns(),results=observed,script_sha256=sha(Path(__file__)),
        native_binary_sha256=sha(BINARIES['guarded'][0]),worker_verification_sha256=sha(OUT/'verification.json'),
        retained_files={str(p.relative_to(result_root)):sha(p) for p in result_root.rglob('*') if p.is_file()},
        synthetic_only=True,live_changed=False,existing_studies_changed=False))
    print(json.dumps(dict(verified=True,old_committed_batches=1,candidate_committed_batches=4,independent_money_checks=30)),flush=True)

if __name__=='__main__':main()
