"""Read-only evidence that recovered consumers crossed the original failure."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
OUT = Path('/vfast/data/trading_research_20260924/poloniex_execution_wait_recovery_20260927_v1')
SCRIPT = '''import gzip,hashlib,io,json,sys,tarfile,time
from pathlib import Path
base=Path('/nvme0n1-disk/code/bitbank-poloniex/data');files={};status={};hearts={}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for label in ('unguarded','guarded'):
 root=base/('execution_wait_'+label+'_recovery_20260927_v1')
 assert sha(root/'protocol.json')==EXPECTED[label]
 h=json.loads((root/'heartbeat.json').read_bytes());hearts[label]=h
 assert h['next_index']>=175 and h['status'] in ('waiting','committed')
 assert not list(root.glob('failure_*.json')) and not (root/'stopped.json').exists()
 command=Path('/proc')/str(h['pid'])/'cmdline';assert command.is_file() and str(root).encode() in command.read_bytes()
last=min(v['next_index'] for v in hearts.values())-1
indices=list(range(172,last+1))
for label,name in [('source','public_retention_20260927_v1')]+[(v,'execution_wait_'+v+'_recovery_20260927_v1') for v in ('unguarded','guarded')]:
 root=base/name
 names=['protocol.json','started.json','launch.json','PROTOCOL.md']
 names+=['recorder.py'] if label=='source' else ['shadow.py','native.py','receipt_rules.py','outcomes.py','prefix.py','prefix_verified.json','tests.log']
 if label!='source':
  p=json.loads((root/'protocol.json').read_bytes());old=Path(p['original_root']);previous=sha(root/'protocol.json')
  for index in range(last+1):
   name=f'batch_{index:05d}';rp=root/(name+'.receipt.json');r=json.loads(rp.read_bytes())
   assert r['source_index']==index and r['previous_sha256']==previous and r['external_orders'] is False
   assert r['recovered_observed_data'] is True and r['actual_decision_commit_claimed'] is False
   for kind in ('input','output'):assert sha(root/(name+'.'+kind+'.json.gz'))==r[kind+'_sha256']
   if index<=172:
    assert r['original_prefix_check']==dict(verified=True,source_index=index,original_receipt_sha256=sha(old/(name+'.receipt.json')))
    for kind in ('input','output'):
     assert json.loads(gzip.decompress((root/(name+'.'+kind+'.json.gz')).read_bytes()))==json.loads(gzip.decompress((old/(name+'.'+kind+'.json.gz')).read_bytes()))
   else:assert r['original_prefix_check'] is None
   previous=sha(rp);names.append(rp.name)
  status[label]=dict(heartbeat=hearts[label],prefix_batches_verified=173,receipt_chain_verified_through=last,last_receipt_sha256=previous)
 else:
  h=json.loads((root/'heartbeat.json').read_bytes());command=Path('/proc')/str(h['pid'])/'cmdline'
  assert command.is_file() and str(root).encode() in command.read_bytes()
  status[label]=dict(heartbeat=h,failures=[p.name for p in root.glob('failure_*.json')])
 for index in indices:
  names += [f'minute_{index:05d}.receipt.json',f'minute_{index:05d}.jsonl.gz'] if label=='source' else [f'batch_{index:05d}.input.json.gz',f'batch_{index:05d}.output.json.gz']
 for name in names:
  p=root/name;assert p.is_file() and p.stat().st_size<16<<20;files[label+'/'+name]=p.read_bytes()
files['status.json']=(json.dumps(dict(at_ns=time.time_ns(),indices=indices,studies=status,remote_mutations=False),sort_keys=True)+'\\n').encode()
manifest={name:dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)) for name,raw in files.items()}
files['manifest.json']=(json.dumps(manifest,sort_keys=True)+'\\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for name,raw in files.items():
  member=tarfile.TarInfo(name);member.size=len(raw);member.mode=0o600;tar.addfile(member,io.BytesIO(raw))
'''


def main():
    launch = json.loads((OUT / 'remote_launch.json').read_text())
    expected = {label:value['sha256'] for label, value in launch['protocols'].items()}
    script = 'EXPECTED=' + repr(expected) + '\n' + SCRIPT
    folder = OUT / 'observation'
    folder.mkdir()
    (folder / 'remote_read.py.txt').write_text(script)
    began = time.time_ns()
    with (folder / 'snapshot.tar.gz').open('xb') as out, (folder / 'stderr.log').open('xb') as err:
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', 'administrator@93.127.141.100', 'python3 -'],
                                input=script.encode(), stdout=out, stderr=err, timeout=300)
    (folder / 'transport.json').write_text(json.dumps(dict(started_ns=began, ended_ns=time.time_ns(), returncode=result.returncode,
        script_sha256=hashlib.sha256(script.encode()).hexdigest(), archive_sha256=hashlib.sha256((folder / 'snapshot.tar.gz').read_bytes()).hexdigest())) + '\n')
    assert result.returncode == 0
    mirror = folder / 'mirror'
    mirror.mkdir()
    with tarfile.open(folder / 'snapshot.tar.gz', 'r:gz') as tar:
        members = tar.getmembers()
        assert len(members) < 21000 and len({m.name for m in members}) == len(members)
        for member in members:
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts and member.size < 16 << 20
            target = mirror / path
            target.parent.mkdir(exist_ok=True)
            with target.open('xb') as stream:
                stream.write(tar.extractfile(member).read())
    manifest = json.loads((mirror / 'manifest.json').read_text())
    assert set(manifest) == {str(p.relative_to(mirror)) for p in mirror.rglob('*') if p.is_file()} - {'manifest.json'}
    for name, value in manifest.items():
        raw = (mirror / name).read_bytes()
        assert len(raw) == value['bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256']
    (folder / 'verified.json').write_text(json.dumps(dict(verified=True, files=len(manifest),
        manifest_sha256=hashlib.sha256((mirror / 'manifest.json').read_bytes()).hexdigest()), sort_keys=True) + '\n')
    print('RECOVERY_OBSERVED', json.loads((mirror / 'status.json').read_text()), flush=True)


if __name__ == '__main__':
    main()
