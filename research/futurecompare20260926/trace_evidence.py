"""One explicitly evidenced non-engine HTTP event; never relax financial checks."""
import hashlib
import json
from pathlib import Path
import time
from capture import OUT,sha,save
from transport import OriginalNative as Native

TRACE=OUT.parent/'poloniex_driver_trace_isolation_v3'
KEYS=('ID','State','Report','Paused','CycleError')
ALLOWED=('unguarded',2062,'quote_aware_fee30','candidate')

class TraceEvidence:
    def __init__(self,output):
        self.output=output/'trace_reconstructions';self.output.mkdir()
        self.proof=json.loads((TRACE/'verification.json').read_text());assert self.proof['verified'] and self.proof['recorded_root_trace_reproduced']
        assert self.proof['source_engine_unchanged'] and self.proof['all_financial_fields_exact']
        for name,h in self.proof['artifact_hashes'].items():assert sha(TRACE/name)==h
        inventory=json.loads((OUT/'recorded_trace_inventory.json').read_text())
        assert inventory['all_saved_outputs_checked'] and inventory['unrequested_paths']==[dict(study='unguarded',index=2062,account='quote_aware_fee30',paths=['/'])]
        self.records=[]
    def verify(self,actual,expected,request,label,index,account,role):
        for key in KEYS:assert actual[key]==expected[key],('financial mismatch',key)
        if sorted(actual['Paths'])==sorted(expected['Paths']):return
        assert (label,index,account,role)==ALLOWED,('unexplained request trace',label,index,account,role)
        assert expected['Paths'].count('/')==1 and '/' not in actual['Paths']
        assert sorted(actual['Paths'])==sorted(p for p in expected['Paths'] if p!='/'),'engine endpoint trace differs'
        native=Native(TRACE/'probe_original/engine.test')
        try:reconstructed=native.apply({**request,'ProbeRoot':True})
        finally:native.close()
        for key in KEYS:assert reconstructed[key]==expected[key],('controlled reconstruction financial mismatch',key)
        assert sorted(reconstructed['Paths'])==sorted(expected['Paths']) and reconstructed['ProbeStatuses']==[503]
        record=dict(at_ns=time.time_ns(),study=label,index=index,account=account,role=role,
            request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            original_native_answer=actual,recorded_expected_answer=expected,controlled_probe_answer=reconstructed,
            all_financial_fields_exact=True,complete_recorded_trace_reproduced=True,original_probe_sender_unknown=True,
            controlled_probe_binary_sha256=sha(TRACE/'probe_original/engine.test'),trace_verification_sha256=sha(TRACE/'verification.json'))
        path=self.output/f'{label}_{index:05d}_{account}_{role}.json';save(path,record)
        self.records.append(dict(file=str(path),sha256=sha(path),index=index,account=account))
