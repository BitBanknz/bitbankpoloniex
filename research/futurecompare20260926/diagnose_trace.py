"""Retain exact replay attempts for the first stopped native path comparison."""
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from capture import OUT,HERE,sha,save
from audit import Bound,BINARIES
from native import Native

def main():
    output=OUT/'trace_2062';output.mkdir(exist_ok=False);bound=Bound()
    stored=bound.gz('unguarded/batch_02062.input.json.gz');answers=bound.gz('unguarded/batch_02062.output.json.gz')
    account=stored['packet']['Accounts'][1];expected=answers[1];assert account['ID']==expected['ID']=='quote_aware_fee30'
    request={**account,'NowNS':stored['packet']['NowNS'],'Responses':stored['packet']['Responses']}
    save(output/'registration.json',dict(at_ns=time.time_ns(),script_sha256=sha(Path(__file__)),native_binary_sha256=sha(BINARIES['unguarded'][0]),
        input_sha256=bound.digest('unguarded/batch_02062.input.json.gz'),output_sha256=bound.digest('unguarded/batch_02062.output.json.gz'),expected_paths=expected['Paths']))
    temp=Path(tempfile.mkdtemp(prefix='polo-trace-',dir='/dev/shm'));old_tmp=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    rows=[]
    try:
        for mode in ('reused_process','fresh_process'):
            native=Native(BINARIES['unguarded'][0]) if mode=='reused_process' else None
            try:
                for attempt in range(20):
                    if mode=='fresh_process':native=Native(BINARIES['unguarded'][0])
                    answer=native.apply(request)
                    if mode=='fresh_process':native.close()
                    differences=[k for k in ('ID','State','Report','Paused','CycleError') if answer[k]!=expected[k]]
                    row=dict(mode=mode,attempt=attempt,financial_differences=differences,paths_match=sorted(answer['Paths'])==sorted(expected['Paths']),paths=answer['Paths'])
                    rows.append(row);save(output/f'{mode}_{attempt:02d}.json',answer)
            finally:
                if mode=='reused_process':native.close()
    finally:
        if old_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=old_tmp
        shutil.rmtree(temp)
    save(output/'results.json',dict(at_ns=time.time_ns(),expected_paths=expected['Paths'],attempts=rows,
        all_financial_outputs_exact=all(not x['financial_differences'] for x in rows),exact_path_attempts=sum(x['paths_match'] for x in rows),
        hashes={p.name:sha(p) for p in output.iterdir() if p.is_file()}))
    print(json.dumps(dict(expected_paths=expected['Paths'],all_financial_outputs_exact=all(not x['financial_differences'] for x in rows),exact_path_attempts=sum(x['paths_match'] for x in rows),unique_actual_paths=sorted(set(tuple(sorted(x['paths'])) for x in rows)))),flush=True)

if __name__=='__main__':main()
