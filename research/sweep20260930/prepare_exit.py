"""Frozen-ledger replay of one slot top-up configuration (slots, cooldown, reserve, halts)."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def regime_off_days():
    import pandas as pd
    c = pd.read_parquet(Path(__file__).resolve().parents[2]/'data/ranker/close.parquet')['BTC']
    daily = c[c.index.hour == 23].ffill()
    daily.index = daily.index.normalize() + pd.Timedelta(days=1)
    on = (daily > daily.rolling(50).mean()) & (daily > daily.rolling(200).mean())
    sel = on[(on.index >= pd.Timestamp('2026-01-10', tz='UTC')) & (on.index <= pd.Timestamp('2026-09-10', tz='UTC'))]
    return [int(d.timestamp()) for d, v in sel.items() if not v]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--geometries', nargs='+', type=int, default=[0, 28])
    parser.add_argument('--budget', default='495')
    parser.add_argument('--max-order', default='49')
    parser.add_argument('--reserve', default='0.4', help='cash reserve fraction for the top-up arm')
    parser.add_argument('--halt-peak', default='0', help='top-up arm peak-drawdown halt (0 = legacy 0.10)')
    parser.add_argument('--halt-daily', default='0', help='top-up arm daily-loss halt (0 = legacy 0.03)')
    parser.add_argument('--slots', type=int, default=3)
    parser.add_argument('--cooldown', type=int, default=120)
    parser.add_argument('--stop', type=float, default=0.9, help='trailing stop fraction of peak bid')
    parser.add_argument('--minhold', type=int, default=72, help='hours before a non-target holding may be rotated out')
    parser.add_argument('--regime', type=int, default=0, help='1: go to cash and block entries when BTC is not above its 50d and 200d SMA')
    parser.add_argument('--window-cycles', type=int, default=12, help='engine cycles simulated inside the 01:00 execution hour (live runs one per minute)')
    args = parser.parse_args()
    budget, max_order, reserve = Decimal(args.budget), Decimal(args.max_order), Decimal(args.reserve)
    if not budget.is_finite() or not max_order.is_finite() or not 0 < max_order <= budget or not 0 <= reserve <= Decimal('0.9'):
        raise ValueError('finite positive budget, order cap and reserve are required')
    root = Path(__file__).resolve().parents[2]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    replace, hashes = {}, {}
    for name in ('engine.go', 'market.go', 'signals.go', 'client.go'):
        source = root/'internal/bot'/name
        hashes[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
        text = source.read_text().replace('time.Now()', 'replayNow()')
        if name == 'client.go':
            old = 'c.mu.Lock()'
            assert text.count(old) == 1
            text = text.replace(old, 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; '+old)
            text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
        if name == 'engine.go':
            assert 'e.Config.slotTarget(s.Budget)' in text
            a = '\tif !c.mirror() {\n\t\treturn .9\n\t}'
            assert text.count(a) == 1
            text = text.replace(a, '\tif !c.mirror() {\n\t\treturn %s\n\t}' % args.stop)
            a = 'exit := ready && observed[symbol] && !desired[symbol] && now.Sub(p.Entered) >= 72*time.Hour'
            assert text.count(a) == 1
            text = text.replace(a, 'exit := ready && observed[symbol] && !desired[symbol] && (now.Sub(p.Entered) >= %d*time.Hour || replayRegimeOff(now))' % args.minhold)
            a = '\tranked := Targets(scores, markets, e.Config.Slots)\n'
            assert text.count(a) == 1
            text = text.replace(a, a + '\tif replayRegimeOff(now) {\n\t\tranked = nil\n\t}\n')
            off = regime_off_days() if args.regime else []
            text += '\nvar replayRegimeOffDays = map[int64]bool{' + ','.join('%d:true' % d for d in off) + '}\nfunc replayRegimeOff(now time.Time) bool { return replayRegimeOffDays[now.Truncate(24*time.Hour).Unix()] }\n'
        target = out/(name+'.txt')
        target.write_text(text)
        replace[str(source)] = str(target)
    template = root/'research/live_parity20260913/replay_test.go.txt'
    hashes[str(template)] = hashlib.sha256(template.read_bytes()).hexdigest()
    text = template.read_text().replace('replayBonus', 'replaySlotTopUp').replace('Bonus', 'SlotTopUp')
    old = 'cfg:=DefaultConfig();cfg.Budget'
    assert text.count(old) == 1
    text = text.replace(old, f'cfg:=DefaultConfig();cfg.SlotTopUp=bonus>0;if cfg.SlotTopUp {{cfg.CashReserve={reserve};cfg.HaltPeakDD={args.halt_peak};cfg.HaltDailyLoss={args.halt_daily}}};cfg.Slots={args.slots};cfg.CooldownHours={args.cooldown};cfg.Budget')
    text = text.replace('cfg.Budget=decimal.NewFromInt(495)', f'cfg.Budget=decimal.RequireFromString("{budget}")')
    text = text.replace('cfg.MaxOrder=decimal.NewFromInt(49)', f'cfg.MaxOrder=decimal.RequireFromString("{max_order}")')
    # Live runs one cycle per minute; inside the execution hour both arms get
    # the same number of cycles so repeated capped orders can execute.
    old = 'replayClock.Store(f.Hours[k].TS+45)\n     if err:=e.Cycle(context.Background());err!=nil {if errors.Is(err,ErrEntriesPaused){paused++} else if strings.Contains(err.Error(),"ledger halted:"){halts++} else {t.Fatalf("hour=%d: %v",k,err)}}'
    assert text.count(old) == 1, 'cycle loop changed'
    new = ('cycles:=1;if time.Unix(f.Hours[k].TS,0).UTC().Hour()==1 {cycles=%d}\n' % args.window_cycles +
           '     for c:=0;c<cycles;c++ {replayClock.Store(f.Hours[k].TS+45+int64(c)*60)\n'
           '     if err:=e.Cycle(context.Background());err!=nil {if errors.Is(err,ErrEntriesPaused){paused++} else if strings.Contains(err.Error(),"ledger halted:"){halts++} else {t.Fatalf("hour=%d: %v",k,err)}}}')
    text = text.replace(old, new)
    old = 'range []int{0,28}'
    assert text.count(old) == 1
    if any(d not in (0, 28, 56, 84) for d in args.geometries):
        raise ValueError('geometry was not preregistered')
    text = text.replace(old, 'range []int{'+','.join(map(str, args.geometries))+'}')
    assert text.count('[]float64{.003,.006}') == 1
    text = text.replace('[]float64{.003,.006}', '[]float64{.003,.004}')
    assert text.count('[]float64{0,1}') == 1
    text = text.replace('[]float64{0,1}', '[]float64{1}')
    target = out/'replay_test.go.txt'
    target.write_text(text)
    replace[str(root/'internal/bot/frozen_ledger_research_test.go')] = str(target)
    (out/'overlay.json').write_text(json.dumps({'Replace': replace}, indent=2)+'\n')
    for file in ('fixture.json', 'markets.json'):
        p = root/'data/frontier_20260912/ledger'/file
        hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'inputs.json').write_text(json.dumps(hashes, indent=2)+'\n')
    (out/'config.json').write_text(json.dumps(dict(budget=str(budget), max_order=str(max_order), reserve=str(reserve), slots=args.slots, cooldown=args.cooldown, stop=args.stop, minhold=args.minhold, regime=args.regime, halt_peak=args.halt_peak, halt_daily=args.halt_daily,
        window_cycles=args.window_cycles, geometries=args.geometries), indent=2)+'\n')


if __name__ == '__main__':
    main()
