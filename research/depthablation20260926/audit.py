"""Independent account sums and integer quantity-floor audit for every capture."""
from collections import Counter, defaultdict
from decimal import Decimal as D, ROUND_FLOOR, ROUND_HALF_UP
import gzip
import json
from pathlib import Path
import subprocess
import sys

from bookmodel import projection, transform
from common import ARMS, HERE, OUT, PARENT, SOURCE, read, save, sha
from coverage import day, first_fill_difference, order_coverage
import receipt_rules as rules


def initialize():
    return dict(cash=D(495), positions={}, fills=[], cycles=0, peak=D(495), dd=D(0),
                fees=D(0), turnover=D(0), buys=0, sells=0, unmarked=0, last_equity=None, days=set())


def reconcile(stat, row, original, fee):
    stat['cycles'] += 1
    stat['days'].add(day(row['now_ns']))
    positions = stat['positions']
    for dust in row['dust']:
        symbol = dust['symbol']
        assert positions.pop(symbol) == D(dust['quantity'])
    fees = D(0)
    turnover = D(0)
    for fill in row['new_fills']:
        order = fill['Order']
        symbol, side = order['symbol'], order['side']
        quantity, price = D(fill['Quantity']), D(order['price'])
        assert quantity > 0 and price > 0 and D(order['quantity']) == quantity
        amount, cost = quantity * price, quantity * price * D(fee) / 10000
        assert amount == D(fill['Amount']) and cost == D(fill['Fee'])
        if side == 'BUY':
            stat['cash'] -= amount + cost
            positions[symbol] = positions.get(symbol, D(0)) + quantity
            stat['buys'] += 1
        else:
            assert side == 'SELL' and positions[symbol] >= quantity
            stat['cash'] += amount - cost
            positions[symbol] -= quantity
            if positions[symbol] == 0:
                del positions[symbol]
            stat['sells'] += 1
        fees += cost
        turnover += amount
        stat['fills'].append(fill)
    assert stat['cash'] == D(row['cash']) and fees == D(row['fees']) and turnover == D(row['turnover'])
    stat['fees'] += fees
    stat['turnover'] += turnover
    assert not set(row['marks']) & set(row['unpriced'])
    assert set(row['marks']) | set(row['unpriced']) == set(positions)
    for symbol, mark in row['marks'].items():
        book = original['/markets/' + symbol + '/orderBook']
        assert book['Status'] == 200 and D(mark) == D(book['Body']['bids'][0])
        assert rules.fresh(book['Body']['ts'], row['now_ns'], 30)
    if row['unpriced']:
        assert row['equity'] is None
        stat['unmarked'] += 1
        stat['last_equity'] = None
    else:
        value = stat['cash'] + sum((q * D(row['marks'][symbol]) for symbol, q in positions.items()), D(0))
        assert value == D(row['equity'])
        stat['peak'] = max(stat['peak'], value)
        stat['dd'] = max(stat['dd'], (stat['peak'] - value) / stat['peak'] * 100)
        stat['last_equity'] = value


def quote_comparison(original, abundant, now):
    prediction = original['/prediction']
    scores = rules.ranks_at(prediction['Body'], now) if prediction['Status'] == 200 else None
    if not scores:
        return []
    markets = {row['symbol']: row for row in original['/markets']['Body']}
    tickers = {row['symbol']: row for row in original['/markets/ticker24h']['Body']}
    eligible = [symbol for symbol in scores if symbol in markets and symbol in tickers and
                markets[symbol]['state'] == 'NORMAL' and markets[symbol]['quoteCurrencyName'] == 'USDT' and
                D(tickers[symbol]['amount']) >= 100000 and rules.fresh(tickers[symbol]['ts'], now, 300)]
    targets = sorted(eligible, key=lambda symbol: (-scores[symbol], symbol))[:3]
    rows = []
    for symbol in targets:
        result = dict(symbol=symbol, account_gates_checked=False)
        for name, responses in (('observed', original), ('ample', abundant)):
            response = responses['/markets/' + symbol + '/orderBook']
            if response['Status'] != 200:
                result[name] = dict(quote_feasible=False, reasons=['unavailable'], depth_limited=None)
                continue
            try:
                feasibility = rules.feasibility(markets[symbol], tickers[symbol], response['Body'], now)
            except (AssertionError, KeyError, ValueError):
                result[name] = dict(quote_feasible=False, reasons=['invalid'], depth_limited=None)
                continue
            scale = markets[symbol]['symbolTradeLimit']['quantityScale']
            full_quantity = (D(49) / D(feasibility['hypothetical_buy_price'])).quantize(D('1e-16'), rounding=ROUND_HALF_UP).quantize(D(1).scaleb(-scale), rounding=ROUND_FLOOR)
            feasibility['depth_limited'] = D(feasibility['hypothetical_buy_quantity']) < full_quantity
            result[name] = feasibility
        rows.append(result)
    return rows


def main():
    folder = OUT / 'audit'
    folder.mkdir(exist_ok=False)
    inputs = [Path(__file__), HERE / 'coverage.py', HERE / 'test_coverage.py', HERE / 'test_audit.py', OUT / 'preflight.json',
              PARENT / 'observed_accounts/verification.json', SOURCE / 'mirror/manifest.json']
    for fee in (30, 40, 60):
        root = OUT / ('fee' + str(fee))
        proof = read(root / 'verification.json')
        assert proof['verified'] and proof['native_cycles'] == 9660
        inputs.append(root / 'verification.json')
        for name, digest in proof['output_hashes'].items():
            assert sha(root / name) == digest
            inputs.append(root / name)
    observed = PARENT / 'observed_accounts'
    observed_proof = read(observed / 'verification.json')
    for name, digest in observed_proof['output_hashes'].items():
        assert sha(observed / name) == digest
        inputs.append(observed / name)
    hashes = {str(path): sha(path) for path in inputs}
    save(folder / 'registration.json', dict(hashes=hashes, descriptive_only=True))
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'test_coverage', 'test_audit'], cwd=HERE, capture_output=True, text=True)
    save(folder / 'tests.json', dict(returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr))
    assert tests.returncode == 0
    assert len({sha(OUT / ('fee' + str(fee)) / 'adapters.jsonl') for fee in (30, 40, 60)}) == 1
    manifest = read(SOURCE / 'mirror/manifest.json')
    observed_stream = (observed / 'paths.jsonl').open()
    ample_streams = {fee: (OUT / ('fee' + str(fee)) / 'paths.jsonl').open() for fee in (30, 40, 60)}
    adaptations = (OUT / 'fee30/adapters.jsonl').open()
    stats = {(model, fee, arm): initialize() for model in ('observed', 'ample') for fee in (30, 40, 60) for arm in ARMS}
    identical = Counter()
    quotes = []
    changed_books = changed_levels = 0
    try:
        with gzip.open(folder / 'paired_equity.jsonl.gz', 'wt') as paired:
            for index in range(78, 3298):
                name = f'guarded/batch_{index:05d}.input.json.gz'
                path = SOURCE / 'mirror' / name
                assert sha(path) == manifest[name]['sha256']
                packet = json.loads(gzip.decompress(path.read_bytes()))['packet']
                original, now = packet['Responses'], packet['NowNS']
                abundant, changes = transform(original, now)
                adapted = json.loads(next(adaptations))
                assert adapted == dict(index=index, now_ns=now, source_sha256=manifest[name]['sha256'], changes=changes)
                assert projection(original) == projection(abundant)
                for change in changes:
                    if 'quantity_floor' not in change:
                        assert abundant[change['path']] == original[change['path']]
                        continue
                    before, after = original[change['path']]['Body'], abundant[change['path']]['Body']
                    minimum = min(D(side[i]) for side in (before['bids'], before['asks']) for i in range(0, len(side), 2))
                    numerator, denominator = minimum.as_integer_ratio()
                    expected_floor = (49000 * denominator + numerator - 1) // numerator
                    assert D(change['quantity_floor']) == expected_floor
                    for side in ('bids', 'asks'):
                        for i in range(1, len(before[side]), 2):
                            old = D(before[side][i])
                            expected = max(old, D(expected_floor)) if old > 0 else old
                            assert D(after[side][i]) == expected
                    changed_books += change['changed']
                    changed_levels += change['changed_levels']
                quotes.extend(dict(index=index, now_ns=now, **row) for row in quote_comparison(original, abundant, now))
                rows = {'observed': [json.loads(next(observed_stream)) for _ in range(9)],
                        'ample': [json.loads(next(ample_streams[fee])) for fee in (30, 40, 60) for _ in range(3)]}
                for model, records in rows.items():
                    assert {(row['account'], row['arm']) for row in records} == {(f'control_fee{fee}', arm) for fee in (30, 40, 60) for arm in ARMS}
                    for row in records:
                        assert row['index'] == index and row['now_ns'] == now
                        fee = int(row['account'].removeprefix('control_fee'))
                        reconcile(stats[model, fee, row['arm']], row, original, fee)
                    for fee in (30, 40, 60):
                        subset = {row['arm']: {key: value for key, value in row.items() if key not in ('arm', 'budget')}
                                  for row in records if row['account'] == f'control_fee{fee}'}
                        for left, right in (('baseline', 'cap9'), ('baseline', 'reserve3'), ('cap9', 'reserve3')):
                            identical[model, fee, left, right] += subset[left] == subset[right]
                paired.write(json.dumps(dict(index=index, now_ns=now, equity={model: {str(fee): {arm: None if stats[model, fee, arm]['last_equity'] is None else str(stats[model, fee, arm]['last_equity']) for arm in ARMS} for fee in (30, 40, 60)} for model in rows}), sort_keys=True) + '\n')
        for stream in (observed_stream, *ample_streams.values(), adaptations):
            assert stream.readline() == ''
    finally:
        observed_stream.close()
        adaptations.close()
        for stream in ample_streams.values():
            stream.close()
    summaries = {'observed': read(observed / 'summary.json'), 'ample': {str(fee): read(OUT / f'fee{fee}/summary.json') for fee in (30, 40, 60)}}
    states = {'observed': read(observed / 'final_states.json'), 'ample': {str(fee): read(OUT / f'fee{fee}/final_states.json') for fee in (30, 40, 60)}}
    coverage = []
    for (model, fee, arm), stat in stats.items():
        expected = summaries[model][arm][f'control_fee{fee}'] if model == 'observed' else summaries[model][str(fee)][arm]
        state = states[model][arm][f'control_fee{fee}'] if model == 'observed' else states[model][str(fee)][arm]
        assert stat['cycles'] == 3220 and stat['fills'] == (state['Fills'] or [])
        assert stat['cash'] == D(state['Cash'])
        assert stat['positions'] == {symbol: D(position['Quantity']) for symbol, position in state['Holdings'].items()}
        stat['return_pct'] = None if stat['last_equity'] is None else (stat['last_equity'] - 495) / 495 * 100
        for key in ('cycles', 'peak', 'dd', 'fees', 'turnover', 'buys', 'sells', 'unmarked', 'last_equity', 'return_pct'):
            if isinstance(stat[key], D):
                assert stat[key] == D(expected[key]), (model, fee, arm, key)
            else:
                assert stat[key] == expected[key]
        coverage.append(dict(model=model, fee_bps=fee, arm=arm, metrics=expected,
                             orders=order_coverage(stat['fills'], stat['days'], *ARMS[arm])))
    comparisons = []
    for fee in (30, 40, 60):
        for arm in ARMS:
            a, b = stats['observed', fee, arm], stats['ample', fee, arm]
            comparisons.append(dict(fee_bps=fee, arm=arm,
                return_difference_pp=str(b['return_pct'] - a['return_pct']),
                drawdown_difference_pp=str(b['dd'] - a['dd']),
                first_fill_difference=first_fill_difference(a['fills'], b['fills'])))
    quote_summary = {model: dict(target_observations=len(quotes),
        quote_feasible=sum(row[model]['quote_feasible'] for row in quotes),
        depth_limited=sum(row[model]['depth_limited'] is True for row in quotes),
        invalid_or_unavailable=sum(row[model]['depth_limited'] is None for row in quotes),
        notional_min=str(min(D(row[model]['hypothetical_buy_amount']) for row in quotes if 'hypothetical_buy_amount' in row[model])),
        notional_max=str(max(D(row[model]['hypothetical_buy_amount']) for row in quotes if 'hypothetical_buy_amount' in row[model])))
        for model in ('observed', 'ample')}
    save(folder / 'coverage.json', coverage)
    save(folder / 'comparisons.json', comparisons)
    save(folder / 'quotes.json', quotes)
    save(folder / 'quote_summary.json', quote_summary)
    save(folder / 'verification.json', dict(verified=True, reconciled_cycles=57960, accounts=18,
        changed_books=changed_books, changed_levels=changed_levels, integer_floor_checks=True,
        price_clock_projection_preserved=True, zero_trade_days_retained=True,
        policy_financial_path_equality=[dict(model=model, fee_bps=fee, left_arm=left, right_arm=right,
            identical_cycles=count, total_cycles=3220, policy_difference_observed=count < 3220)
            for (model, fee, left, right), count in sorted(identical.items())],
        hashes=hashes, output_hashes={str(path): sha(path) for path in folder.iterdir() if path.is_file()},
        reused_data=True, live_changed=False, deployment_qualified=False))
    print('DEPTH_ABLATION_AUDITED', 57960, quote_summary, flush=True)


if __name__ == '__main__':
    main()
