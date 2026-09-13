"""Production-budget replay; only generated Go overlays can change decisions."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--out', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[2]
out = Path(a.out).resolve()
out.mkdir(parents=True, exist_ok=False)
replace = {}
for name in ('engine.go', 'market.go', 'signals.go', 'client.go'):
    source = root/'internal/bot'/name
    text = source.read_text().replace('time.Now()', 'replayNow()')
    if name == 'client.go':
        text = text.replace('c.mu.Lock()', 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
        text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
    if name == 'engine.go':
        old = '''if activeSlots >= e.Config.Slots {
				break
			}
			if _, held := s.Holdings[symbol]; held || now.Before(s.Cooldown[symbol]) {'''
        new = '''pos, held := s.Holdings[symbol]
            if activeSlots >= e.Config.Slots && !(replayBonus > 0 && held && !pos.Imported) { continue }
            if (held && !(replayBonus > 0 && !pos.Imported)) || now.Before(s.Cooldown[symbol]) {'''
        assert text.count(old) == 1
        text = text.replace(old, new)
        old = 'if side == "BUY" && !spend.IsPositive() {'
        new = '''if replayBonus > 0 && side == "BUY" {
        if pos, held := s.Holdings[m.Symbol]; held {
            bid,_ := decimal.NewFromString(b.Bids[0])
            spend = decimal.Min(spend, limit.Sub(pos.Quantity.Mul(bid)))
        }
    }
    ''' + old
        assert text.count(old) == 1
        text = text.replace(old, new)
    target = out/(name+'.txt')
    target.write_text(text)
    replace[str(source)] = str(target)
replace[str(root/'internal/bot/frozen_ledger_research_test.go')] = str(Path(__file__).with_name('replay_test.go.txt'))
(out/'overlay.json').write_text(json.dumps({'Replace': replace}, indent=2)+'\n')
(out/'source-hashes.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'internal/bot').glob('*.go')}, indent=2)+'\n')
