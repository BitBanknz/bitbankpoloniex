#!/usr/bin/env python3
"""Separate fixed dust-allocation study, using the same frozen ledger harness."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'data/frontier_20260912/ledger_dust/overlay'
out.mkdir(parents=True, exist_ok=True)
replace, hashes = {}, {}
for name in ['engine.go', 'market.go', 'signals.go', 'client.go']:
    source = root / 'internal/bot' / name
    text = source.read_text()
    hashes[str(source.relative_to(root))] = hashlib.sha256(source.read_bytes()).hexdigest()
    text = text.replace('time.Now()', 'replayNow()')
    if name == 'client.go':
        text = text.replace('c.mu.Lock()', 'if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
        text = text.replace('delay := time.Until(c.next)', 'delay := time.Duration(0)')
    if name == 'engine.go':
        edits = [
            ('for _, p := range s.Holdings {\n\t\t\t\tif !p.Imported {',
             'for heldSymbol, p := range s.Holdings {\n\t\t\t\tif !p.Imported && (!replayDustMode || !replayIsDust(p, bySymbol[heldSymbol], books[heldSymbol])) {'),
            ('if _, held := s.Holdings[symbol]; held || now.Before(s.Cooldown[symbol]) {',
             'if p, held := s.Holdings[symbol]; (held && (!replayDustMode || !replayIsDust(p, bySymbol[symbol], books[symbol]))) || now.Before(s.Cooldown[symbol]) {'),
            ('if p.Entered.IsZero() {', 'if p.Entered.IsZero() || replayDustMode {'),
            ('owned := s.Holdings[m.Symbol].Quantity',
             '''owned := s.Holdings[m.Symbol].Quantity
    if replayDustMode && side == "BUY" && replayIsDust(s.Holdings[m.Symbol], m, b) {
        bid, _ := decimal.NewFromString(b.Bids[0])
        spend = decimal.Min(spend, limit.Sub(owned.Mul(bid)))
    }'''),
        ]
        for before, after in edits:
            assert text.count(before) == 1, before
            text = text.replace(before, after)
    target = out / (name + '.txt')
    target.write_text(text)
    replace[str(source)] = str(target)

original = (root / 'research/ledger_20260912/replay_test.go.txt').read_text()
(out / 'base_driver.go.txt').write_text(original)
driver = original.replace('var replayBonus float64', 'var replayDustMode bool')
start, end = driver.index('func replayTargets('), driver.index('func replayRead(')
driver = driver[:start] + '''func replayIsDust(p Position,m Market,b Book) bool {
 if !p.Quantity.IsPositive() || len(b.Bids)==0 || m.Limits.PriceScale<0 || m.Limits.QuantityScale<0 {return false}
 bid,err:=decimal.NewFromString(b.Bids[0]);if err!=nil || !bid.IsPositive(){return false}
 minQty,err:=decimal.NewFromString(m.Limits.MinQuantity);if err!=nil{return false}
 minAmount,err:=decimal.NewFromString(m.Limits.MinAmount);if err!=nil{return false}
 qty:=p.Quantity.RoundFloor(int32(m.Limits.QuantityScale));price:=bid.RoundFloor(int32(m.Limits.PriceScale))
 return qty.LessThan(minQty) || qty.Mul(price).LessThan(minAmount)
}
''' + driver[end:]
for before,after in [
    ('for _,bonus:=range []float64{0,.4}', 'for _,dustMode:=range []bool{false,true}'),
    ('replayBonus=bonus', 'replayDustMode=dustMode'),
    ('Fee,Bonus float64', 'Fee float64; DustMode bool'),
    ('{days,fee,bonus,', '{days,fee,dustMode,'),
    ('bonus=%g', 'dust=%t'),
    ('days,fee,bonus,a/bars', 'days,fee,dustMode,a/bars'),
    ('ledger_fee%g_bonus%g.json",fee,bonus', 'ledger_fee%g_dust%t.json",fee,dustMode'),
]:
    assert before in driver, before
    driver=driver.replace(before,after)
driver += '''
func TestDustRebuildPreservesUnitsAndAllocationCeiling(t *testing.T) {
 replayDustMode=true;replayClock.Store(1768352445)
 e:=engine(t);s,err:=e.read();if err!=nil {t.Fatal(err)}
 m:=market();b:=book();b.TS=replayNow().UnixMilli()
 oldQty:=decimal.RequireFromString("0.0001")
 s.Holdings[m.Symbol]=Position{Quantity:oldQty,Peak:decimal.NewFromInt(4000),Entered:replayNow().Add(-1000*time.Hour)}
 if !replayIsDust(s.Holdings[m.Symbol],m,b){t.Fatal("minimum-notional remnant consumed an active slot")}
 if err:=e.trade(context.Background(),&s,m,b,"BUY",replayNow(),"dust_research");err!=nil {t.Fatal(err)}
 if len(s.Fills)!=1 {t.Fatal("missing rebuild fill")}
 pos:=s.Holdings[m.Symbol];fill:=s.Fills[0]
 if !pos.Quantity.Equal(oldQty.Add(fill.Quantity)) || !pos.Entered.Equal(replayNow()) || pos.Peak.GreaterThan(decimal.NewFromInt(2100)) {t.Fatal("units or new lot clock/basis incorrect")}
 bid:=decimal.RequireFromString(b.Bids[0]);if pos.Quantity.Mul(bid).GreaterThan(e.Config.MaxOrder) {t.Fatal("rebuilt allocation exceeded existing dollar ceiling")}
 replayDustMode=false
}
'''
target = out / 'replay_test.go.txt'
target.write_text(driver)
replace[str(root / 'internal/bot/frozen_ledger_research_test.go')] = str(target)
(out.parent / 'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
(out.parent / 'production-source-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
print('Prepared separate dust overlay; production and first-study sources unchanged.')
