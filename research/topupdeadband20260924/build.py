"""Build a private, default-off top-up gap treatment from authenticated source."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path('/vfast/data/code/bitbankpoloniex')
HERE=Path(__file__).resolve().parent
OUT=Path('/vfast/data/trading_research_20260924/poloniex_topup_deadband_v1')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)


def main():
    registered=read(OUT/'registration.json')['hashes']
    assert all(sha(p)==h for p,h in registered.items())
    src=OUT/'source';src.mkdir(exist_ok=False)
    for name in registered:
        p=Path(name)
        if p.is_relative_to(ROOT) and (p.suffix=='.go' or p.name in ('go.mod','go.sum')):
            q=src/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
    engine=src/'internal/bot/engine.go'
    text=engine.read_text()
    text=replace(text,'SlotTopUp            bool', 'SlotTopUpGapFraction float64 // minimum fraction of a slot target before topping up; zero preserves the existing floor\n\tSlotTopUp            bool')
    text=replace(text,'func (c Config) Validate() error {','func (c Config) Validate() error {\n\tif !finite(c.SlotTopUpGapFraction) || c.SlotTopUpGapFraction < 0 || c.SlotTopUpGapFraction >= 1 {\n\t\treturn errors.New("slot top-up gap fraction must be finite and in [0,1)")\n\t}')
    text=replace(text,'func (c Config) reserve(budget decimal.Decimal) decimal.Decimal {','''func (c Config) topUpMinGap(budget decimal.Decimal) decimal.Decimal {
    floor := c.MaxOrder.Mul(decimal.NewFromFloat(.25))
    if c.SlotTopUp && !c.mirror() {
        return decimal.Max(floor, c.slotTarget(budget).Mul(decimal.NewFromFloat(c.SlotTopUpGapFraction)))
    }
    return floor
}

func (c Config) reserve(budget decimal.Decimal) decimal.Decimal {''')
    text=replace(text,'gap.LessThan(e.Config.MaxOrder.Mul(decimal.NewFromFloat(.25)))','gap.LessThan(e.Config.topUpMinGap(s.Budget))')
    engine.write_text(text)
    tests=src/'internal/bot/topup_gap_test.go'
    shutil.copyfile(HERE/'topup_gap_test.go.txt',tests)
    # Exercise the actual repeated-order fixture, with only the treatment enabled.
    original=(src/'internal/bot/topup_test.go').read_text()
    begin=original.index('func TestSlotTopUpFillsHeldTargetWithCappedOrders')
    end=original.index('\nfunc TestCashReserveConfig',begin)
    body=original[begin:end].replace('TestSlotTopUpFillsHeldTargetWithCappedOrders','TestSlotTopUpDeadbandReducesRepeatedBuys')
    body=replace(body,'e.Config.SlotTopUp = topUp','e.Config.SlotTopUp = topUp\n\t\te.Config.SlotTopUpGapFraction = .25')
    body=replace(body,'mark.LessThan(d("193")) || mark.GreaterThan(d("200"))','mark.LessThan(d("150")) || mark.GreaterThan(d("175"))')
    body=body.replace('len(after.Fills) != 8 || after.OrdersToday != 8','len(after.Fills) != 6 || after.OrdersToday != 6').replace('expected eight capped top-ups','expected six capped top-ups')
    # The copied function uses the original imports; keep this test in a separate file.
    integration=src/'internal/bot/topup_gap_integration_test.go'
    integration.write_text(original[:begin].split('// A held rotation')[0]+body+'\n')
    subprocess.run(['gofmt','-w',str(engine),str(tests),str(integration)],check=True)
    sources={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()}
    patch=''.join(''.join(difflib.unified_diff((ROOT/p.relative_to(src)).read_text().splitlines(True) if (ROOT/p.relative_to(src)).exists() else [],
        p.read_text().splitlines(True),fromfile='a/'+str(p.relative_to(src)) if (ROOT/p.relative_to(src)).exists() else '/dev/null',tofile='b/'+str(p.relative_to(src)))) for p in (engine,tests,integration))
    (OUT/'native.patch').write_text(patch)
    receipts=[]
    for label,argv in [('suite',['go','test','./...','-count=1','-json']),('race',['go','test','-race','./...','-count=1','-json']),('vet',['go','vet','./...'])]:
        with (OUT/(label+'.log')).open('x') as log:
            p=subprocess.run(argv,cwd=src,env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly'},stdout=log,stderr=subprocess.STDOUT)
        receipt=dict(argv=argv,returncode=p.returncode,log_sha256=sha(OUT/(label+'.log')));save(OUT/(label+'.json'),receipt);assert p.returncode==0,(label,OUT/(label+'.log'))
        receipts.append(receipt);print('DEADBAND_BUILD',label,flush=True)
    assert all(sha(p)==h for p,h in registered.items())
    assert all(sha(src/p)==h for p,h in sources.items())
    save(OUT/'validation.json',dict(verified=True,sources=sources,commands=receipts,patch_sha256=sha(OUT/'native.patch'),
        builder_sha256=sha(__file__),test_template_sha256=sha(HERE/'topup_gap_test.go.txt'),registration_sha256=sha(OUT/'registration.json'),live_changed=False))


if __name__=='__main__':main()
