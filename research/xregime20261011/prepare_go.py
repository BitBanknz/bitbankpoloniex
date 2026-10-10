"""Research build of f3aa665 for the 2026-10-11 xregime study: fidelity harness plus default-off hooks.
usage: python3 -I prepare_go.py --out <dir>"""
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
HOOKS = '''package bot

import "time"

var researchEntryGate func(time.Time) bool
var researchFlatGate func(time.Time) bool
var researchBuyBand, researchBuyPart float64
'''


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
            text = sub(text, '\tranked := Targets(scores, markets, e.Config.Slots)\n', '\tranked := Targets(scores, markets, e.Config.Slots)\n\tif researchFlatGate != nil && !researchFlatGate(now) {\n\t\tranked = nil\n\t}\n')
            text = sub(text, '\tif ready {\n\t\tfor _, symbol := range ranked {', '\tif ready && (researchEntryGate == nil || researchEntryGate(now)) {\n\t\tfor _, symbol := range ranked {')
            text = sub(text, '\treturn e.tradeSized(ctx, s, m, b, side, hour, source, cap, suffix, OrderOpts{MaxSpread: e.Config.MaxSpread}, false)',
                       '\topts := OrderOpts{MaxSpread: e.Config.MaxSpread}\n\tif side == "BUY" {\n\t\topts.Band, opts.Participation = researchBuyBand, researchBuyPart\n\t}\n\treturn e.tradeSized(ctx, s, m, b, side, hour, source, cap, suffix, opts, false)')
        p.write_text(text)
    (bot/'research_hooks.go').write_text(HOOKS)
    t = HERE/'replay_test.go.txt'; shutil.copy(t, bot/'xregime_replay_test.go'); hashes['replay_test.go.txt'] = hashlib.sha256(t.read_bytes()).hexdigest()
    hashes['prepare_go.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out/'inputs.json').write_text(json.dumps(dict(head=rev, files=hashes), indent=1))
    subprocess.run(['go', 'test', '-c', '-o', str(out/'replay.test'), './internal/bot/'], cwd=out, check=True, env={**os.environ, 'CGO_ENABLED': '0', 'GOTOOLCHAIN': 'go1.25.0'})
    print(out/'replay.test')


if __name__ == '__main__':
    main()
