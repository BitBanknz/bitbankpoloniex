"""Descriptive cost/exposure decomposition; introduces no new selection rule."""
from collections import defaultdict
from decimal import Decimal as D, getcontext
import gzip
import json
from pathlib import Path

from build import ARMS, BASE, OUT, read, save, sha

getcontext().prec = 80


def main():
    folder = OUT / 'observed_attribution'
    folder.mkdir(exist_ok=False)
    observed = OUT / 'observed_accounts'
    proof = read(observed / 'verification.json')
    assert proof['verified'] and proof['native_cycles'] == 28980
    for name, digest in proof['output_hashes'].items():
        assert sha(observed / name) == digest
    states = read(observed / 'final_states.json')
    stats = read(observed / 'summary.json')
    source = BASE / 'poloniex_future_prefix_3297_v1/mirror'
    name = 'guarded/batch_03297.input.json.gz'
    manifest = read(source / 'manifest.json')
    capture = read(source.parent / 'capture.verified.json')
    assert sha(source / 'manifest.json') == capture['manifest_sha256']
    assert sha(source / name) == manifest[name]['sha256']
    packet = json.loads(gzip.decompress((source / name).read_bytes()))['packet']
    results = {}
    for arm in ARMS:
        results[arm] = {}
        for aid, state in states[arm].items():
            days = defaultdict(lambda: dict(buys=0, turnover=D(0), fees=D(0)))
            symbols = defaultdict(lambda: dict(quantity=D(0), paid=D(0), fees=D(0)))
            for fill in state['Fills']:
                assert fill['Order']['side'] == 'BUY'
                amount, cost = D(fill['Amount']), D(fill['Fee'])
                day = days[fill['At'][:10]]
                day['buys'] += 1
                day['turnover'] += amount
                day['fees'] += cost
                position = symbols[fill['Order']['symbol']]
                position['quantity'] += D(fill['Quantity'])
                position['paid'] += amount
                position['fees'] += cost
            assert set(symbols) == set(state['Holdings'])
            for symbol, row in symbols.items():
                response = packet['Responses']['/markets/' + symbol + '/orderBook']
                assert response['Status'] == 200
                bid = D(response['Body']['bids'][0])
                assert row['quantity'] == D(state['Holdings'][symbol]['Quantity'])
                row['final_bid'] = bid
                row['final_mark'] = row['quantity'] * bid
                row['net_pnl'] = row['final_mark'] - row['paid'] - row['fees']
            total = dict(turnover=sum(row['paid'] for row in symbols.values()),
                         fees=sum(row['fees'] for row in symbols.values()),
                         final_mark=sum(row['final_mark'] for row in symbols.values()),
                         net_pnl=sum(row['net_pnl'] for row in symbols.values()))
            assert D(state['Cash']) == 495 - total['turnover'] - total['fees']
            assert total['fees'] == D(stats[arm][aid]['fees'])
            assert total['turnover'] == D(stats[arm][aid]['turnover'])
            assert D(state['Cash']) + total['final_mark'] == D(stats[arm][aid]['last_equity'])
            assert 495 + total['net_pnl'] == D(stats[arm][aid]['last_equity'])
            stringify = lambda row: {key: str(value) if isinstance(value, D) else value for key, value in row.items()}
            results[arm][aid] = dict(days={day: stringify(row) for day, row in days.items()},
                                     symbols={symbol: stringify(row) for symbol, row in symbols.items()},
                                     totals=stringify(total))
    for aid in states['baseline']:
        baseline = states['baseline'][aid]['Fills']
        candidate = states['reserve3'][aid]['Fills']
        assert baseline[:9] == candidate[:9]
        assert len(baseline) == 12 and len(candidate) == 10
        assert all(fill['At'].startswith('2026-09-25') for fill in baseline)
        assert candidate[9]['At'].startswith('2026-09-26')
        assert all(fill['Order']['symbol'] == 'PEPE_USDT' for fill in baseline[9:] + candidate[9:])
        assert results['reserve3'][aid] == results['cap9'][aid]
    save(folder / 'attribution.json', results)
    inputs = [Path(__file__), observed / 'verification.json', observed / 'final_states.json',
              observed / 'summary.json', source / 'manifest.json', source / name, folder / 'attribution.json']
    save(folder / 'verification.json', dict(verified=True, accounts=9,
        first_nine_buys_identical=True, all_different_fills_are_pepe_topups=True,
        baseline_extra_topups=3, candidate_next_day_topups=1,
        accounting_identities_exact=True, retrospective_description_only=True,
        hashes={str(path): sha(path) for path in inputs}))
    print('EXIT_RESERVE_ATTRIBUTION_VERIFIED', 9, flush=True)


if __name__ == '__main__':
    main()
