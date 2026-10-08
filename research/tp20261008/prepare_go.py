"""Research build of the DEPLOYED engine (release-stop-guard-20260930_v3 source) for the 2026-10-08 take-profit test.
= research/knobs20261008/prepare_go.py (clock/loopback patches, inert ExitRank/MinHoldH hooks, fee floor 0.0005,
slot cap 5, in-process transport) plus the profit exits of main's internal/bot/exits.go, copied verbatim and wired
into the release engine at the same four points as main (Config fields, Validate, Position fields + apply, stop check).
All inert at TakeProfit = TrailArm = 0."""
import argparse, hashlib, importlib.util, json, shutil, subprocess, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
K = HERE.parent/'knobs20261008'
spec = importlib.util.spec_from_file_location('kprep', K/'prepare_go.py'); kprep = importlib.util.module_from_spec(spec); spec.loader.exec_module(kprep)
sub = kprep.sub


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', type=Path, required=True); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args(); a.out = a.out.resolve()
    if a.out.exists(): shutil.rmtree(a.out)
    shutil.copytree(a.src, a.out, ignore=shutil.ignore_patterns('*_test.go'))
    bot = a.out/'internal/bot'; hashes = {}
    exits = HERE.parents[1]/'internal/bot/exits.go'; shutil.copy(exits, bot/'exits.go'); hashes['exits.go'] = hashlib.sha256(exits.read_bytes()).hexdigest()
    for name in ('engine.go', 'market.go', 'signals.go', 'client.go'):
        p = bot/name; text = p.read_text(); hashes[name] = hashlib.sha256(text.encode()).hexdigest()
        text = text.replace('time.Now()', 'replayNow()')
        if name == 'client.go':
            text = sub(text, 'c.mu.Lock()', 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
            text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
        if name == 'engine.go':
            text = sub(text, 'c.FeeRate.LessThan(decimal.NewFromFloat(.003))', 'c.FeeRate.LessThan(decimal.NewFromFloat(.0005))')
            text = sub(text, 'c.Slots > 4 ||', 'c.Slots > 5 ||')
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
            # profit exits, wired exactly as in main
            text = sub(text, '''	HaltDailyLoss        float64 // latch a risk halt below this fraction under the UTC day start (0 = legacy 3%)
}''', '''	HaltDailyLoss        float64 // latch a risk halt below this fraction under the UTC day start (0 = legacy 3%)
	TakeProfit, TrailArm, TrailArmStop float64
}''')
            text = sub(text, '''	if c.ExperimentalFallback && c.Mode != "paper" {''', '''	if err := c.validateExits(); err != nil {
		return err
	}
	if c.ExperimentalFallback && c.Mode != "paper" {''')
            text = sub(text, '''	Entered  time.Time
}''', '''	Entered  time.Time
	Entry    *decimal.Decimal `json:",omitempty"`
	Exiting  string           `json:",omitempty"`
}''')
            text = sub(text, '''		s.Cash = s.Cash.Sub(amount).Sub(fee)
		p.Quantity = p.Quantity.Add(qty)''', '''		s.Cash = s.Cash.Sub(amount).Sub(fee)
		p = e.Config.noteBuy(p, qty, amount)
		p.Quantity = p.Quantity.Add(qty)''')
            text = sub(text, '''	stops := make(map[string]bool, len(s.Holdings))
''', '''	stops := make(map[string]bool, len(s.Holdings))
	profits := make(map[string]bool, len(s.Holdings))
''')
            text = sub(text, 'stops[symbol] = bid.LessThanOrEqual(p.Peak.Mul(decimal.NewFromFloat(.9)))', '''var stop bool
		stop, profits[symbol], s.Holdings[symbol] = e.Config.protectiveExit(p, bid, .9)
		stops[symbol] = stop || profits[symbol]''')
            text = sub(text, '''		if stops[symbols[i]] != stops[symbols[j]] {
			return stops[symbols[i]]
		}''', '''		if stops[symbols[i]] != stops[symbols[j]] {
			return stops[symbols[i]]
		}
		if profits[symbols[i]] != profits[symbols[j]] {
			return profits[symbols[j]]
		}''')
        p.write_text(text)
    t = HERE/'replay_test.go.txt'; shutil.copy(t, bot/'longkfold_replay_test.go')
    hashes['replay_test.go.txt'] = hashlib.sha256(t.read_bytes()).hexdigest()
    (a.out/'inputs.json').write_text(json.dumps(hashes, indent=1))
    subprocess.run(['go', 'test', '-c', '-o', str(a.out/'replay.test'), './internal/bot/'], cwd=a.out, check=True, env={**os.environ, 'CC': 'gcc', 'CGO_ENABLED': '0'})
    print(json.dumps(hashes, indent=1))


if __name__ == '__main__':
    main()
