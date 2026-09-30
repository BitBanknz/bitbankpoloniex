"""Seal the clock-only ablation after every registered check has completed."""
from decimal import Decimal as D
import json
from pathlib import Path
import time

from build import HERE, OUT, REPO, read, save, sha


def main():
    root=OUT/'historical_accounts'
    history=read(root/'verification.json');comparison=read(root/'three_way_verification.json')
    observed=read(OUT/'observed_accounts/verification.json')
    regression=read(OUT/'regressions/verification.json');arrival=read(OUT/'forecast_arrival/verification.json')
    clocks=read(OUT/'exact_clock_verification.json')
    assert all(proof['verified'] for proof in (history,comparison,observed,regression,arrival,clocks))
    assert clocks['cases']==278 and clocks['all_clocks_causal_at_nanosecond_precision']
    assert history['accounts_per_arm']==comparison['accounts']==45
    assert observed['native_cycles']==19320 and observed['paired_cycles']==9660
    assert regression['native_money_checks']==regression['native_race_cases']==254
    assert arrival['native_money_checks']==arrival['native_race_cases']==24
    assert regression['all_fixture_clocks_causal'] and arrival['all_fixture_clocks_causal']
    assert comparison['all_clock_sells_at_most_once_per_symbol_per_actual_hour']
    checked={}
    def check(path,digest):
        actual=sha(path);assert actual==digest,str(path);checked[str(path)]=actual
    for folder in ('','regressions','forecast_arrival','historical_accounts','observed_accounts'):
        proof=read(OUT/folder/'registration.json')
        for path,digest in proof['hashes'].items():check(path,digest)
    for folder in ('observed','historical'):
        for path,digest in read(OUT/folder/'verification.json')['hashes'].items():check(path,digest)
    for name,digest in read(OUT/'validation.json')['sources'].items():check(OUT/'source'/name,digest)
    for name,digest in observed['output_hashes'].items():check(OUT/'observed_accounts'/name,digest)
    check(root/'accounts.json',history['accounts_sha256'])
    for path,digest in comparison['hashes'].items():check(path,digest)
    for path,digest in clocks['hashes'].items():check(path,digest)
    for name,digest in comparison['output_hashes'].items():check(root/name,digest)
    for folder,proof in [('regressions',regression),('forecast_arrival',arrival)]:
        check(OUT/folder/'cycles.jsonl.gz',proof['cycles_sha256'])
    for row in read(root/'three_way_accounts.json'):
        for binding in row['bindings'].values():check(binding['path'],binding['sha256'])
    tests={}
    for label in ('suite','race'):
        proof=read(OUT/(label+'.json'));assert proof['returncode']==0;check(OUT/(label+'.log'),proof['log_sha256'])
        events=[json.loads(line) for line in (OUT/(label+'.log')).read_text().splitlines() if line.startswith('{')]
        tests[label]={action:sum(event.get('Action')==action and 'Test' in event for event in events) for action in ('pass','fail','skip')}
        assert tests[label]=={'pass':103,'fail':0,'skip':0}
    vet=read(OUT/'vet.json');assert vet['returncode']==0;check(OUT/'vet.log',vet['log_sha256'])
    table=[]
    for group in comparison['groups']:
        case=group['case'];label='Continuous' if case['days']==0 else str(case['days'])+' days'
        returns=' → '.join(f"{D(group[arm]['mean_return_pct']):.4f}%" for arm in ('control','clock','minute'))
        drawdowns=' → '.join(f"{D(group[arm]['maximum_drawdown_pct']):.4f}%" for arm in ('control','clock','minute'))
        table.append(f"| {label} | {round(case['fee']*10000)} | {group['accounts']} | {returns} | {drawdowns} |")
    cv=comparison['clock_minus_control'];mv=comparison['clock_minus_minute']
    doc=f'''# Protective clock ablation: actual-hour keys without minute selling

This private candidate keys protective sells for non-imported positions to the
actual observed UTC hour, independently of the forecast's execution hour. It
retains the existing one-successful-sell-per-symbol-per-hour limit and ordinary
decision suffix. The previous minute candidate also allowed later-minute sells
within an hour; this ablation separates that added frequency from the clock rule.

Against the guarded control, return improved in {cv['higher_return']} of 45
historical accounts, worsened in {cv['lower_return']}, and was equal in
{cv['equal_return']}. Drawdown improved in {cv['lower_drawdown']} and worsened in
{cv['higher_drawdown']}; the largest increase was
{D(cv['largest_drawdown_increase_pp']):.6f} percentage points. Against the minute
candidate, the clock-only return was higher in {mv['higher_return']}, lower in
{mv['lower_return']}, and equal in {mv['equal_return']}. These are reused,
correlated windows and cost arms, not independent holdout results.

No live deployment is qualified by this experiment. The source and research
protocol were fixed before running this arm, following
[the ablation preregistration](2026-09-26-protective-clock-prereg.md).

## All registered historical groups

Values in each sequence are **guarded control → clock-only → minute selling**.
Reset groups retain their partial final accounts. Individual account drawdown
worsening can be hidden by a group's largest drawdown; the complete paired
differences are retained separately.

| Horizon | Fee, bps/side | Accounts | Mean return: control → clock → minute | Largest account drawdown: control → clock → minute |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(table)}

The clock-only arm has identical economic fills to the control in
{comparison['same_economic_fills_vs_control']} accounts and to the minute arm in
{comparison['same_economic_fills_vs_minute']}. Client IDs are excluded only for
this economic-fill comparison; every arm's complete decision IDs were checked
by the independent accounting reference.

Only three comparisons differ economically between clock-only and minute
selling, all from the same April 16 ZEC episode at the three fee levels. The
minute arm earned more in those cases, by up to
{abs(D(mv['largest_return_decrease_pp'])):.6f} percentage points, and also had
higher drawdown in those same three comparisons. The other 42 economic paths
were identical. Thus the extra selling frequency did not explain the other
changed accounts in the earlier experiment. All clock-only/control first
differences remain concentrated in three ZEC episodes (April 16, May 12 and
June 18), not twelve independent opportunities.

[Three-way return/drawdown chart]({root/'clock_ablation.png'}) and
[all paired accounts, fees, fills and first differences]({root/'three_way_accounts.json'}).

## Behavior and accounting verification

The native suite passed 103 tests, the native race suite passed 103, and vet
passed. There were 278 valid complete-cycle accounting checks, each repeated
under the race detector: 254 core cases plus 24 unavailable-to-available forecast
arrival cases. Prior-cycle, equity-mark, position-entry and fill timestamps were
checked for causality in every before/after state. A fresh process respected the
persisted decision key after reloading the ledger.
An independent nanosecond-precision audit checked all 553 non-null states and
rejected four mutations that moved a prior-cycle, equity, entry or fill timestamp
just one nanosecond into the future.

Two concrete failures of the old clock were reproduced. A pre-execution sell
could consume the following execution-hour key and suppress that later hour's
reduction. Separately, losing or receiving a forecast within the current hour
could switch the key between actual and future hours, allowing another sell.
The clock-only candidate allows one actual-hour reduction in both situations.
Consecutive minute calls do not enable extra reductions. Hour/day boundaries,
full exit and cooldown, imported and ordinary exits, depth, spread/stale/missing
quotes, daily caps, risk halts and incomplete valuation were checked.

All 45 default-off historical reports and full ledgers were byte-identical to
the sealed guarded-release baseline. Native control ledgers were also identical
across the two experiments. The independent Decimal audit made
{history['exact_comparisons']:,} exact comparisons, with maximum reported metric
error {history['maximum_metric_error']}. A corrupted decision ID was rejected.
All {comparison['clock_sell_hours']:,} candidate symbol/hour sell groups contained
at most one successful sell.

The observed-book replay covered all three fees on fixed source indices 78–3297
with each arm's own continuing state: 19,320 native account executions and 9,660
paired comparisons. Every treatment state and financial output matched its
guarded control. The prefix had no protective stops, so this is compatibility
evidence and does not demonstrate a performance benefit for the new rule.

## Limits and decision

Both the historical data and the observed prefix were reused, not held out.
The historical driver uses hourly prices and synthetic books, repeats those
quotes during the entry hour, and calls only once per hour outside that window.
It does not capture every real forecast-availability transition, intraminute
price move, replenishment event, queue position or realized fill. Fee stress
does not replace those missing execution observations.

This candidate establishes more consistent decision timing in native tests.
It does not establish durable alpha or the owner's 35% rolling-28-calendar-day /
40% full-window drawdown requirements. Its private flag defaults off and rejects
live mode and fallback mode. Sizing, order/daily caps, protective thresholds,
cash reserve, cooldown, forecasting, training, imported allocations and ordinary
rotation exits were not changed. Existing live processes, account state and
ongoing paper studies were not modified.

Evidence root: `{OUT}`.
'''
    document=REPO/'docs/2026-09-26-protective-clock-results.md'
    with document.open('x') as f:f.write(doc)
    artifacts={p for p in OUT.rglob('*') if p.is_file()}
    artifacts.update(p for p in HERE.iterdir() if p.is_file())
    artifacts.update([document,REPO/'docs/2026-09-26-protective-clock-prereg.md'])
    save(OUT/'completion.json',dict(verified=True,at_ns=time.time_ns(),tests=tests,
        native_money_and_race_cases=278,historical_accounts_per_arm=45,observed_native_cycles=19320,
        actual_hour_sell_limit_preserved=True,clock_minus_control=cv,clock_minus_minute=mv,
        live_changed=False,ongoing_studies_changed=False,deployment_qualified=False,
        upstream_hash_checks=checked,artifact_hashes={str(p):sha(p) for p in sorted(artifacts)}))
    print(dict(verified=True,clock_minus_control=cv,clock_minus_minute=mv,document=str(document)),flush=True)

if __name__=='__main__':main()
