"""Write the result and seal completed checks; never qualifies live deployment."""
from decimal import Decimal as D
import json
from pathlib import Path
import time

from build import BASE, HERE, OUT, REPO, read, save, sha


def main():
    history=read(OUT/'historical_accounts/verification.json')
    observed=read(OUT/'observed_accounts/verification.json')
    attribution=read(OUT/'historical_accounts/attribution.json')
    regression=read(OUT/'regressions/verification.json')
    correction=read(OUT/'clock_fixture_correction/verification.json')
    clocks=read(OUT/'clock_fixture_correction/all_fixture_clocks.json')
    first_difference=read(OUT/'historical_accounts/first_difference.json')
    assert all(p['verified'] for p in (history,observed,attribution,regression,correction,clocks,first_difference))
    assert clocks['valid_cases']==240 and clocks['states_checked']==477
    checked={}
    def check(path,expected):
        value=sha(path);assert value==expected,str(path);checked[str(path)]=value
    for name in ('registration.json','regressions/registration.json','historical_accounts/registration.json',
                 'observed_accounts/registration.json','clock_fixture_correction/registration.json'):
        registration=read(OUT/name)
        for path,digest in registration['hashes'].items():check(path,digest)
    for path,digest in clocks['hashes'].items():check(path,digest)
    for path,digest in first_difference['hashes'].items():check(path,digest)
    for name in ('observed','historical'):
        for path,digest in read(OUT/name/'verification.json')['hashes'].items():check(path,digest)
    for name,digest in read(OUT/'validation.json')['sources'].items():check(OUT/'source'/name,digest)
    for name,digest in observed['output_hashes'].items():check(OUT/'observed_accounts'/name,digest)
    check(OUT/'historical_accounts/accounts.json',history['accounts_sha256'])
    check(OUT/'historical_accounts/verification.json',attribution['history_verification_sha256'])
    check(HERE/'attribution.py',attribution['analyzer_sha256'])
    for name,digest in attribution['plot_hashes'].items():check(OUT/'historical_accounts'/name,digest)
    check(OUT/'regressions/cycles.jsonl.gz',regression['cycles_sha256'])
    check(OUT/'clock_fixture_correction/cycles.json',correction['cycles_sha256'])
    account_pairs=read(OUT/'historical_accounts/accounts.json')
    for pair in account_pairs:
        for binding in pair['bindings'].values():check(binding['path'],binding['sha256'])
    assert observed['native_cycles']==19320 and observed['paired_cycles']==9660
    assert history['accounts_per_arm']==45 and history['default_off_complete_ledger_parity']
    assert regression['native_money_checks']==regression['native_race_cycles']==240
    assert correction['superseded_invalid_clock_executions']==correction['corrected_native_money_checks']==correction['corrected_native_race_checks']==12
    tests={}
    for label in ('suite','race'):
        command=read(OUT/(label+'.json'));assert command['returncode']==0
        check(OUT/(label+'.log'),command['log_sha256'])
        events=[json.loads(line) for line in (OUT/(label+'.log')).read_text().splitlines() if line.startswith('{')]
        tests[label]={action:sum(event.get('Action')==action and 'Test' in event for event in events) for action in ('pass','fail','skip')}
        assert tests[label]=={'pass':103,'fail':0,'skip':0}
    vet=read(OUT/'vet.json');assert vet['returncode']==0;check(OUT/'vet.log',vet['log_sha256'])

    table=[]
    for group in history['groups']:
        case=group['case'];horizon='Continuous' if not case['days'] else str(case['days'])+' days'
        a,b=group['control'],group['repeat']
        table.append(f"| {horizon} | {round(case['fee']*10000)} | {group['accounts']} | {D(a['mean_return_pct']):.4f}% → {D(b['mean_return_pct']):.4f}% | {D(a['maximum_drawdown_pct']):.4f}% → {D(b['maximum_drawdown_pct']):.4f}% | {a['fills']} → {b['fills']} |")
    chart=OUT/'historical_accounts/paired_changes.png'
    same=attribution['accounts_with_same_economic_fills']
    worst_dd_increase=max(D(pair['difference']['max_drawdown_pct']) for pair in account_pairs)
    doc=f'''# Minute protective reductions: tested paper candidate, no deployment qualification

The isolated treatment allows one capped protective sell per actual UTC minute
for a non-imported holding below its existing stop. The guarded control allows
one per forecast decision hour. Successful duplicate calls within a minute keep
the same durable order ID, even if forecast availability changes. Imported
allocations and ordinary rotation exits retain their existing behavior.

The research flag defaults off and rejects live mode and experimental fallback.
The order cap, daily cap, stop threshold, reserve, cooldown, quote validation,
depth participation, forecasts and training are unchanged. This follows the
[fixed protocol](2026-09-26-protective-minute-prereg.md). All changes are in a
private source copy based on the authenticated guarded release.

## All historical outcomes

Across all 45 paired accounts, treatment return was higher in {history['higher_return']},
lower in {history['lower_return']}, and equal in {history['equal_return']}. Observed
account drawdown was lower in {history['lower_drawdown']} and higher in
{history['higher_drawdown']}. There were {attribution['better_return_and_no_worse_drawdown']}
pairs with higher return and no worse drawdown. These are correlated account
windows and fee arms, not 45 independent observations. No losing account or
partial tail was removed. The largest individual account drawdown increase was
{worst_dd_increase:.6f} percentage points; group maxima can hide that worsening.

| Horizon | Fee, bps/side | Accounts | Mean return: control → treatment | Largest account drawdown: control → treatment | Fills: control → treatment |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(table)}

All 45 default-off reports and complete ledgers were byte-identical to the
sealed guarded-release controls. The independent Decimal reference checked
both arms, including cash, quantity, fees, dust, peaks, decision IDs, cooldowns,
daily allowances and reported marks: {history['exact_comparisons']:,} exact
comparisons, maximum metric error {history['maximum_metric_error']}. A corrupted
decision ID was rejected. {same} pairs had identical economic fills after
excluding the treatment's deliberately different client IDs.

All twelve changed accounts first diverged at one of only three underlying ZEC
episodes (April 16, May 12, and June 18). In each, the control's 00:00 protective
sell used the forecast's 01:00 decision key. That blocked the following 01:00
sell; the treatment's actual observation-time key permitted it. This establishes
the first divergence, not the cause of the entire eventual PnL difference.
Actual-hour keying and repeated minute reductions are combined in this treatment;
their separate performance effects have not been isolated. The
[first-difference proof]({OUT/'historical_accounts/first_difference.json'})
retains the relevant fills and decision IDs for every changed account.

[Paired return/drawdown chart]({chart}) and
[all account comparisons]({OUT/'historical_accounts/accounts.json'}).

The candidate produced {attribution['repeated_protective_hour_groups']} symbol/hour
groups with multiple protective sells. In
{attribution['repeated_groups_above_one_quote_10pct_allowance']} of those groups,
cumulative sold quantity exceeded the modeled 10% allowance of a single quote.
The retained historical driver refreshes the same hourly price and synthetic
depth on each minute call during the entry hour. Actual replenishment was not
observed. These counts describe simulation dependence, not a demonstrated
exchange liquidity violation. Outside the entry hour this historical driver
calls the strategy once per hour, so it does not fully exercise the treatment.

## Native behavior and observed-data comparison

Qualification passed 103 native suite tests, 103 race tests, and vet. There are
240 valid complete-cycle accounting checks, each also repeated using the race
binary. They cover duplicate calls, consecutive capped reductions, full exit
and cooldown, forecast-clock changes, recovered prices, shallow depth, rejected
quotes, exhausted daily limits, risk halts and another holding's missing quote.

During review, twelve original clock-change executions were found to have an
invalid seed chronology: the test clock moved back an hour while the prior
cycle and equity mark stayed in the future. Those executions are retained and
superseded by twelve corrected cases. All corrected before/after state clocks
are causal. Expected sell counts, financial checks, tolerances and the trading
implementation were unchanged. The 240 valid checks exclude the superseded
executions and include their corrected replacements.

The corrected forecast-clock test exposes a separate consequence of the old
hour key: losing a pre-execution forecast within the same minute can change the
decision hour and permit another protective sell. The treatment's actual-minute
key suppresses that duplicate. This is a synthetic native reproduction, not a
claimed live incident.

All three fee controls and treatments were replayed with their own continuing
state across the fixed public prefix 78–3297: 19,320 native account cycles and
9,660 paired cycle comparisons. Every treatment state and financial output
matched its control. The prefix contained no protective stops and provides no
observed-market performance test of faster exits. Its previously reported
returns remain −0.592454%, −0.649675%, and −0.764116% at 30/40/60 bps per side.

Synthetic falling and rebounding paths explicitly show the tradeoff. At 30 bps,
the falling path ended at 489.6153 USDT with the treatment versus 479.5530 with
the control. The rebound ended at 495.3060 versus 510.1530. These deliberately
constructed paths verify behavior and accounting; they are not alpha evidence.

## Decision

Retain this as a tested research candidate. No live algorithm promotion or
activation is justified by this study. The historical fixture is reused,
uses hourly prices and synthetic liquidity, and has no independent holdout.
Fee stress does not establish realistic fills, latency, intraminute prices or
liquidity replenishment. The observed public prefix did not activate the rule.
The owner's 35% rolling-28-day and 40% full-window drawdown requirements remain
unchanged and are not established by this experiment.

Evidence root: `{OUT}`. Existing live code, credentials, trading services,
account state, sealed studies and running paper workers were not changed.
'''
    path=REPO/'docs/2026-09-26-protective-minute-results.md'
    with path.open('x') as f:f.write(doc)
    artifacts=set(p for p in OUT.rglob('*') if p.is_file())
    artifacts.update(p for p in HERE.iterdir() if p.is_file())
    artifacts.update([path,REPO/'docs/2026-09-26-protective-minute-prereg.md'])
    save(OUT/'completion.json',dict(verified=True,at_ns=time.time_ns(),tests=tests,
        valid_native_money_and_race_cases=240,superseded_clock_executions=12,
        history_accounts_per_arm=45,observed_native_cycles=19320,observed_paired_cycles=9660,
        deployment_qualified=False,live_changed=False,ongoing_studies_changed=False,
        upstream_hash_checks=checked,artifact_hashes={str(p):sha(p) for p in sorted(artifacts)}))
    print(json.dumps(dict(verified=True,higher_return=history['higher_return'],lower_return=history['lower_return'],
                         equal_return=history['equal_return'],report=str(path),deployment_qualified=False)),flush=True)


if __name__=='__main__':main()
