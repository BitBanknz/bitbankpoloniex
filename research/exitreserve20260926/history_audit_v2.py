"""Complete the audit without assuming historical paths crossed nine orders.

The original negative test expected a violation absent from these histories.
Preserve that failure, reconcile every unchanged ledger, and use explicit invalid
budgets to exercise both reference rejections. Native boundary-nine cases remain
required in the separately verified full-cycle regression/assessment evidence.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import time

from account_reference import Check, verify
from build import ARMS, BASE, HERE, OUT, PARENT, REPO, read, save, sha


def main():
    root = OUT / 'historical_accounts'
    folder = OUT / 'historical_audit_v2'
    folder.mkdir(exist_ok=False)
    assert not (root / 'verification.json').exists()
    failure_log = BASE / 'poloniex_exit_reserve_v1.history.log'
    failure = failure_log.read_text()
    assert "assert len(accounts)==45 and set(rejected)==" in failure and failure.endswith('AssertionError\n')
    registration = read(root / 'registration.json')
    for path, digest in registration['hashes'].items():
        assert sha(path) == digest
    cases = read(BASE / 'poloniex_stop_topup_guard_v1/cases.json')
    assert len(cases) == 9
    native_files = sorted(p for p in root.rglob('*') if p.is_file())
    inputs = [Path(__file__), HERE / 'history.py', HERE / 'account_reference.py', failure_log,
              OUT / 'regressions_v3/verification.json', *native_files]
    hashes = {str(p): sha(p) for p in inputs}
    save(folder / 'registration.json', dict(at_ns=time.time_ns(), hashes=hashes,
        original_failure_preserved=True, native_code_changed=False, native_replay_outputs_changed=False,
        financial_reference_changed=False, selection_gates_changed=False,
        correction='Historical paths never crossed nine orders; use deliberately impossible budgets for negative reference checks. Boundary-nine mutations remain in full-cycle assessment.'))
    fixture = read(REPO / 'data/frontier_20260912/ledger/fixture.json')
    markets = read(REPO / 'data/frontier_20260912/ledger/markets.json')
    check = Check()
    accounts = []
    rejected = {}
    daily_maxima = {arm: [] for arm in ARMS}
    parity_count = 0
    for case in cases:
        reports = {}
        for arm in ARMS:
            location = root / arm / case['id']
            assert read(location / 'exit.json')['returncode'] == 0
            command = read(location / 'command.json')
            assert command['arm'] == arm and command['case'] == case
            assert command['env']['RESEARCH_ARM'] == arm
            assert command['argv'][0] == str(OUT / 'historical/engine.test')
            reports[arm] = [json.loads(line) for line in (location / 'results.jsonl').read_text().splitlines()]
            assert len(reports[arm]) == {0: 1, 28: 9, 56: 5}[case['days']]
            if arm == 'baseline':
                assert (location / 'results.jsonl').read_bytes() == (PARENT / 'parity' / case['id'] / 'results.jsonl').read_bytes()
        for triple in zip(*(reports[arm] for arm in ARMS), strict=True):
            assert len({(row['Start'], row['End']) for row in triple}) == 1
            result = dict(case=case['id'], start=triple[0]['Start'], end=triple[0]['End'], arms={}, bindings={})
            states = {}
            for arm, row in zip(ARMS, triple, strict=True):
                path = root / arm / case['id'] / row['Ledger']
                state = read(path)
                states[arm] = state
                maximum, reserve = ARMS[arm]
                result['arms'][arm] = verify(state, row, case, fixture, markets, check,
                    require_stop_guard=True, max_orders_day=maximum, exit_order_reserve=reserve)
                result['bindings'][arm] = dict(path=str(path), sha256=sha(path))
                by_day = Counter(fill['At'][:10] for fill in state['Fills'] or [])
                daily_maxima[arm].append(max(by_day.values(), default=0))
                if arm == 'baseline':
                    assert path.read_bytes() == (PARENT / 'parity' / case['id'] / row['Ledger']).read_bytes()
                    parity_count += 1
                if state['Fills'] and not rejected:
                    for name, limit, held in (('total_order_budget', 0, 0), ('buy_order_budget', 12, 12)):
                        try:
                            verify(state, row, case, fixture, markets, Check(), require_stop_guard=True,
                                   max_orders_day=limit, exit_order_reserve=held)
                        except AssertionError as error:
                            assert error.args and isinstance(error.args[0], tuple) and error.args[0][0] == name, error
                            rejected[name] = dict(case=case['id'], arm=arm, start=row['Start'],
                                                  max_orders_day=limit, exit_order_reserve=held, error=error.args[0])
                        else:
                            raise AssertionError('invalid reference budget accepted')
                    changed = deepcopy(state)
                    changed['Fills'][0]['Order']['clientOrderId'] = 'bbp-corrupted'
                    try:
                        verify(changed, row, case, fixture, markets, Check(), require_stop_guard=True,
                               max_orders_day=maximum, exit_order_reserve=reserve)
                    except AssertionError:
                        rejected['corrupted_id'] = dict(case=case['id'], arm=arm, start=row['Start'])
                    else:
                        raise AssertionError('corrupted decision ID accepted')
            assert states['baseline'] == states['cap9'] == states['reserve3']
            for arm in ('cap9', 'reserve3'):
                assert result['bindings'][arm]['sha256'] == result['bindings']['baseline']['sha256']
            accounts.append(result)
    assert len(accounts) == parity_count == 45
    assert set(rejected) == {'total_order_budget', 'buy_order_budget', 'corrupted_id'}
    assert all(max(values) == 8 for values in daily_maxima.values())
    assert all(sha(path) == digest for path, digest in hashes.items())
    save(folder / 'accounts.json', accounts)
    save(folder / 'verification.json', dict(verified=True, at_ns=time.time_ns(), accounts_per_arm=45,
        total_accounts=135, baseline_reports_and_ledgers_byte_exact=True,
        all_three_arms_ledger_byte_exact=True, maximum_daily_orders=8,
        daily_order_maxima_histograms={arm: dict(Counter(values)) for arm, values in daily_maxima.items()},
        historical_treatment_never_activated=True, exact_comparisons=check.count,
        maximum_metric_error=str(check.maximum), budget_and_id_rejections=rejected,
        accounts_sha256=sha(folder / 'accounts.json'), registration_sha256=sha(folder / 'registration.json'),
        historical_reuse=True, full_policy_oracle=False, native_replays_repeated=False,
        original_failed_audit_preserved=True, live_changed=False, deployment_qualified=False))
    print('EXIT_RESERVE_HISTORY_AUDIT_V2_VERIFIED', 135, check.count, flush=True)


if __name__ == '__main__':
    main()
