"""Build the replay test binary from the DEPLOYED engine source (release-stop-guard-20260930_v3
package source, binary sha256 4cc91224...), with the same clock/loopback patches as
research/sweep20260930/prepare.py."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', type=Path, required=True); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args(); a.out = a.out.resolve()
    if a.out.exists(): shutil.rmtree(a.out)
    shutil.copytree(a.src, a.out, ignore=shutil.ignore_patterns('*_test.go'))
    bot = a.out/'internal/bot'; hashes = {}
    for name in ('engine.go', 'market.go', 'signals.go', 'client.go'):
        p = bot/name; text = p.read_text(); hashes[name] = hashlib.sha256(text.encode()).hexdigest()
        text = text.replace('time.Now()', 'replayNow()')
        if name == 'client.go':
            old = 'c.mu.Lock()'; assert text.count(old) == 1
            text = text.replace(old, 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; '+old)
            text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
        p.write_text(text)
    t = Path(__file__).with_name('replay_test.go.txt'); shutil.copy(t, bot/'longkfold_replay_test.go')
    hashes['replay_test.go.txt'] = hashlib.sha256(t.read_bytes()).hexdigest()
    (a.out/'inputs.json').write_text(json.dumps(hashes, indent=1))
    subprocess.run(['go', 'test', '-c', '-o', str(a.out/'replay.test'), './internal/bot/'], cwd=a.out, check=True, env={**__import__('os').environ, 'CC': 'gcc', 'CGO_ENABLED': '0'})
    print(json.dumps(hashes, indent=1))


if __name__ == '__main__':
    main()
