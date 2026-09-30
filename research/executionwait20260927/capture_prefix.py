"""Read-only capture around the newly failed consumer boundary."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time

OUT = Path('/vfast/data/trading_research_20260924/poloniex_execution_wait_recovery_20260927_v1')
SCRIPT = '''import hashlib,io,json,sys,tarfile,time
from pathlib import Path
base=Path('/nvme0n1-disk/code/bitbank-poloniex/data');files={};status={}
for label,name in [('source','public_retention_20260927_v1'),('unguarded','completed_cycle_unguarded_future_20260927_v1'),('guarded','completed_cycle_guarded_future_20260927_v1')]:
 root=base/name
 names=['protocol.json','started.json','launch.json','PROTOCOL.md']
 names+=['recorder.py'] if label=='source' else ['shadow.py','native.py','receipt_rules.py','outcomes.py']
 names += [p.name for p in root.glob('failure_*.json')]
 for i in (range(175) if label=='source' else range(173)):
  names+=[f'minute_{i:05d}.receipt.json',f'minute_{i:05d}.jsonl.gz'] if label=='source' else [f'batch_{i:05d}.receipt.json',f'batch_{i:05d}.input.json.gz',f'batch_{i:05d}.output.json.gz']
 for name in names:
  p=root/name;assert p.is_file() and p.stat().st_size<16<<20;files[label+'/'+name]=p.read_bytes()
 status[label]={'heartbeat':json.loads((root/'heartbeat.json').read_text()),'failure_files':[p.name for p in root.glob('failure_*.json')]}
files['status.json']=(json.dumps({'at_ns':time.time_ns(),'studies':status},sort_keys=True)+'\\n').encode()
manifest={name:{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)} for name,raw in files.items()}
files['manifest.json']=(json.dumps(manifest,sort_keys=True)+'\\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for name,raw in files.items():
  member=tarfile.TarInfo(name);member.size=len(raw);member.mode=0o600;tar.addfile(member,io.BytesIO(raw))
'''


def main():
    folder = OUT / 'capture_v2'; folder.mkdir()
    (folder / 'remote_read.py.txt').write_text(SCRIPT)
    began = time.time_ns()
    with (folder / 'snapshot.tar.gz').open('xb') as out, (folder / 'stderr.log').open('xb') as err:
        p = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','administrator@93.127.141.100','python3 -'],
                           input=SCRIPT.encode(), stdout=out, stderr=err, timeout=600)
    receipt = dict(started_ns=began, ended_ns=time.time_ns(), returncode=p.returncode, remote_mutations=False,
                   archive_sha256=hashlib.sha256((folder / 'snapshot.tar.gz').read_bytes()).hexdigest(),
                   script_sha256=hashlib.sha256(SCRIPT.encode()).hexdigest())
    (folder / 'transfer.json').write_text(json.dumps(receipt, indent=2)+'\n'); assert p.returncode == 0
    mirror = folder / 'mirror'; mirror.mkdir()
    with tarfile.open(folder / 'snapshot.tar.gz', 'r:gz') as tar:
        members = tar.getmembers(); assert len(members) < 1500 and len({m.name for m in members}) == len(members)
        for m in members:
            path = Path(m.name); assert m.isfile() and not path.is_absolute() and '..' not in path.parts and m.size < 16 << 20
            target = mirror / path; target.parent.mkdir(exist_ok=True)
            with target.open('xb') as out: out.write(tar.extractfile(m).read())
    manifest = json.loads((mirror / 'manifest.json').read_text())
    assert set(manifest) == {str(p.relative_to(mirror)) for p in mirror.rglob('*') if p.is_file()} - {'manifest.json'}
    for name, value in manifest.items():
        raw = (mirror / name).read_bytes(); assert len(raw) == value['bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256']
    (folder / 'capture_verified.json').write_text(json.dumps(dict(verified=True, files=len(manifest), transfer=receipt,
         manifest_sha256=hashlib.sha256((mirror / 'manifest.json').read_bytes()).hexdigest()), indent=2)+'\n')
    print('RECOVERY_PREFIX_CAPTURED', len(manifest), flush=True)


if __name__ == '__main__': main()
