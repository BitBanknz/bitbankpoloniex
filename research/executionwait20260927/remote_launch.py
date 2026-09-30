"""Install paper recovery beside failed consumers; reuse the public recorder."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

BASE = Path('/nvme0n1-disk/code/bitbank-poloniex/data')
SOURCE = BASE / 'public_retention_20260927_v1'
OLD = {name:BASE / ('completed_cycle_' + name + '_future_20260927_v1') for name in ('unguarded', 'guarded')}
NEW = {name:BASE / ('execution_wait_' + name + '_recovery_20260927_v1') for name in OLD}
PACKAGE = BASE / 'research_execution_wait_20260927_v1'
SOURCE_SHA = '04f495b23286742ccdb988239bcf01e400d47f2d9c5646a6cc2396b19dc2fce3'
OLD_SHA = dict(unguarded='da999ec13be6fe92fbbe0113d8cbac5d58535c097976fc7b5f6e2d1c71ceac3a',
               guarded='1396dc8a9511bd1163f63c9c2468e36cba2e840bf8edb9ab2a33902c33a308f3')
LAST_SHA = dict(unguarded='4b869ccee725e2d6d72d09907be1197ca580893ebb7379678642ac708ce2c16f',
                guarded='49e3b050cf0b65e0c02c93281050893fd29dbe803ce2c1777626bf093b862cb4')
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
encode = lambda v:(json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def write(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def inventory(root):
    values = {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    return dict(files=len(values), manifest_sha256=hashlib.sha256(encode(values)).hexdigest())


def main(payload_b64, expected_archive):
    archive = base64.b64decode(payload_b64, validate=True)
    assert hashlib.sha256(archive).hexdigest() == expected_archive
    assert all(not p.exists() for p in [PACKAGE, *NEW.values()])
    assert shutil.disk_usage(BASE).free >= 30 << 30
    assert sha(SOURCE / 'protocol.json') == SOURCE_SHA
    source_protocol = json.loads((SOURCE / 'protocol.json').read_text())
    source_start = json.loads((SOURCE / 'started.json').read_text())
    source_cmd = Path('/proc') / str(source_start['pid']) / 'cmdline'
    assert source_cmd.is_file() and str(SOURCE).encode() in source_cmd.read_bytes()
    allowed = {'PROTOCOL.md', 'prefix_verified.json', 'tests.log', 'manifest.json'} | {
        'worker/' + n for n in ('shadow.py', 'native.py', 'receipt_rules.py', 'outcomes.py', 'prefix.py')}
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        members = tar.getmembers()
        assert len(members) == len(allowed) and {m.name for m in members} == allowed
        for member in members:
            assert member.isfile() and member.size < 256 << 10
            files[member.name] = tar.extractfile(member).read()
    manifest = json.loads(files['manifest.json'])
    assert set(manifest) == allowed - {'manifest.json'}
    for name, digest in manifest.items():
        assert hashlib.sha256(files[name]).hexdigest() == digest
    assert b'Ran 12 tests' in files['tests.log'] and files['tests.log'].rstrip().endswith(b'OK')
    proof = json.loads(files['prefix_verified.json'])
    for filename in ('shadow.py', 'native.py', 'receipt_rules.py', 'outcomes.py', 'prefix.py'):
        bound = '/vfast/data/code/bitbankpoloniex/research/executionwait20260927/worker/' + filename
        assert proof['source_hashes'][bound] == manifest['worker/' + filename]
    namespace = {'__name__':'recovery_prefix_preflight'}
    exec(compile(files['worker/prefix.py'], 'verified_prefix.py', 'exec'), namespace)
    original = {}
    before = {}
    for label, root in OLD.items():
        prefix = namespace['Prefix'](root, OLD_SHA[label], 172, LAST_SHA[label])
        p = prefix.protocol
        original[label] = p
        assert p['format'] == 'poloniex-fixed-future-replay-v2'
        assert p['source_root'] == str(SOURCE) and p['source_protocol_sha256'] == SOURCE_SHA
        assert p['source_start_ns'] == source_protocol['start_ns']
        assert p['source_end_exclusive_ns'] == source_protocol['end_exclusive_ns']
        assert time.time_ns() < p['source_end_exclusive_ns'] and p['last_index'] == 10079
        assert sha(root / 'observed_cycle.test') == p['files']['observed_cycle.test'] == proof['variants'][label]['binary_sha256']
        assert proof['variants'][label]['original_protocol_sha256'] == OLD_SHA[label]
        assert proof['variants'][label]['original_last_receipt_sha256'] == LAST_SHA[label]
        assert proof['variants'][label]['verified'] is True and proof['variants'][label]['original_batches'] == 173
        assert proof['variants'][label]['gap_indices'] == [97]
        assert list(root.glob('failure_*.json'))
        started = json.loads((root / 'started.json').read_text())
        command = Path('/proc') / str(started['pid']) / 'cmdline'
        assert not command.is_file() or str(root).encode() not in command.read_bytes(), 'original consumer still running'
        for account in p['accounts']:
            c = account['config']
            assert c['Mode'] == 'paper' and c['Budget'] == '495' and c['FeeRate'] in ('.003', '.004', '.006')
        assert len(p['accounts']) == 6
        before[label] = inventory(root)
    assert original['guarded']['accounts'] == original['unguarded']['accounts']
    PACKAGE.mkdir()
    for name, raw in files.items():
        path = PACKAGE / name
        path.parent.mkdir(exist_ok=True)
        write(path, raw)
    registered = time.time_ns()
    protocols = {}
    for label, root in NEW.items():
        root.mkdir()
        for filename in ('shadow.py', 'native.py', 'receipt_rules.py', 'outcomes.py', 'prefix.py'):
            write(root / filename, files['worker/' + filename])
        for filename in ('PROTOCOL.md', 'prefix_verified.json', 'tests.log'):
            write(root / filename, files[filename])
        write(root / 'observed_cycle.test', (OLD[label] / 'observed_cycle.test').read_bytes())
        (root / 'observed_cycle.test').chmod(0o700)
        p = dict(original[label])
        p.update(format='poloniex-captured-recovery-v1', registered_at_ns=registered,
                 recovered_observed_data=True, original_prospective_study_failed=True,
                 original_root=str(OLD[label]), original_protocol_sha256=OLD_SHA[label],
                 prefix_last_index=172, prefix_last_receipt_sha256=LAST_SHA[label],
                 local_prefix_verification_sha256=manifest['prefix_verified.json'],
                 matched_other_study=str(NEW['guarded' if label == 'unguarded' else 'unguarded']),
                 files={path.name:sha(path) for path in root.iterdir() if path.is_file()})
        write(root / 'protocol.json', encode(p))
        protocols[label] = dict(root=str(root), sha256=sha(root / 'protocol.json'), protocol=p)
    launches = []
    for label, root in NEW.items():
        argv = ['/usr/bin/nice', '-n', '19', '/usr/bin/python3', str(root / 'shadow.py'), '--root', str(root), '--protocol-sha', sha(root / 'protocol.json')]
        with (root / 'worker.log').open('xb') as log:
            process = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env={'PATH':'/usr/local/bin:/usr/bin:/bin', 'PYTHONUNBUFFERED':'1', 'GOMAXPROCS':'1'})
        receipt = dict(at_ns=time.time_ns(), pid=process.pid, argv=argv, root=str(root), external_orders=False,
                       protocol_sha256=sha(root / 'protocol.json'), recovered_observed_data=True)
        write(root / 'launch.json', encode(receipt))
        launches.append(receipt)
    after = {label:inventory(root) for label, root in OLD.items()}
    assert before == after and sha(SOURCE / 'protocol.json') == SOURCE_SHA
    result = dict(registered_at_ns=registered, package_sha256=expected_archive, source_pid=source_start['pid'],
                  original_directories_unchanged=True, original_inventories=before, launches=launches,
                  protocols=protocols, source_restarted=False, external_orders=False, credentials_transferred=False)
    write(PACKAGE / 'launch_verification.json', encode(result))
    print(json.dumps(result, sort_keys=True), flush=True)
