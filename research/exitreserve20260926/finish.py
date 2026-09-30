"""Report every registered comparison and seal the completed reservation study."""
from collections import Counter
from decimal import Decimal as D
import json
from pathlib import Path
import subprocess
import time

from build import ARMS, BASE, HERE, OUT, PARENT, REPO, read, save, sha


def comparisons(accounts, control):
    returns = [D(row['arms']['reserve3']['return_pct']) - D(row['arms'][control]['return_pct']) for row in accounts]
    drawdowns = [D(row['risk']['reserve3']['full_drawdown_pct']) - D(row['risk'][control]['full_drawdown_pct']) for row in accounts]
    episodes = Counter((r['first_difference'][control]['at'], r['first_difference'][control]['symbol'],
                        r['first_difference'][control]['side']) for r in accounts if not r['first_difference'][control]['equal'])
    return dict(higher_return=sum(x > 0 for x in returns), lower_return=sum(x < 0 for x in returns),
                equal_return=sum(x == 0 for x in returns), lower_drawdown=sum(x < 0 for x in drawdowns),
                higher_drawdown=sum(x > 0 for x in drawdowns), equal_drawdown=sum(x == 0 for x in drawdowns),
                largest_return_gain_pp=str(max(returns)), largest_return_loss_pp=str(min(returns)),
                largest_drawdown_increase_pp=str(max(drawdowns)), largest_drawdown_reduction_pp=str(min(drawdowns)),
                distinct_first_divergences=[dict(at=at, symbol=symbol, side=side, accounts=count)
                                           for (at, symbol, side), count in sorted(episodes.items())])


def main():
    history = read(OUT / 'historical_audit_v2/verification.json')
    observed = read(OUT / 'observed_accounts/verification.json')
    regression = read(OUT / 'regressions_v3/verification.json')
    assessment = read(OUT / 'assessment/verification.json')
    sources = read(OUT / 'source_audit/verification.json')
    attribution = read(OUT / 'observed_attribution/verification.json')
    assert all(p['verified'] for p in (history, observed, regression, assessment, sources, attribution))
    assert history['accounts_per_arm'] == assessment['accounts_per_arm'] == 45
    assert history['total_accounts'] == 135 and assessment['groups'] == 9
    assert history['all_three_arms_ledger_byte_exact'] and history['maximum_daily_orders'] == 8
    assert regression['native_money_checks'] == regression['native_race_cases'] == 256
    assert regression['default_off_full_output_cases'] == 30
    assert observed['native_cycles'] == 28980 and observed['matched_control_comparisons'] == 9660
    assert observed['baseline_full_output_parity'] and observed['candidate_and_nine_order_control_financial_paths_identical']
    assert assessment['first_divergences_explained_by_registered_rule']
    assert len(assessment['clock_and_budget_mutations_rejected']) == 6
    checked = {}

    def check(path, digest):
        assert sha(path) == digest, str(path)
        checked[str(path)] = digest

    for subdir in ('', 'regressions', 'regressions_v2', 'regressions_v3', 'historical_accounts', 'historical_audit_v2', 'observed_accounts'):
        proof = read(OUT / subdir / 'registration.json')
        for path, digest in proof['hashes'].items():
            check(path, digest)
    for subdir in ('observed', 'historical', 'assessment', 'source_audit', 'observed_attribution'):
        proof = read(OUT / subdir / 'verification.json')
        for key in ('hashes', 'source_hashes', 'output_hashes'):
            for path, digest in proof.get(key, {}).items():
                check(path, digest)
    for name, digest in read(OUT / 'validation.json')['sources'].items():
        check(OUT / 'source' / name, digest)
    for name, digest in observed['output_hashes'].items():
        check(OUT / 'observed_accounts' / name, digest)
    check(OUT / 'historical_audit_v2/accounts.json', history['accounts_sha256'])
    check(OUT / 'regressions_v3/cycles.jsonl.gz', regression['cycles_sha256'])
    check(OUT / 'regressions_v3/examples.json', regression['examples_sha256'])
    for subdir, proof in (('historical_audit_v2', history), ('observed_accounts', observed), ('regressions_v3', regression)):
        check(OUT / subdir / 'registration.json', proof['registration_sha256'])
    routing = read(HERE / 'analysis_audit_routing_v2.json')
    check(routing['source'], routing['source_sha256'])
    check(routing['target'], routing['target_sha256'])
    routed = Path(routing['source']).read_text()
    for old, new in routing['replacements']:
        assert routed.count(old) == routing['occurrences']
        routed = routed.replace(old, new)
    assert routed == Path(routing['target']).read_text()

    accounts = read(OUT / 'assessment/accounts.json')
    groups = read(OUT / 'assessment/groups.json')
    for row in accounts:
        for arm, binding in row['bindings'].items():
            check(binding['path'], binding['sha256'])
            if arm == 'baseline':
                expected = PARENT / 'parity' / row['case'] / Path(binding['path']).name
                check(expected, binding['sha256'])
    for group in groups:
        case = group['case']['id']
        path = OUT / 'historical_accounts/baseline' / case / 'results.jsonl'
        check(PARENT / 'parity' / case / 'results.jsonl', sha(path))
    summary = {arm: comparisons(accounts, arm) for arm in ('baseline', 'cap9')}
    save(OUT / 'assessment/paired_summary.json', summary)
    individual = []
    for row in accounts:
        individual.append(dict(case=row['case'], start=row['start'], end=row['end'], comparisons={arm: dict(
            return_difference_pp=str(D(row['arms']['reserve3']['return_pct']) - D(row['arms'][arm]['return_pct'])),
            funded_full_drawdown_difference_pp=str(D(row['risk']['reserve3']['full_drawdown_pct']) - D(row['risk'][arm]['full_drawdown_pct'])),
            rolling_28d_drawdown_difference_pp=str(D(row['risk']['reserve3']['rolling_28d_drawdown_pct']) - D(row['risk'][arm]['rolling_28d_drawdown_pct'])))
            for arm in ('baseline', 'cap9')}))
    save(OUT / 'assessment/individual_differences.json', individual)

    table = []
    failure_table = []
    for group in groups:
        case = group['case']
        label = 'Continuous' if case['days'] == 0 else str(case['days']) + '-day resets'
        fee = round(case['fee'] * 10000)
        values = [' / '.join(f"{D(group['arms'][arm][key]):.4f}" for arm in ARMS)
                  for key in ('mean_return_pct', 'maximum_drawdown_pct')]
        table.append(f"| {label} | {fee} | {group['accounts']} | {values[0]} | {values[1]} | {sum(group['gates'].values())}/{len(group['gates'])} |")
        failures = ', '.join(key for key, passed in group['gates'].items() if not passed) or 'None'
        failure_table.append(f"| {label}, {fee} bps | {failures} |")

    actual = read(OUT / 'observed_accounts/summary.json')
    attribution_rows = read(OUT / 'observed_attribution/attribution.json')
    baseline_pepe = attribution_rows['baseline']['control_fee30']['symbols']['PEPE_USDT']
    candidate_pepe = attribution_rows['reserve3']['control_fee30']['symbols']['PEPE_USDT']
    observed_table = []
    for aid in sorted(actual['baseline']):
        for arm in ARMS:
            row = actual[arm][aid]
            assert row['cycles'] == 3220 and row['sells'] == 0 and row['unmarked'] == 0
            observed_table.append(f"| {aid} | {arm} | {D(row['return_pct']):.6f} | {D(row['dd']):.6f} | {row['buys']} | {D(row['fees']):.6f} |")
    examples = read(OUT / 'regressions_v3/examples.json')
    synthetic_table = []
    for name in ('falling', 'rebounding'):
        values = [next(row['equity'] for row in examples if row['name'] == name and row['fee'] == '.003' and row['arm'] == arm) for arm in ARMS]
        synthetic_table.append(f"| {name} | {' | '.join(values)} |")
    decision = ('Passed the historical screen; still not deployment-qualified.' if assessment['historical_screen_passes']
                else 'Rejected by the fixed historical screen. No deployment is qualified.')
    paired = []
    for arm in ('baseline', 'cap9'):
        p = summary[arm]
        paired.append(f"Against `{arm}`, reserve3 had higher return in {p['higher_return']} accounts, lower in {p['lower_return']}, and equal in {p['equal_return']}. "
                      f"Funded full-window drawdown improved in {p['lower_drawdown']}, worsened in {p['higher_drawdown']}, and was equal in {p['equal_drawdown']}. "
                      f"The largest drawdown increase was {D(p['largest_drawdown_increase_pp']):.6f} percentage points. "
                      f"There were {len(p['distinct_first_divergences'])} distinct first-divergence timestamp/symbol/side combinations across the reused fee and reset arms.")
    rolling_max = max(D(group['arms']['reserve3']['maximum_rolling_28d_drawdown_pct']) for group in groups)
    full_max = max(D(group['arms']['reserve3']['maximum_drawdown_pct']) for group in groups)
    document = REPO / 'docs/2026-09-26-exit-order-reserve-results.md'
    report = f'''# Reserving daily order capacity for exits

**{decision}** The candidate passed {assessment['groups_passing']}/9 complete fee/geometry groups and
{assessment['gates_passed']}/{assessment['gates_total']} individual checks. A pass requires every group and both controls;
the individual-check fraction is not a probability of success.

**The historical simulation did not exercise the new rule.** Every account used
at most eight orders in any UTC day: 36 of the 45 accounts per arm peaked at six,
and nine peaked at eight. All 45 three-arm ledger triples were byte-identical.
Thus this study offers no historical evidence for profitable reserved exits.
By contrast, the retained real-book paper path used twelve buys in one day;
its small PEPE top-ups exercise an order-budget situation absent from these
hourly synthetic-book histories. This is a concrete simulation coverage gap.

The retained paper path consumed its twelve daily order allowances on buys.
This experiment asks whether keeping three allowances available for later sells
improves the account. The fixed arms are `baseline` (12 total, no reserve),
`cap9` (9 total, no reserve), and `reserve3` (12 total, buys blocked from order
count 9 onward). All successful buys and sells consume the same total allowance.
Ordinary sells can also use the reserved capacity; three reserved orders do not
guarantee full liquidation. This is the preregistered test in
[the protocol](2026-09-26-exit-order-reserve-prereg.md), with no parameter rescue.

The private source starts from the authenticated guarded release. Its stop/top-up
guard remains enabled; its original decision clock remains unchanged. The only
changed parent source is `internal/bot/engine.go`, plus two new native tests.
The reserve defaults to zero and rejects live mode and fallback mode.

## All historical groups

Each value sequence is **baseline / cap9 / reserve3**. Returns and drawdowns are
percentages. Drawdown includes the initially funded 495 USDT and every retained
hourly equity mark. Reset groups retain the partial final account.

| Window | Fee bps/side | Accounts/arm | Mean return % | Largest account drawdown % | Checks passed |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(table)}

{chr(10).join(paired)}

The largest candidate sampled rolling 28-calendar-day drawdown was {rolling_max:.6f}%;
the largest funded full-window drawdown was {full_max:.6f}%. These are checks on
the retained marks, not proof of intrahour risk. The required ceilings remain
35% and 40%, respectively. Group maxima can hide individual regressions;
[every paired return and drawdown difference]({OUT/'assessment/individual_differences.json'}) is retained.

The registered first-divergence checks found no differing historical paths.
They therefore provide no evidence of a reserved sale occurring in history.
The synthetic full-cycle tests exercise the boundary explicitly. Every historical
path with identical fills was required to have an identical complete native state.
[The paired summary]({OUT/'assessment/paired_summary.json'}) lists the distinct
first differences; [all accounts]({OUT/'assessment/accounts.json'}) retain their ledger bindings.
Fee arms and overlapping geometries are correlated reused observations.

| Group | Failed registered checks |
| --- | --- |
{chr(10).join(failure_table)}

## Recorded public-market replay

The authenticated prefix 78–3297, 2026-09-24 03:14 through 2026-09-26 08:53 UTC,
was replayed with each arm's own continuing account state. It was already
observed and known to contain no stops. Across 28,980 native cycles, the baseline
matched the original complete outputs and request paths. Reserve3 and cap9 had
identical complete financial paths in all 9,660 paired comparisons, with no sells
and no unmarked cycles. Consequently this prefix cannot establish any benefit
from the additional sell allowance; any difference from baseline is the buying rule.

| Account / fee setting | Arm | Return % | Minute-sampled drawdown % | Buys | Fees USDT |
| --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(observed_table)}

[Observed summary]({OUT/'observed_accounts/summary.json'}) and
[final native account states]({OUT/'observed_accounts/final_states.json'}).
Sequential public snapshots and modeled IOC fills do not establish real execution.

The first nine buys were identical. Baseline then made three more small PEPE
top-ups on September 25. The restricted arms instead made one larger PEPE
top-up on September 26 after the UTC reset. Fewer orders therefore did not mean
less total exposure: PEPE quantity ended at {baseline_pepe['quantity']} for
baseline versus {candidate_pepe['quantity']} for both restricted arms. Turnover
rose from {D(actual['baseline']['control_fee30']['turnover']):.6f} to
{D(actual['reserve3']['control_fee30']['turnover']):.6f} USDT. Return was slightly
worse and sampled drawdown lower at all three fees. The
[per-symbol and per-day accounting attribution]({OUT/'observed_attribution/attribution.json'})
reconciles cash, marked inventory, costs and PnL exactly for all nine accounts.

## Verification and synthetic behavior

Native tests: 104 passed; race tests: 104 passed; vet passed. Thirty default-off
complete cycles matched the authenticated baseline. The 256 full-cycle synthetic
accounting cases all passed and were repeated under the race detector with
identical outputs and paths. They cover shallow buying, reserved protective and
ordinary exits, partial reductions, failed buys, daily exhaustion, duplicates,
process restart, imported holdings, stale/missing/wide books, incomplete valuation,
risk halts and UTC reset. Prior-cycle, mark, position-entry and fill timestamps
were checked at nanosecond precision. Four deliberately future-dated timestamps
and two mutated order budgets were rejected.

All 135 historical accounts were independently reconciled using Decimal cash,
position, fee, fill, mark, decision-ID and order-budget calculations. There were
{history['exact_comparisons']:,} comparisons, with maximum reported metric error
{history['maximum_metric_error']}. All 45 baseline reports and ledgers matched the
guarded release byte-for-byte. Deliberate total-budget, buy-budget and decision-ID
violations were rejected. This reference consumes recorded intents; it is not a
complete independent planner and does not prove every eligible order was emitted.
Four calendar/precision tests and eleven adversarial selection tests passed,
including 100 seeded drawdown comparisons against an every-pair reference.
Focused Python correctness lint passed; the compact research scripts were not
required to pass Ruff's full style rules.

The synthetic shallow-buy example spends nine allowances before a stop. Reserve3
then sells all three small holdings; both exhausted controls cannot sell that day.
The next price either falls further or rebounds. At 30 bps, account equity is:

| Synthetic continuation | Baseline equity | Cap9 equity | Reserve3 equity |
| --- | ---: | ---: | ---: |
{chr(10).join(synthetic_table)}

These constructed outcomes demonstrate both reduced downside and forgone rebound
exposure. They are behavior checks, not estimates of profitability.

Two original fixture failures remain preserved. First, the duplicate-cycle test
incorrectly demanded unchanged equity history: a repeated no-fill observation
updates the mark to include the preceding sale's fees. The corrected test checks
unchanged cash, positions, fills, order count and identity, plus the independently
reconciled mark. Second, the synthetic ordinary-exit entry time used a redundant
`.000000000Z` suffix that Go canonicalized to `Z`; the fixture formatter now
matches Go while preserving the exact nanosecond instant. Native treatment code
and accounting formulas were unchanged for both corrections. Their derivations
and original failed runs are included in the evidence.

The original historical audit also failed its final negative-test assumption:
it expected a baseline ledger to violate a nine-order total or buy limit, but
all ledgers stayed below nine. The preserved native replays and unchanged
financial reference were audited again without rerunning the simulations.
Explicit reference mutations then prohibited all orders (total 0) or all buys
(total 12/reserve 12), and both were rejected, as was a corrupted decision ID.
Separately, the already-required native full-cycle boundary-nine mutations were
rejected by the daily-budget checker. All original historical accounts remain
included, their nonactivation is reported, and selection gates were unchanged.

## Decision and limits

{decision} No favorable fee, reset geometry or reserve size is selected after
the results. Historical books use hourly prices and synthetic depth, reused
during the entry hour; they cannot prove liquidity replenishment, market impact,
queue position, intrahour drawdown or realized fills. Neither the historical
accounts nor the recorded prefix are fresh holdout evidence. Even a screen pass
would require separately fixed unused/prospective evidence and production parity.

Forecasting, training, stop thresholds, sizing, cash reserve and cooldown were
held fixed. This study changed no installed trading binary, live process, account
state, or ongoing paper campaign. Evidence root: `{OUT}`.
'''
    with document.open('x') as stream:
        stream.write(report)
    argv = ['/home/lee/.pyenv/shims/ruff', 'check', '--select', 'E9,F63,F7,F82', str(HERE)]
    lint = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
    save(OUT / 'final_lint.json', dict(argv=argv, returncode=lint.returncode, stdout=lint.stdout, stderr=lint.stderr))
    assert lint.returncode == 0
    artifacts = {p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    artifacts.update(p for p in HERE.iterdir() if p.is_file())
    artifacts.update((document, REPO / 'docs/2026-09-26-exit-order-reserve-prereg.md'))
    artifacts.update(p for p in BASE.glob('poloniex_exit_reserve_v1.*.log') if p.name != 'poloniex_exit_reserve_v1.finish.log')
    save(OUT / 'completion.json', dict(verified=True, at_ns=time.time_ns(), native_tests=sources['native_tests'],
        native_money_and_race_cases=256, historical_accounts_per_arm=45, historical_accounts_total=135,
        observed_native_cycles=28980, historical_screen_passes=assessment['historical_screen_passes'],
        historical_treatment_never_activated=True, historical_maximum_daily_orders=8,
        original_failed_audit_preserved=True,
        groups_passing=assessment['groups_passing'], groups_total=9,
        gates_passed=assessment['gates_passed'], gates_total=assessment['gates_total'], paired_summary=summary,
        live_changed=False, ongoing_studies_changed=False, deployment_qualified=False,
        upstream_hash_checks=checked, artifact_hashes={str(p): sha(p) for p in sorted(artifacts)}))
    print(json.dumps(dict(verified=True, decision=decision, groups_passing=assessment['groups_passing'],
                         paired_summary=summary, document=str(document)), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
