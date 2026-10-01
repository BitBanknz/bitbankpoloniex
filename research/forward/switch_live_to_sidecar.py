"""Guarded, reversible switch of the live trader's signal URL to the EMA 0.25 sidecar. Dry run unless --execute.
Run on the remote. Only the unit's --predictions URL changes; binary, state and every other argument are preserved."""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'stopguardactivation20260929'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path('/nvme0n1-disk/code/bitbank-poloniex'); STATE = ROOT/'data/live'; BINARY = ROOT/'bin/bitbankpoloniex'
UNIT = Path('/etc/systemd/system/bitbankpoloniex-live.service'); SERVICE = 'bitbankpoloniex-live.service'
CAND = '4cc9122477f3e5c6e030ecf5df4aaf73ceb4bf31c3747208944c737f99d44805'
UNIT_SHA = '9f3af984558bdb09a685413057cabe981d129bc53ef74a9933f93c385d9c9765'
OLD = 'http://127.0.0.1:8745/api/trading-bot/rotation-signals'; NEW = 'http://127.0.0.1:18746/api/trading-bot/rotation-signals'
SIDECAR_STATE = ROOT/'data/ema25-signal-state.json'; FORECAST = Path('/nvme0n1-disk/code/bitbankgo/data/rotation/state/forecast.json')
BASE = [str(BINARY), '--command', 'run', '--mode', 'live', '--state', 'data/live', '--budget', '495', '--max-order', '49', '--slots', '3',
        '--cooldown-hours', '120', '--slot-top-up', '--cash-reserve', '0.4', '--halt-peak-dd', '0.25', '--halt-daily-loss', '0.08',
        '--enable-live-orders', '--predictions', OLD, '--env', str(ROOT/'.env')]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def service():
    raw = subprocess.check_output(['systemctl', 'show', SERVICE, '-p', 'MainPID', '-p', 'ActiveState', '-p', 'SubState', '-p', 'NRestarts'], text=True)
    return dict(l.split('=', 1) for l in raw.splitlines())
def args_of(pid): return (Path('/proc')/str(pid)/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
def running(expected_args):
    s = service(); assert s['ActiveState'] == 'active' and s['SubState'] == 'running', s
    pid = int(s['MainPID']); assert sha(Path('/proc')/str(pid)/'exe') == CAND == sha(BINARY)
    assert args_of(pid) == expected_args, ('arguments differ', args_of(pid)); return s
def sudo(*a): subprocess.run(['sudo', '-n', *a], check=True, timeout=90)
def observe(expected_args, before, label, out):
    from continuity import verify
    began, clocks, proofs = time.monotonic(), set(), []
    while time.monotonic() - began < 240:
        try:
            cur = running(expected_args); after = read(STATE/'state.json')
            if after['LastCycle'] not in clocks:
                proofs.append(dict(service=cur, continuity=verify(before, after))); clocks.add(after['LastCycle']); print('COMPLETED_CYCLE', label, len(clocks), flush=True)
                if len(clocks) >= 2: return proofs, after
        except (AssertionError, FileNotFoundError) as e: err = str(e)
        time.sleep(2)
    raise RuntimeError('completed cycles not verified')
def install_unit(text):
    tmp = ROOT/'data/.unit.tmp'; tmp.write_text(text); sudo('install', '-m', '644', str(tmp), str(UNIT)); tmp.unlink(); sudo('systemctl', 'daemon-reload')
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--execute', action='store_true'); args = ap.parse_args(); os.umask(0o077)
    out = ROOT/f'data/release-ema25-switch-{int(time.time())}'; 
    assert sha(UNIT) == UNIT_SHA, 'live unit changed since qualification'
    running(BASE); before = read(STATE/'state.json'); assert before['Pending'] is None and before['AccountBacked']
    st = read(SIDECAR_STATE); fc = read(FORECAST)
    assert st['alpha'] == 0.25 and st['pairs'] == fc['pairs'] and st['issued_hour'] == fc['issued_hour'], 'sidecar has not served the current forecast day'
    assert subprocess.run(['systemctl', 'is-active', 'bitbankpoloniex-ema25-signal.service'], capture_output=True, text=True).stdout.strip() == 'active'
    text = UNIT.read_text(); assert text.count(OLD) == 1; new_text = text.replace(OLD, NEW)
    print('CHECKS_PASSED; unit change: --predictions', OLD, '->', NEW)
    if not args.execute: print('DRY_RUN: nothing changed'); return
    out.mkdir(); shutil.copy2(UNIT, out/'unit.before'); shutil.copytree(STATE, out/'state_before')
    NEWARGS = [NEW if a == OLD else a for a in BASE]; switched = False
    try:
        assert read(STATE/'state.json')['Pending'] is None
        install_unit(new_text); switched = True; sudo('systemctl', 'restart', SERVICE)
        proofs, after = observe(NEWARGS, before, 'switched', out)
        assert read(STATE/'state.json')['Pending'] is None
        (out/'verified.json').write_text(json.dumps(dict(verified=True, proofs=proofs, unit_before_sha256=UNIT_SHA), indent=2)); print('SWITCHED')
    except Exception as e:
        print('FAILED, rolling back:', e)
        if switched:
            sudo('systemctl', 'stop', SERVICE); latest = read(STATE/'state.json')
            install_unit((out/'unit.before').read_text()); sudo('systemctl', 'start', SERVICE)
            if latest['Pending'] is None: observe(BASE, latest, 'rollback', out)
        raise
if __name__ == '__main__': main()
