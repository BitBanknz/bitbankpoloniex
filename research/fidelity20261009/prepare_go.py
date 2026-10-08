"""Research build of THIS checkout's engine for the 2026-10-09 fidelity k-fold (loopback GETs, no orders).
Patches: time.Now -> replay clock in engine/market/signals/client, loopback-only client, no rate-limit sleep.
usage: python3 -I prepare_go.py --out <dir>"""
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]


def sub(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args(); out = a.out.resolve()
    if out.exists(): shutil.rmtree(out)
    (out/'internal').mkdir(parents=True)
    shutil.copytree(ROOT/'internal/bot', out/'internal/bot', ignore=shutil.ignore_patterns('*_test.go'))
    for f in ('go.mod', 'go.sum'): shutil.copy(ROOT/f, out/f)
    bot = out/'internal/bot'; hashes = {}
    for name in sorted(os.listdir(bot)):
        hashes[name] = hashlib.sha256((bot/name).read_bytes()).hexdigest()
    for name in ('engine.go', 'market.go', 'signals.go', 'client.go'):
        p = bot/name; text = p.read_text().replace('time.Now()', 'replayNow()')
        if name == 'client.go':
            text = sub(text, 'c.mu.Lock()', 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
            text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
        p.write_text(text)
    t = HERE/'replay_test.go.txt'; shutil.copy(t, bot/'fidelity_replay_test.go'); hashes['replay_test.go.txt'] = hashlib.sha256(t.read_bytes()).hexdigest()
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out/'inputs.json').write_text(json.dumps(dict(head=rev, files=hashes), indent=1))
    subprocess.run(['go', 'test', '-c', '-o', str(out/'replay.test'), './internal/bot/'], cwd=out, check=True, env={**os.environ, 'CGO_ENABLED': '0'})
    print(out/'replay.test')


if __name__ == '__main__':
    main()
