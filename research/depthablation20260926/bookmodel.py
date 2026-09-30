"""Pure current-packet liquidity ablation; no I/O and no history or future input."""
from copy import deepcopy
from decimal import Decimal as D, InvalidOperation, ROUND_CEILING


def levels(flat, ascending):
    if not isinstance(flat, list) or len(flat) < 2 or len(flat) % 2:
        raise ValueError('incomplete levels')
    if any(not isinstance(value, str) for value in flat):
        raise ValueError('book levels must remain strings')
    try:
        rows = [(D(flat[i]), D(flat[i + 1])) for i in range(0, len(flat), 2)]
    except (TypeError, InvalidOperation):
        raise ValueError('invalid level number') from None
    if any(not p.is_finite() or not q.is_finite() or p <= 0 or q < 0 for p, q in rows):
        raise ValueError('invalid level value')
    prices = [p for p, _ in rows]
    if prices != sorted(prices, reverse=not ascending):
        raise ValueError('unordered prices')
    return rows


def fresh(ts, now):
    return isinstance(ts, int) and not isinstance(ts, bool) and 0 < ts <= now // 1_000_000 + 5000 and ts >= now // 1_000_000 - 30000


def projection(responses):
    result = deepcopy(responses)
    for path, response in result.items():
        if not path.endswith('/orderBook') or not isinstance(response.get('Body'), dict):
            continue
        for side in ('bids', 'asks'):
            flat = response['Body'].get(side)
            if isinstance(flat, list):
                for index in range(1, len(flat), 2):
                    flat[index] = '<quantity>'
    return result


def transform(responses, now, mode='ample'):
    if mode not in ('identity', 'ample'):
        raise ValueError('explicit registered book model required')
    result = deepcopy(responses)
    changes = []
    for path, response in result.items():
        if not path.endswith('/orderBook'):
            continue
        row = dict(path=path, changed=False, reason=None, changed_levels=0)
        changes.append(row)
        if mode == 'identity':
            row['reason'] = 'identity'
            continue
        body = response.get('Body')
        if response.get('Status') != 200 or not isinstance(body, dict):
            row['reason'] = 'unavailable'
            continue
        if not fresh(body.get('ts'), now):
            row['reason'] = 'stale_or_invalid_clock'
            continue
        try:
            bids, asks = levels(body.get('bids'), False), levels(body.get('asks'), True)
            if bids[0][0] > asks[0][0]:
                raise ValueError('crossed book')
        except ValueError as error:
            row['reason'] = str(error)
            continue
        floor = (D(49000) / min(p for p, _ in bids + asks)).to_integral_value(rounding=ROUND_CEILING)
        row['quantity_floor'] = str(floor)
        for side, parsed in (('bids', bids), ('asks', asks)):
            for i, (_, quantity) in enumerate(parsed):
                if 0 < quantity < floor:
                    body[side][2 * i + 1] = str(floor)
                    row['changed_levels'] += 1
        row['changed'] = row['changed_levels'] > 0
        row['reason'] = 'positive_quantities_raised' if row['changed'] else 'no_positive_quantity_below_floor'
    assert projection(result) == projection(responses)
    return result, changes
