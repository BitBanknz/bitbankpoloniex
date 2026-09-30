"""Seal the matched depth diagnostic without choosing a strategy from its result."""
from decimal import Decimal as D
from pathlib import Path
import subprocess
import time

from common import ARMS, BASE, HERE, OUT, PARENT, REPO, read, save, sha


def main():
    proof = read(OUT / 'audit/verification.json')
    preflight = read(OUT / 'preflight.json')
    assert proof['verified'] and proof['reconciled_cycles'] == 57960 and proof['accounts'] == 18
    assert preflight['verified'] and preflight['native_accounting_cases'] == 512
    checked = {}

    def check(path, digest):
        assert sha(path) == digest, str(path)
        checked[str(path)] = digest

    check(OUT / 'registration.json', preflight['registration_sha256'])
    check(OUT / 'regressions.jsonl.gz', preflight['regressions_sha256'])
    for folder in (OUT, OUT / 'audit'):
        for path, digest in read(folder / 'registration.json')['hashes'].items():
            check(path, digest)
    for path, digest in proof['hashes'].items():
        check(path, digest)
    for path, digest in proof['output_hashes'].items():
        check(path, digest)
    for fee in (30, 40, 60):
        folder = OUT / ('fee' + str(fee))
        result = read(folder / 'verification.json')
        assert result['verified'] and result['native_cycles'] == 9660
        for path, digest in result['input_hashes'].items():
            check(path, digest)
        for name, digest in result['output_hashes'].items():
            check(folder / name, digest)
    chart = read(OUT / 'chart.json')
    check(OUT / 'audit/paired_equity.jsonl.gz', chart['input_sha256'])
    check(OUT / 'depth_equity.png', chart['output_sha256'])
    coverage = read(OUT / 'audit/coverage.json')
    quotes = read(OUT / 'audit/quote_summary.json')
    quote_rows = read(OUT / 'audit/quotes.json')
    feasible_limited = {model: sum(row[model]['quote_feasible'] and row[model]['depth_limited'] is True for row in quote_rows)
                        for model in ('observed', 'ample')}
    comparison = read(OUT / 'audit/comparisons.json')
    indexed = {(row['model'], row['fee_bps'], row['arm']): row for row in coverage}
    table = []
    for fee in (30, 40, 60):
        for arm in ARMS:
            original, ample = (indexed[model, fee, arm] for model in ('observed', 'ample'))
            metrics = [f"{D(row['metrics']['return_pct']):.6f}" for row in (original, ample)]
            drawdowns = [f"{D(row['metrics']['dd']):.6f}" for row in (original, ample)]
            fills = [row['metrics']['buys'] + row['metrics']['sells'] for row in (original, ample)]
            maxima = [row['orders']['maximum_daily_orders'] for row in (original, ample)]
            table.append(f"| {fee} | {arm} | {' / '.join(metrics)} | {' / '.join(drawdowns)} | {fills[0]} / {fills[1]} | {maxima[0]} / {maxima[1]} |")
    equality = proof['policy_financial_path_equality']
    coverage_table = [f"| {row['model']} | {row['fee_bps']} | {row['left_arm']} vs {row['right_arm']} | {row['identical_cycles']} / {row['total_cycles']} | {'Yes' if row['policy_difference_observed'] else 'No'} |" for row in equality]
    observed_max = max(row['orders']['maximum_daily_orders'] for row in coverage if row['model'] == 'observed')
    ample_max = max(row['orders']['maximum_daily_orders'] for row in coverage if row['model'] == 'ample')
    affected = sum(D(row['return_difference_pp']) != 0 for row in comparison)
    effects = dict(higher_return=sum(D(row['return_difference_pp']) > 0 for row in comparison),
                   lower_return=sum(D(row['return_difference_pp']) < 0 for row in comparison),
                   higher_drawdown=sum(D(row['drawdown_difference_pp']) > 0 for row in comparison),
                   lower_drawdown=sum(D(row['drawdown_difference_pp']) < 0 for row in comparison))
    ample_nonactivation = [row for row in equality if row['model'] == 'ample' and not row['policy_difference_observed']]
    doc = f'''# Depth assumptions change the account simulation's coverage

This fixed diagnostic compared the same recorded prices, spreads, market
contracts, forecasts and timestamps under observed depth and deliberately
abundant depth. Changing only displayed quantities changed final return in
{affected}/9 matched accounts. The largest daily filled-order count was
{observed_max} with observed depth and {ample_max} with abundant depth.
{len(ample_nonactivation)}/9 policy-pair/fee comparisons under abundant depth
had identical financial paths for the entire prefix. These are simulator
sensitivity results, not evidence of better real trading performance.

The original hourly historical replay stayed at or below eight orders per day,
so it could not exercise a buy boundary at nine. The observed-book path used
twelve buys in one day. This ablation holds prices and decision clocks fixed to
isolate one source of that coverage difference. It does not attribute every
historical/public discrepancy to depth: the two original datasets also differ
in dates, sampling frequency, forecasts and execution observations.

## Fixed comparison

The [protocol](2026-09-26-depth-ablation-protocol.md) was frozen before the new
native replay. The existing compiled guarded engine and its three private order
budget policies were reused: baseline 12 total, cap9 total, and reserve3 with 12
total and buys blocked once nine daily orders have succeeded. Fees remain
30/40/60 bps per side. Every account starts with 495 USDT and retains the 49-USDT
order cap, sizing, stop, cooldown and cash-reserve rules.

The diagnostic quantity floor is ceil(49000 / the smallest price in the current
book), in base units. Every positive quantity below that floor is raised to it;
zeros stay zero. Invalid, stale and unavailable inputs are not repaired. All
nonquantity values remain unchanged. This is an intentionally abundant-depth
counterfactual, not a proposed execution model or a claim of available liquidity.
It uses only the current received packet and has no future-price input.

All values below are **observed / abundant depth**. Drawdown is calculated from
the initially funded equity and retained minute observations. Filled orders
are counted separately from their notional size; unsuccessful attempts are not
inferred from fills.

| Fee bps/side | Policy | Return % | Sampled drawdown % | Filled orders | Largest daily order count |
| --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(table)}

Abundant depth raised return in {effects['higher_return']} comparisons and lowered
it in {effects['lower_return']}; it increased sampled drawdown in
{effects['higher_drawdown']} and reduced it in {effects['lower_drawdown']}.
Thus the model change is not uniformly favorable or conservative. The main
coverage result is that every abundant-depth account completed its buying in
six orders, making the nine-order buy boundary irrelevant on this prefix.

![Account equity by depth assumption]({OUT/'depth_equity.png'})

Curves are merged in the chart only when their complete plotted equity sequences
are exactly equal within the same depth model. The
[full paired return/drawdown and first-fill differences]({OUT/'audit/comparisons.json'})
retain all nine comparisons, including negative differences. The
[coverage matrix]({OUT/'audit/coverage.json'}) includes every observed UTC day,
including days with zero orders, and counts days reaching nine, twelve, the
policy's buy boundary and its total allowance. It does not claim that reaching
a boundary proves an additional order was attempted.

## Quote feasibility and policy activation

Across {quotes['observed']['target_observations']} forecast-target observations,
the flat hypothetical 49-USDT order was constrained by displayed depth in
{quotes['observed']['depth_limited']} observed-book cases versus
{quotes['ample']['depth_limited']} abundant-book cases. Quote feasibility was
{quotes['observed']['quote_feasible']} versus {quotes['ample']['quote_feasible']}.
The observed hypothetical notional range was
{D(quotes['observed']['notional_min']):.6f}–{D(quotes['observed']['notional_max']):.6f} USDT;
the abundant-depth range was
{D(quotes['ample']['notional_min']):.6f}–{D(quotes['ample']['notional_max']):.6f} USDT.
Depth-limited counts and notional ranges include quotes rejected by other quote
gates. Among quote-feasible observations specifically, depth constrained
{feasible_limited['observed']} observed cases and {feasible_limited['ample']} abundant cases.
These quote checks exclude account sizing, holdings, cooldown, reserve and risk
gates. Repeated minutes and fee arms are not independent trading opportunities.
[Every quote comparison]({OUT/'audit/quotes.json'}) is retained.

Identical financial paths below mean no observed account effect for that pair
under that depth model. In particular, cap9 versus reserve3 isolates extra sell
capacity after the same buy restriction; equality supplies no reserved-exit
performance evidence.

| Depth model | Fee bps/side | Policy pair | Identical financial cycles | Any account effect? |
| --- | ---: | --- | ---: | --- |
{chr(10).join(coverage_table)}

The reusable coverage output makes this nonactivation explicit instead of
treating an unchanged return as an improvement. It is descriptive evidence for
future validation design, not a replacement for out-of-sample strategy gates.

## Verification

Seven adapter tests passed, including 200 seeded price-scale examples, input
immutability, preservation of zero sizes, price/status/clock projection, malformed
data and exact native freshness boundaries. All 256 existing complete-cycle
fixtures matched their original full outputs and request paths in identity
mode. Another 256 abundant-depth complete cycles passed independent money,
nanosecond clock and daily-budget checks, and all 256 were repeated under the
existing race binary with identical full outputs and paths.

No native engine source or binary was changed. The prior 104 native tests,
104 race tests and successful vet run remain authenticated by the sealed parent
study. All nine new account paths cover the full 3220-capture prefix: 28,980 native
cycles. The already-reconciled observed accounts were reused as fixed controls.
A further independent audit reconstructed cash, quantities, fill costs, fees,
source-price marks and equity for all 57,960 observed/counterfactual cycles.
It matched every reported return, drawdown, fill, fee and final position.

The audit checked the quantity floor using exact integer ratios, independently
of the adapter's Decimal division. There were {proof['changed_books']:,} changed
book responses and {proof['changed_levels']:,} raised levels across the fixed
source prefix. Every capture retained the original price and clock projection;
all three fee processes produced identical adapter records. Five coverage tests
check zero-order days, successful-sale counting, day resets, invalid budgets and
same-timestamp quantity differences.
Four additional accounting tests verify hand-calculated buys and partial sales,
rejection of fee/quantity/source-mark mutations, unavailable valuation, and dust
removal without creating cash.

## Scope and decision

The result supports keeping recorded book depth and order-budget coverage in
future account comparisons. Abundant-depth results must not replace observed
results or be used to select a winning strategy. This experiment did not train
a model, tune a strategy, qualify deployment, alter a live account, or change an
ongoing paper campaign.

The source prefix, September 24 03:14 through September 26 08:53 UTC, was already
observed. Its snapshots are sequential, and both models still use hypothetical
IOC fills. Neither displayed depth nor this counterfactual proves matching,
queue priority, replenishment, market impact or intraminute risk. Longer unused
or prospective evidence and production parity remain required for advancement.

Evidence root: `{OUT}`.
'''
    document = REPO / 'docs/2026-09-26-depth-ablation-results.md'
    with document.open('x') as stream:
        stream.write(doc)
    argv = ['/home/lee/.pyenv/shims/ruff', 'check', '--select', 'E9,F63,F7,F82', str(HERE)]
    lint = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
    save(OUT / 'final_lint.json', dict(argv=argv, returncode=lint.returncode, stdout=lint.stdout, stderr=lint.stderr))
    assert lint.returncode == 0
    artifacts = {path for path in OUT.rglob('*') if path.is_file() and '__pycache__' not in path.parts}
    artifacts.update(path for path in HERE.iterdir() if path.is_file())
    artifacts.update((document, REPO / 'docs/2026-09-26-depth-ablation-protocol.md'))
    artifacts.update(path for path in BASE.glob('poloniex_depth_ablation_v1.*.log') if path.name != 'poloniex_depth_ablation_v1.finish.log')
    save(OUT / 'completion.json', dict(verified=True, at_ns=time.time_ns(), diagnostic_only=True,
        observed_accounts_reused=9, new_accounts=9, new_native_cycles=28980, reconciled_cycles=57960,
        native_source_changed=False, live_changed=False, ongoing_studies_changed=False,
        deployment_qualified=False, affected_return_accounts=affected,
        observed_maximum_daily_orders=observed_max, ample_maximum_daily_orders=ample_max,
        quote_summary=quotes, policy_financial_path_equality=equality,
        quote_feasible_depth_limited=feasible_limited, metric_effect_counts=effects,
        upstream_hash_checks=checked, artifact_hashes={str(path): sha(path) for path in sorted(artifacts)}))
    print('DEPTH_ABLATION_COMPLETE', affected, observed_max, ample_max, str(document), flush=True)


if __name__ == '__main__':
    main()
