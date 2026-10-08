"""Research build of the DEPLOYED engine (release-stop-guard-20260930_v3 source) for the 2026-10-08 levers.
Same clock/loopback patches as research/longkfold20261007/prepare_go.py plus three research-only hooks, all
inert at their defaults (ExitRank 0 = exit outside top Slots, MinHoldH 0 = 72h, fee floor only widened):
  1. exit keep-set = top ExitRank ranks (rank hysteresis) instead of the entry target set;
  2. minimum hold from the driver instead of the hard-coded 72h;
  3. Validate fee floor 0.003 -> 0.0005 so the measured 14 bps TRX-discounted fee can be replayed."""
import argparse, hashlib, json, shutil, subprocess, os
from pathlib import Path


def sub(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', type=Path, required=True); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args(); a.out = a.out.resolve()
    if a.out.exists(): shutil.rmtree(a.out)
    shutil.copytree(a.src, a.out, ignore=shutil.ignore_patterns('*_test.go'))
    bot = a.out/'internal/bot'; hashes = {}
    for name in ('engine.go', 'market.go', 'signals.go', 'client.go'):
        p = bot/name; text = p.read_text(); hashes[name] = hashlib.sha256(text.encode()).hexdigest()
        text = text.replace('time.Now()', 'replayNow()')
        if name == 'client.go':
            text = sub(text, 'c.mu.Lock()', 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
            text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
        if name == 'engine.go':
            text = sub(text, 'c.FeeRate.LessThan(decimal.NewFromFloat(.003))', 'c.FeeRate.LessThan(decimal.NewFromFloat(.0005))')
            text = sub(text, '''	for _, symbol := range ranked {
		desired[symbol] = true
	}
''', '''	for _, symbol := range ranked {
		desired[symbol] = true
	}
	keep := desired
	if researchExitRank > e.Config.Slots {
		keep = map[string]bool{}
		for _, symbol := range Targets(scores, markets, researchExitRank) {
			keep[symbol] = true
		}
	}
''')
            text = sub(text, 'exit := ready && observed[symbol] && !desired[symbol] && now.Sub(p.Entered) >= 72*time.Hour',
                       'exit := ready && observed[symbol] && !keep[symbol] && now.Sub(p.Entered) >= researchMinHold')
            text += '\nvar researchExitRank = 0\nvar researchMinHold = 72 * time.Hour\n'
        p.write_text(text)
    t = Path(__file__).with_name('replay_test.go.txt'); shutil.copy(t, bot/'longkfold_replay_test.go')
    hashes['replay_test.go.txt'] = hashlib.sha256(t.read_bytes()).hexdigest()
    (a.out/'inputs.json').write_text(json.dumps(hashes, indent=1))
    subprocess.run(['go', 'test', '-c', '-o', str(a.out/'replay.test'), './internal/bot/'], cwd=a.out, check=True, env={**os.environ, 'CC': 'gcc', 'CGO_ENABLED': '0'})
    print(json.dumps(hashes, indent=1))


if __name__ == '__main__':
    main()
