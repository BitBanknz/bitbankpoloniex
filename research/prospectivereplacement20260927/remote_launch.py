"""Install only a verified public-research package into new directories."""
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
MINUTE = 60_000_000_000
PUBLIC = BASE / 'public_retention_20260927_v1'
PAPERS = {name:BASE / ('completed_cycle_' + name + '_future_20260927_v1') for name in ('unguarded', 'guarded')}
PACKAGE = BASE / 'research_package_20260927_v1'
OLD = {name:BASE / ('quote_aware_' + ('guarded_' if name == 'guarded' else '') + 'future_20260924_v1') for name in PAPERS}
EXPECTED = dict(unguarded='a1ad7dbfd6a5fc8d72102ea78c5bb1833ae90e4c5250c2facaca155f6bf569ca',
                guarded='62cd81e7cbe73206e8fcca841c98c268bcc18e523b9e9379866f81f71fce9e10')
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
encode = lambda v:(json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def write(path, raw):
    with path.open('xb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def launch(root, script, expected):
    argv = ['/usr/bin/nice', '-n', '15', '/usr/bin/python3', str(root / script), '--root', str(root), '--protocol-sha', expected]
    with (root / 'worker.log').open('xb') as log:
        p = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, env={'PATH':'/usr/local/bin:/usr/bin:/bin', 'PYTHONUNBUFFERED':'1', 'GOMAXPROCS':'1'})
    receipt = dict(at_ns=time.time_ns(), pid=p.pid, argv=argv, root=str(root), protocol_sha256=expected, external_orders=False)
    write(root / 'launch.json', encode(receipt))
    return receipt


def main(payload_b64, expected_archive):
    archive = base64.b64decode(payload_b64, validate=True)
    assert hashlib.sha256(archive).hexdigest() == expected_archive
    assert all(not p.exists() for p in [PACKAGE, PUBLIC, *PAPERS.values()])
    assert shutil.disk_usage(BASE).free >= 30 << 30
    original = {}
    for name, root in OLD.items():
        assert sha(root / 'protocol.json') == EXPECTED[name]
        p = json.loads((root / 'protocol.json').read_text()); original[name] = p
        assert p['external_orders'] is False and len(p['accounts']) == 6
        assert sha(root / 'observed_cycle.test') == p['files']['observed_cycle.test']
        for a in p['accounts']:
            c = a['config']
            assert c['Mode'] == 'paper' and c['Budget'] == '495' and c['FeeRate'] in ('.003', '.004', '.006')
    assert original['unguarded']['accounts'] == original['guarded']['accounts']
    allowed = {'collector/recorder.py', 'PROTOCOL.md', 'worker/shadow.py', 'worker/native.py', 'worker/receipt_rules.py', 'worker/outcomes.py', 'manifest.json'}
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        members = tar.getmembers(); assert len(members) == len(allowed) and {m.name for m in members} == allowed
        for m in members:
            assert m.isfile() and m.size < 128 << 10
            files[m.name] = tar.extractfile(m).read()
    manifest = json.loads(files['manifest.json']); assert set(manifest) == allowed - {'manifest.json'}
    for name, digest in manifest.items(): assert hashlib.sha256(files[name]).hexdigest() == digest
    assert manifest['collector/recorder.py'] == '36231ab8b6fbce60167174e46c230ab1b69d9ce173bd15c29496180de0f76608'
    PACKAGE.mkdir()
    for name, raw in files.items():
        path = PACKAGE / name; path.parent.mkdir(exist_ok=True); write(path, raw)
    for root in [PUBLIC, *PAPERS.values()]: root.mkdir()
    registered = time.time_ns(); start = (registered // MINUTE + 4) * MINUTE + 15_000_000_000
    assert start - registered >= 180_000_000_000
    write(PUBLIC / 'recorder.py', files['collector/recorder.py']); write(PUBLIC / 'PROTOCOL.md', files['PROTOCOL.md'])
    old_source = BASE / 'public_retention_20260924_v1/protocol.json'
    assert sha(old_source) == 'f6c627405f80ade06457c6d659a031834e3b6f50acf17b7317d2cf39538b23c4'
    p = json.loads(old_source.read_text())
    p.update(start_ns=start, end_exclusive_ns=start + 10080 * MINUTE, registered_at_ns=registered,
             protocol_document_sha256=sha(PUBLIC / 'PROTOCOL.md'), replacement_of_stopped_archive=str(old_source.parent))
    write(PUBLIC / 'protocol.json', encode(p))
    source_sha = sha(PUBLIC / 'protocol.json')
    for name, root in PAPERS.items():
        for filename in ('shadow.py', 'native.py', 'receipt_rules.py', 'outcomes.py'):
            write(root / filename, files['worker/' + filename])
        write(root / 'PROTOCOL.md', files['PROTOCOL.md'])
        write(root / 'observed_cycle.test', (OLD[name] / 'observed_cycle.test').read_bytes())
        (root / 'observed_cycle.test').chmod(0o700)
        p = dict(format='poloniex-fixed-future-replay-v2', mode='observed_book_paper_replay', external_orders=False,
                 actual_decision_commit_claimed=False, registered_at_ns=registered, first_index=0, last_index=10079,
                 first_scheduled_ns=start, source_start_ns=start, source_end_exclusive_ns=start+10080*MINUTE,
                 source_root=str(PUBLIC), source_protocol_sha256=source_sha, accounts=original[name]['accounts'],
                 variant=name, matched_other_study=str(PAPERS['guarded' if name == 'unguarded' else 'unguarded']),
                 files={p.name:sha(p) for p in root.iterdir() if p.is_file()})
        assert p['files']['observed_cycle.test'] == original[name]['files']['observed_cycle.test']
        write(root / 'protocol.json', encode(p))
    assert time.time_ns() < start - 120_000_000_000
    receipts = [launch(PUBLIC, 'recorder.py', source_sha)]
    receipts.extend(launch(root, 'shadow.py', sha(root / 'protocol.json')) for root in PAPERS.values())
    result = dict(registered_at_ns=registered, start_ns=start, end_exclusive_ns=start+10080*MINUTE,
                  package_sha256=expected_archive, package_root=str(PACKAGE), launches=receipts,
                  protocols={str(root):json.loads((root / 'protocol.json').read_text()) for root in [PUBLIC, *PAPERS.values()]},
                  original_protocols_unchanged=all(sha(OLD[name] / 'protocol.json') == EXPECTED[name] for name in OLD),
                  external_orders=False, credentials_used=False)
    write(PACKAGE / 'launch_verification.json', encode(result))
    print(json.dumps(result, sort_keys=True), flush=True)
