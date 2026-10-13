"""Research build of THIS checkout's engine for the 2026-10-13 hourly k-fold (loopback GETs, no orders).
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
        if name == 'engine.go':
            # research-only hooks, inert at defaults: keep-set = top researchExitRank; exit only after the holding has been
            # outside the keep-set on every ready decision for researchExitConfirm (debounce of hourly rank flips)
            # hourly-native thresholds (inert unless researchThresh): entries = every name with score >= researchEntryMin, best first,
            # until slots are full; exits after min hold when the score falls below researchExitBelow
            text = sub(text, 'ranked := Targets(scores, markets, e.Config.Slots)', '''ranked := Targets(scores, markets, e.Config.Slots)
	if researchThresh {
		eligible := map[string]float64{}
		for symbol, v := range scores {
			if v >= researchEntryMin {
				eligible[symbol] = v
			}
		}
		ranked = Targets(eligible, markets, len(markets))
	}''')
            text = sub(text, '''	for _, symbol := range ranked {
		desired[symbol] = true
	}
''', '''	for _, symbol := range ranked {
		desired[symbol] = true
	}
	keep := desired
	if researchThresh {
		keep = map[string]bool{}
		for symbol, v := range scores {
			if v >= researchExitBelow {
				keep[symbol] = true
			}
		}
	}
	if researchExitRank > e.Config.Slots {
		keep = map[string]bool{}
		for _, symbol := range Targets(scores, markets, researchExitRank) {
			keep[symbol] = true
		}
	}
	if ready {
		for symbol := range s.Holdings {
			if keep[symbol] {
				delete(researchOutside, symbol)
			} else if _, ok := researchOutside[symbol]; !ok {
				researchOutside[symbol] = now
			}
		}
	}
''')
            text = sub(text, 'exit := ready && observed[symbol] && !desired[symbol] && now.Sub(p.Entered) >= e.Config.minHold()',
                       'exit := ready && observed[symbol] && !keep[symbol] && now.Sub(p.Entered) >= e.Config.minHold() && now.Sub(researchOutsideSince(symbol, now)) >= researchExitConfirm')
            text += '''
var researchExitRank = 0
var researchExitConfirm time.Duration
var researchOutside = map[string]time.Time{}
var researchThresh = false
var researchEntryMin, researchExitBelow float64

func researchOutsideSince(symbol string, now time.Time) time.Time {
	if t, ok := researchOutside[symbol]; ok {
		return t
	}
	return now
}
'''
        p.write_text(text)
    t = HERE/'replay_test.go.txt'; shutil.copy(t, bot/'hourly_replay_test.go'); hashes['replay_test.go.txt'] = hashlib.sha256(t.read_bytes()).hexdigest()
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out/'inputs.json').write_text(json.dumps(dict(head=rev, files=hashes), indent=1))
    subprocess.run(['go', 'test', '-c', '-o', str(out/'replay.test'), './internal/bot/'], cwd=out, check=True, env={**os.environ, 'CGO_ENABLED': '0'})
    print(out/'replay.test')


if __name__ == '__main__':
    main()
