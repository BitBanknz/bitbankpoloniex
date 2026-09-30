"""Read-only bounded remote public/paper capture; never touches live accounts."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time

HERE=Path(__file__).resolve().parent
OUT=Path('/vfast/data/trading_research_20260924/poloniex_future_prefix_3297_v1')
END=3297

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')

def main():
    OUT.mkdir(exist_ok=False)
    protocol=HERE.parents[1]/'docs/2026-09-26-future-prefix-comparison-protocol.md'
    save(OUT/'registration.json',dict(at_ns=time.time_ns(),through_index=END,
         hashes={str(p):sha(p) for p in [Path(__file__),protocol]},external_orders=False))
    script=r'''import hashlib,io,json,os,pathlib,sys,tarfile,time
parent=pathlib.Path('/nvme0n1-disk/code/bitbank-poloniex/data')
folders={'unguarded':'quote_aware_future_20260924_v1','guarded':'quote_aware_guarded_future_20260924_v1','source':'public_retention_20260924_v1'}
manifest={};status={};started=time.time_ns()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tar:
 def raw(name,data):
  ti=tarfile.TarInfo(name);ti.size=len(data);tar.addfile(ti,io.BytesIO(data))
 def add(label,name):
  path=parent/folders[label]/name;data=path.read_bytes();arc=label+'/'+name
  manifest[arc]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()};raw(arc,data)
 for label in ('unguarded','guarded','source'):
  root=parent/folders[label];p=json.loads((root/'protocol.json').read_text())
  names={'protocol.json','started.json','launch.json','validation.json','PROTOCOL.md'}
  if label=='source':
   names.update(['recorder.py','test_recorder.py','remote_tests.log'])
  else:
   names.update(p['files']);names.update(['SOURCE_VALIDATION.json','native_cases.jsonl.gz'])
  for name in sorted(names):add(label,name)
  if label=='source':
   for i in range(38,3298):
    if (root/f'minute_{i:05d}.receipt.json').exists():
     add(label,f'minute_{i:05d}.receipt.json');add(label,f'minute_{i:05d}.jsonl.gz')
    elif (root/f'gap_{i:05d}.json').exists():add(label,f'gap_{i:05d}.json')
  else:
   for i in range(p['first_index'],3298):
    for suffix in ('.receipt.json','.input.json.gz','.output.json.gz'):add(label,f'batch_{i:05d}'+suffix)
  hb=json.loads((root/'heartbeat.json').read_text())
  try:os.kill(hb['pid'],0);alive=True
  except ProcessLookupError:alive=False
  status[label]={'heartbeat':hb,'alive':alive,'stopped':(root/'stopped.json').exists(),'failures':[x.name for x in root.glob('failure_*.json')]}
 raw('manifest.json',(json.dumps(manifest,sort_keys=True)+'\n').encode())
 raw('remote_status.json',(json.dumps({'request_ns':started,'complete_ns':time.time_ns(),'workers':status})+'\n').encode())
'''
    (OUT/'remote_read.py.txt').write_text(script)
    before=time.time_ns()
    with (OUT/'capture.tar').open('xb') as out,(OUT/'stderr.txt').open('xb') as err:
        r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','administrator@93.127.141.100','python3','-'],input=script.encode(),stdout=out,stderr=err,timeout=1800)
    save(OUT/'transfer.receipt.json',dict(request_ns=before,received_ns=time.time_ns(),returncode=r.returncode,
        archive_sha256=sha(OUT/'capture.tar'),archive_bytes=(OUT/'capture.tar').stat().st_size))
    assert r.returncode==0,(OUT/'stderr.txt').read_text()
    mirror=OUT/'mirror';mirror.mkdir()
    with tarfile.open(OUT/'capture.tar','r|') as tar:
        for item in tar:
            p=Path(item.name);assert item.isfile() and not p.is_absolute() and '..' not in p.parts and len(p.parts)<=2
            dest=mirror/p;dest.parent.mkdir(exist_ok=True)
            with dest.open('xb') as out:out.write(tar.extractfile(item).read())
    manifest=json.loads((mirror/'manifest.json').read_text())
    for name,v in manifest.items():assert sha(mirror/name)==v['sha256'] and (mirror/name).stat().st_size==v['bytes'],name
    save(OUT/'capture.verified.json',dict(at_ns=time.time_ns(),verified=True,files=len(manifest),
         manifest_sha256=sha(mirror/'manifest.json'),remote_status_sha256=sha(mirror/'remote_status.json'),
         archive_sha256=sha(OUT/'capture.tar'),registration_sha256=sha(OUT/'registration.json')))
    print(json.dumps(dict(captured_files=len(manifest),bytes=(OUT/'capture.tar').stat().st_size,status=json.loads((mirror/'remote_status.json').read_text()))),flush=True)

if __name__=='__main__':main()
