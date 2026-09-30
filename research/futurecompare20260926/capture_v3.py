"""Lossless transport: expand reproducible gzip members before stream compression.

Logical files and SHA256 hashes stay identical. Only public/archive reads remote.
"""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time
from capture import OUT,HERE,END,sha,save

def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)

def main():
    save(OUT/'capture_v3_registration.json',dict(at_ns=time.time_ns(),through_index=END,
        hashes={str(p):sha(p) for p in [Path(__file__),HERE/'capture.py',OUT/'registration.json',OUT/'remote_read.py.txt']},
        reason='preserve exact logical bytes while compressing repeated public metadata across batches'))
    script=(OUT/'remote_read.py.txt').read_text()
    script=replace(script,'import hashlib,io,json,os,pathlib,sys,tarfile,time','import gzip,hashlib,io,json,os,pathlib,subprocess,sys,tarfile,time')
    script=replace(script,"with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tar:","compressor=subprocess.Popen(['zstd','-q','-1','--long=24','-c'],stdin=subprocess.PIPE,stdout=sys.stdout.buffer)\nwith tarfile.open(fileobj=compressor.stdin,mode='w|') as tar:")
    script=replace(script,"manifest[arc]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()};raw(arc,data)","""manifest[arc]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'codec':'identity'}
  if name.endswith('.gz'):
   expanded=gzip.decompress(data)
   if gzip.compress(expanded,mtime=0)==data:
    manifest[arc]['codec']='gzip-mtime0';data=expanded
  raw(arc,data)""")
    script+="\ncompressor.stdin.close();assert compressor.wait()==0\n"
    (OUT/'remote_read_v3.py.txt').write_text(script)
    before=time.time_ns()
    with (OUT/'capture_v3.tar.zst').open('xb') as out,(OUT/'stderr_v3.txt').open('xb') as err:
        r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','administrator@93.127.141.100','python3','-'],input=script.encode(),stdout=out,stderr=err,timeout=1800)
    save(OUT/'transfer_v3.receipt.json',dict(request_ns=before,received_ns=time.time_ns(),returncode=r.returncode,
        archive_sha256=sha(OUT/'capture_v3.tar.zst'),archive_bytes=(OUT/'capture_v3.tar.zst').stat().st_size))
    assert r.returncode==0,(OUT/'stderr_v3.txt').read_text()
    expanded=OUT/'expanded_transport';expanded.mkdir()
    z=subprocess.Popen(['zstd','-q','-d','-c',str(OUT/'capture_v3.tar.zst')],stdout=subprocess.PIPE)
    with tarfile.open(fileobj=z.stdout,mode='r|') as tar:
        for item in tar:
            p=Path(item.name);assert item.isfile() and not p.is_absolute() and '..' not in p.parts and len(p.parts)<=2
            dest=expanded/p;dest.parent.mkdir(exist_ok=True)
            with dest.open('xb') as out:out.write(tar.extractfile(item).read())
    assert z.wait()==0
    manifest=json.loads((expanded/'manifest.json').read_text());mirror=OUT/'mirror';mirror.mkdir()
    for name,v in manifest.items():
        raw=(expanded/name).read_bytes()
        assert v['codec'] in ('identity','gzip-mtime0')
        if v['codec']=='gzip-mtime0':raw=gzip.compress(raw,mtime=0)
        assert len(raw)==v['bytes'] and hashlib.sha256(raw).hexdigest()==v['sha256'],name
        path=mirror/name;path.parent.mkdir(exist_ok=True)
        with path.open('xb') as f:f.write(raw)
        (expanded/name).unlink()
    for name in ('manifest.json','remote_status.json'):
        with (mirror/name).open('xb') as f:f.write((expanded/name).read_bytes())
    save(OUT/'capture.verified.json',dict(at_ns=time.time_ns(),verified=True,files=len(manifest),transport_version=3,
        manifest_sha256=sha(mirror/'manifest.json'),remote_status_sha256=sha(mirror/'remote_status.json'),
        archive_sha256=sha(OUT/'capture_v3.tar.zst'),registration_sha256=sha(OUT/'capture_v3_registration.json')))
    print(json.dumps(dict(captured_files=len(manifest),transport_bytes=(OUT/'capture_v3.tar.zst').stat().st_size,
        logical_bytes=sum(x['bytes'] for x in manifest.values()),status=json.loads((mirror/'remote_status.json').read_text()))),flush=True)

if __name__=='__main__':main()
