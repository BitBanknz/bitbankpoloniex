"""Seal repair evidence; the bounded paper observation remains ongoing."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = Path('/vfast/data/trading_research_20260924')
OUT = BASE / 'poloniex_execution_wait_recovery_20260927_v1'
REPORT = REPO / 'docs/2026-09-27-execution-wait-recovery-results.md'
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p:json.loads(Path(p).read_bytes())


def main():
    assert not (OUT / 'completion.json').exists()
    proof = read(OUT / 'prefix_verified.json')
    suffix = read(OUT / 'recovery_verified.json')
    launch = read(OUT / 'remote_launch.json')
    observation = read(OUT / 'observation/mirror/status.json')
    assert launch['original_directories_unchanged'] is True and launch['source_restarted'] is False
    assert launch['external_orders'] is False and launch['credentials_transferred'] is False
    assert suffix['external_orders'] is False
    tests = (OUT / 'tests.log').read_text()
    assert 'Ran 12 tests' in tests and tests.rstrip().endswith('OK')
    for label in ('guarded', 'unguarded'):
        assert proof['variants'][label]['verified'] and proof['variants'][label]['original_batches'] == 173
        assert proof['variants'][label]['original_transitions'] == 1032
        assert proof['variants'][label]['total_transitions'] == 1044
        assert proof['variants'][label]['gap_indices'] == [97]
        assert suffix['variants'][label]['verified']
        assert sha(OUT / (label + '_prefix_audit.json.gz')) == proof['variants'][label]['audit_sha256']
        assert sha(OUT / (label + '_recovered_suffix.json.gz')) == suffix['variants'][label]['suffix_proof_sha256']
    for name in ('shadow.py', 'native.py', 'receipt_rules.py', 'outcomes.py', 'prefix.py'):
        path = HERE / 'worker' / name
        assert sha(path) == proof['source_hashes'][str(path)]
        assert sha(OUT / 'package/worker' / name) == sha(path)
    n = sum(v['suffix_transitions'] for v in suffix['variants'].values())
    latest = min(v['through_index'] for v in suffix['variants'].values())
    observed = datetime.fromtimestamp(observation['at_ns'] / 1e9, timezone.utc).isoformat()
    lines = ['# Poloniex paper execution-wait recovery', '',
        'The paper completion checker now accepts a valid forecast that has been published but is not yet executable. Both repaired consumers were launched in new directories using the unchanged native trading binaries and all original account settings. The recorder was not restarted. No real-money order, service or setting changed.', '',
        'The original consumers stopped at source index 173, logical 2026-09-27 00:05:24.993586862 UTC. A valid forecast issued at midnight was executable at 01:00. The native engines correctly returned a completed waiting cycle with no fills, but the old checker asserted that every successful cycle must already have an executable signal. The original failed directories and receipts remain preserved.', '',
        'The added waiting outcome validates the published forecast, issue/execution clocks, successful native completion, state flags and intact fill prefix. New entries remain forbidden while waiting; protective sales remain allowed. Malformed forecasts, unknown errors, incomplete cycles and inconsistent states still fail. See the [recovery protocol](2026-09-27-execution-wait-recovery-protocol.md).', '',
        'All 12 tests passed: the original five outcome tests, three waiting-state tests using both native variants, and four prefix-integrity tests. Native boundary checks cover one nanosecond before execution, execution itself, one nanosecond after it, and forecast expiry. Protective selling while waiting is exercised, and forged buys are rejected.', '',
        'Before launch, 1,412 captured files were authenticated. All 173 originally committed batches in each consumer were replayed from initial state; every decoded input and output matched the authenticated originals exactly. This includes the unusable metadata gap at index 97. Across the two variants, 2,064 original native transitions and 24 additional transitions across indices 173–174 were checked with independent Decimal accounting. The accounting checker verifies execution/account arithmetic; it is not an independent implementation of the trading planner.', '',
        f'After launch, both recovered receipt chains were authenticated through source index {latest}. Their compressed prefix inputs and outputs also matched the original bytes. The complete recovered suffix from index 172 through {latest} was downloaded and independently rerun: {n} native and Decimal transitions matched the remote outputs exactly. The snapshot was observed at {observed}.', '',
        '| Variant | Paper PID | Verified through | Suffix transitions | Suffix fills | Outcomes |',
        '|---|---:|---:|---:|---:|---|']
    by_root = {r['root']:r for r in launch['launches']}
    for label in ('unguarded', 'guarded'):
        v = suffix['variants'][label]
        pid = by_root[launch['protocols'][label]['root']]['pid']
        lines.append(f"| {label} | {pid} | {v['through_index']} | {v['suffix_transitions']} | {v['fills']} | {', '.join(v['outcomes'])} |")
    lines += ['', 'Recovery reconstructs the original cash, holdings, high-water marks and counters through verified replay. It does not reset the accounts at the interruption. The original consumers remain failed; the new streams are explicitly recovered observed-data replays, whose computations may occur after publication. They do not claim contemporaneous order decisions or actual exchange fills.', '',
        'The source and recovered consumers retain the original October 3, 2026, 21:12:15 UTC endpoint. Their full-period comparison is still incomplete. This repair improves paper validation reliability and establishes no profitability improvement or trading-algorithm qualification.', '',
        'The first full-prefix download hit its 60-second transfer limit; the partial archive and the consequent missing-input audit failure were retained. A separately named read-only transfer completed and was fully authenticated before replay or launch.', '',
        f'Evidence: `{OUT}`. Initial failure capture: `{BASE / "poloniex_consumer_failure_20260927_v1"}`.', '']
    with REPORT.open('x') as stream:
        stream.write('\n'.join(lines))
    dependencies = {p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    dependencies.update(p for p in (BASE / 'poloniex_consumer_failure_20260927_v1').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    dependencies.update(p for p in (REPO / 'research/futurecompare20260926').glob('*.py'))
    dependencies.update([REPORT, REPO / 'docs/2026-09-27-execution-wait-recovery-protocol.md',
        REPO / 'research/quoteaware20260924/native.py', REPO / 'research/quoteaware20260924/replay_v2.py',
        REPO / 'research/futureworker20260926/test_outcomes.py',
        BASE / 'poloniex_prospective_replacement_20260927_v2/completion.json',
        BASE / 'poloniex_quote_aware_v1/driver/candidate/observed_cycle.test',
        BASE / 'poloniex_stop_topup_guard_v1/observed/engine.test',
        BASE / 'poloniex_quote_aware_v1/source/internal/bot/engine.go',
        BASE / 'poloniex_quote_aware_v1/source/internal/bot/signals.go'])
    assert all(p.is_file() for p in dependencies)
    result = dict(verified=True, completed_utc=datetime.now(timezone.utc).isoformat(), tests=12,
        original_batches_each=173, original_native_decimal_transitions=2064, local_total_native_decimal_transitions=2088,
        postlaunch_suffix_transitions=n, verified_through_index=latest,
        live_changed=False, paper_recovery_launched=True, original_consumers_failed=True,
        original_directories_unchanged=True, source_restarted=False, full_period_comparison_complete=False,
        hashes={str(p):sha(p) for p in sorted(dependencies)},
        artifacts={str(p):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts})
    with (OUT / 'completion.json').open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write('\n')
    print('PAPER_RECOVERY_SEALED', sha(OUT / 'completion.json'), len(result['hashes']), len(result['artifacts']), flush=True)


if __name__ == '__main__':
    main()
