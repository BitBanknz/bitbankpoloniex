"""Ship only manifested research code after all local checks pass."""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
OUT = Path('/vfast/data/trading_research_20260924/poloniex_execution_wait_recovery_20260927_v1')
sha = lambda raw:hashlib.sha256(raw).hexdigest()


def main():
    proof = json.loads((OUT / 'prefix_verified.json').read_text())
    assert set(proof['variants']) == {'guarded', 'unguarded'}
    for value in proof['variants'].values():
        assert value['verified'] is True and value['total_transitions'] == 1044
    tests = (OUT / 'tests.log').read_bytes()
    assert b'Ran 12 tests' in tests and tests.rstrip().endswith(b'OK')
    files = {'PROTOCOL.md':(HERE.parents[1] / 'docs/2026-09-27-execution-wait-recovery-protocol.md').read_bytes(),
             'prefix_verified.json':(OUT / 'prefix_verified.json').read_bytes(), 'tests.log':tests}
    for name in ('shadow.py', 'native.py', 'receipt_rules.py', 'outcomes.py', 'prefix.py'):
        path = HERE / 'worker' / name
        assert sha(path.read_bytes()) == proof['source_hashes'][str(path)]
        files['worker/' + name] = path.read_bytes()
    manifest = {name:sha(raw) for name, raw in files.items()}
    files['manifest.json'] = (json.dumps(manifest, sort_keys=True) + '\n').encode()
    package = OUT / 'package'
    package.mkdir()
    for name, raw in files.items():
        path = package / name
        path.parent.mkdir(exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:') as tar:
        for name, raw in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            member.mode = 0o600
            tar.addfile(member, io.BytesIO(raw))
    archive = buf.getvalue()
    (OUT / 'package.tar').write_bytes(archive)
    launcher = (HERE / 'remote_launch.py').read_text()
    remote = launcher + '\nmain(' + repr(base64.b64encode(archive).decode()) + ',' + repr(sha(archive)) + ')\n'
    (OUT / 'remote_launch.py.txt').write_text(remote)
    (OUT / 'launch_binding.json').write_text(json.dumps(dict(at_ns=time.time_ns(), archive_sha256=sha(archive),
        launcher_sha256=sha(launcher.encode()), script_sha256=sha(remote.encode()), manifest=manifest), sort_keys=True) + '\n')
    with (OUT / 'remote_launch.json').open('xb') as out, (OUT / 'remote_launch.stderr.log').open('xb') as err:
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', 'administrator@93.127.141.100', 'python3 -'],
                                input=remote.encode(), stdout=out, stderr=err, timeout=60)
    (OUT / 'launch_transport.json').write_text(json.dumps(dict(at_ns=time.time_ns(), returncode=result.returncode,
        output_sha256=sha((OUT / 'remote_launch.json').read_bytes())), sort_keys=True) + '\n')
    assert result.returncode == 0
    result = json.loads((OUT / 'remote_launch.json').read_text())
    print('RECOVERY_LAUNCHED', [(v['root'], v['pid']) for v in result['launches']], flush=True)


if __name__ == '__main__':
    main()
