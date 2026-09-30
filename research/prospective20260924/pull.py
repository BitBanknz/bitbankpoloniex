"""Read an immutable, bounded recorder prefix over the existing SSH connection."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time

REMOTE = '/nvme0n1-disk/code/bitbank-poloniex/data/public_retention_20260924_v1'


def pull(output, through):
    assert 0 <= through < 10080
    output.mkdir(parents=True, exist_ok=False)
    script = '''import base64,hashlib,json,os,time
from pathlib import Path
root=Path(REMOTE)
names=['protocol.json','PROTOCOL.md','recorder.py','test_recorder.py','validation.json','remote_tests.log','started.json','launch.json']
for index in range(THROUGH+1):
    stem=f'minute_{index:05d}'
    if (root/(stem+'.receipt.json')).exists():names += [stem+'.receipt.json',stem+'.jsonl.gz']
    else:names += [f'gap_{index:05d}.json']
files={}
for name in names:
    raw=(root/name).read_bytes()
    files[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'body_b64':base64.b64encode(raw).decode()}
heartbeat=json.loads((root/'heartbeat.json').read_text())
try:os.kill(heartbeat['pid'],0);alive=True
except ProcessLookupError:alive=False
print(json.dumps({'files':files,'at_ns':time.time_ns(),'heartbeat':heartbeat,'process_alive':alive,'failures':[p.name for p in root.glob('failure_*.json')],'stopped':(root/'stopped.json').exists()}))
'''.replace('REMOTE', repr(REMOTE)).replace('THROUGH', str(through))
    (output/'remote_read.py.txt').write_text(script)
    before=time.time_ns()
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','administrator@93.127.141.100','python3','-'],input=script.encode(),capture_output=True,timeout=60)
    after=time.time_ns()
    (output/'transfer.json').write_bytes(result.stdout)
    (output/'transfer.stderr').write_bytes(result.stderr)
    receipt={'request_ns':before,'received_ns':after,'returncode':result.returncode,'through':through,'remote':REMOTE,'transfer_sha256':hashlib.sha256(result.stdout).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/'transfer.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert result.returncode==0, result.stderr.decode()
    data=json.loads(result.stdout);dest=output/'mirror';dest.mkdir()
    for name,record in data['files'].items():
        assert Path(name).name==name
        raw=base64.b64decode(record['body_b64'],validate=True)
        assert len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['sha256']
        (dest/name).write_bytes(raw)
    print(json.dumps({'output':str(output),'files':len(data['files']),'heartbeat':data['heartbeat'],'process_alive':data['process_alive'],'failures':data['failures'],'stopped':data['stopped']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--through',type=int,required=True)
    args=parser.parse_args();pull(args.output,args.through)
