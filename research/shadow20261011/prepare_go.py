"""Research build of a Poloniex engine source for the live shadow replay (loopback GETs, no orders).
usage: python3 -I prepare_go.py --src <repo-root-with-internal/bot> --variant new|old --out <dir>"""
import argparse, hashlib, json, os, re, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent

SHIM_COMMON = '''package bot

import "time"

type ShadowSkip struct {
	At  time.Time
	Key string
	Err string
}

var shadowSkips []ShadowSkip

func shadowSkip(key string, err error) {
	shadowSkips = append(shadowSkips, ShadowSkip{replayNow(), key, err.Error()})
}
'''
SHIM_NEW = '''package bot

import "github.com/shopspring/decimal"

func shadowApply(c *Config, minHold, ramp int, minExit string) error {
	c.MinHoldHours = minHold
	c.ExitRampMinutes = ramp
	c.MinExitUSDT = decimal.RequireFromString(minExit)
	return nil
}

func shadowExiting(p Position) bool { return p.Exiting != "" }
'''
SHIM_OLD = '''package bot

import "errors"

func shadowApply(c *Config, minHold, ramp int, minExit string) error {
	if (minHold != 0 && minHold != 72) || ramp != 0 || (minExit != "0" && minExit != "") {
		return errors.New("flag not supported by this engine source")
	}
	return nil
}

func shadowExiting(p Position) bool { return false }
'''


def sub(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', type=Path, required=True); ap.add_argument('--variant', choices=('new', 'old'), required=True)
    ap.add_argument('--out', type=Path, required=True); a = ap.parse_args(); out = a.out.resolve()
    if out.exists(): shutil.rmtree(out)
    (out/'internal').mkdir(parents=True)
    shutil.copytree(a.src/'internal/bot', out/'internal/bot', ignore=shutil.ignore_patterns('*_test.go'))
    for f in ('go.mod', 'go.sum'): shutil.copy(a.src/f, out/f)
    bot = out/'internal/bot'
    hashes = {n: hashlib.sha256((bot/n).read_bytes()).hexdigest() for n in sorted(os.listdir(bot))}
    for name in ('engine.go', 'market.go', 'signals.go', 'client.go'):
        p = bot/name; text = p.read_text().replace('time.Now()', 'replayNow()')
        if name == 'client.go':
            text = sub(text, 'c.mu.Lock()', 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
            text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
        if name == 'engine.go':
            build = 'BuildOrderOpts(m, b, side, id, spend, owned, opts)' if a.variant == 'new' else 'BuildOrder(m, b, side, id, spend, owned, e.Config.MaxSpread)'
            text = sub(text, f'o, err := {build}\n\tif err != nil {{\n\t\treturn nil\n\t}}', f'o, err := {build}\n\tif err != nil {{\n\t\tshadowSkip(key, err)\n\t\treturn nil\n\t}}')
            text = sub(text, 'if side == "BUY" && !spend.IsPositive() {\n\t\treturn nil', 'if side == "BUY" && !spend.IsPositive() {\n\t\tshadowSkip(key, errors.New("no spendable cash above reserve"))\n\t\treturn nil')
            if a.variant == 'old':
                text = sub(text, 'c.FeeRate.LessThan(decimal.NewFromFloat(.003))', 'c.FeeRate.LessThan(decimal.NewFromFloat(.0005))')
        p.write_text(text)
    (bot/'shadow_hook.go').write_text(SHIM_COMMON)
    (bot/'shadow_flags.go').write_text(SHIM_NEW if a.variant == 'new' else SHIM_OLD)
    t = HERE/'shadow_replay_test.go.txt'; shutil.copy(t, bot/'shadow_replay_test.go')
    hashes['shadow_replay_test.go.txt'] = hashlib.sha256(t.read_bytes()).hexdigest()
    (out/'inputs.json').write_text(json.dumps(dict(src=str(a.src), variant=a.variant, files=hashes), indent=1))
    subprocess.run(['go', 'test', '-c', '-o', str(out/'replay.test'), './internal/bot/'], cwd=out, check=True, env={**os.environ, 'CGO_ENABLED': '0'})
    print(out/'replay.test')


if __name__ == '__main__':
    main()
