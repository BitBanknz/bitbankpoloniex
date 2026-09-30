"""Descriptive native-account coverage; never converts nonactivation into a pass."""
from collections import Counter
from datetime import datetime, timezone


def day(ns):
    return datetime.fromtimestamp(ns // 1_000_000_000, timezone.utc).date().isoformat()


def order_coverage(fills, observed_days, total_limit, reserve):
    if not 0 <= reserve <= total_limit or total_limit <= 0:
        raise ValueError('invalid daily limits')
    days = sorted(set(observed_days))
    counts = Counter({date: 0 for date in days})
    buys = Counter({date: 0 for date in days})
    sells = Counter({date: 0 for date in days})
    for fill in fills or []:
        date = fill['At'][:10]
        side = fill['Order']['side']
        if date not in counts or side not in ('BUY', 'SELL'):
            raise ValueError('fill outside observed days or invalid side')
        if counts[date] >= total_limit:
            raise ValueError('total order allowance exceeded')
        if side == 'BUY' and counts[date] >= total_limit - reserve:
            raise ValueError('buy allowance exceeded')
        counts[date] += 1
        (buys if side == 'BUY' else sells)[date] += 1
    return dict(days=days, filled_orders_by_day=dict(counts), buys_by_day=dict(buys), sells_by_day=dict(sells),
        maximum_daily_orders=max(counts.values(), default=0),
        days_reaching_buy_boundary=sum(value >= total_limit - reserve for value in counts.values()),
        days_reaching_total_limit=sum(value >= total_limit for value in counts.values()),
        days_reaching_nine=sum(value >= 9 for value in counts.values()),
        days_reaching_twelve=sum(value >= 12 for value in counts.values()),
        blocked_attempts_known=False)


def first_fill_difference(left, right):
    left, right = left or [], right or []
    common = 0
    while common < min(len(left), len(right)) and left[common] == right[common]:
        common += 1
    return dict(equal=common == len(left) == len(right), common_fills=common,
                left_next=None if common == len(left) else left[common],
                right_next=None if common == len(right) else right[common])
