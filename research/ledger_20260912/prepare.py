#!/usr/bin/env python3
"""Build a research-only Go overlay; no exchange-facing source is edited."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'data/frontier_20260912/ledger/overlay'
out.mkdir(parents=True, exist_ok=True)
replace = {}
hashes = {}
for name in ['engine.go', 'market.go', 'signals.go', 'client.go']:
    source = root / 'internal/bot' / name
    text = source.read_text()
    hashes[str(source.relative_to(root))] = hashlib.sha256(source.read_bytes()).hexdigest()
    text = text.replace('time.Now()', 'replayNow()')
    if name == 'client.go':
        # The offline loopback fixture has no exchange rate limit. Refuse any
        # external base URL, and remove pacing only in this research overlay.
        text = text.replace('c.mu.Lock()', 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
        text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
    if name == 'engine.go':
        before = 'ranked := Targets(scores, markets, e.Config.Slots)'
        assert text.count(before) == 1
        text = text.replace(before, 'ranked := replayTargets(scores, markets, e.Config.Slots, &s)')
    target = out / (name + '.txt')
    target.write_text(text)
    replace[str(source)] = str(target)
driver = root / 'research/ledger_20260912/replay_test.go.txt'
replace[str(root / 'internal/bot/frozen_ledger_research_test.go')] = str(driver)
(out.parent / 'overlay.json').write_text(json.dumps({'Replace': replace}, indent=2) + '\n')
(out.parent / 'production-source-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
print('Prepared clock/selector overlay; production source unchanged.')
