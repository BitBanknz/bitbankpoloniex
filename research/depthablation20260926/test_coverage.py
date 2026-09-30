import unittest

from coverage import first_fill_difference, order_coverage


def fill(side, date='2026-09-25', quantity='1'):
    return {'At': date + 'T01:00:00Z', 'Order': {'side': side}, 'Quantity': quantity}


class CoverageTests(unittest.TestCase):
    def test_zero_trade_days_stay_in_denominator(self):
        report = order_coverage([fill('BUY')], ['2026-09-24', '2026-09-25', '2026-09-26'], 12, 3)
        self.assertEqual(report['filled_orders_by_day'], {'2026-09-24': 0, '2026-09-25': 1, '2026-09-26': 0})
        self.assertEqual(report['days_reaching_buy_boundary'], 0)
        self.assertFalse(report['blocked_attempts_known'])

    def test_sales_use_the_same_daily_counter(self):
        fills = [fill('SELL')] * 3 + [fill('BUY')] * 6
        report = order_coverage(fills, ['2026-09-25'], 12, 3)
        self.assertEqual(report['days_reaching_buy_boundary'], 1)
        self.assertEqual(report['days_reaching_total_limit'], 0)
        with self.assertRaises(ValueError):
            order_coverage([*fills, fill('BUY')], ['2026-09-25'], 12, 3)
        self.assertEqual(order_coverage([*fills, *[fill('SELL')] * 3], ['2026-09-25'], 12, 3)['days_reaching_total_limit'], 1)

    def test_day_reset_is_explicit(self):
        fills = [fill('BUY')] * 9 + [fill('BUY', '2026-09-26')] * 9
        report = order_coverage(fills, ['2026-09-25', '2026-09-26'], 12, 3)
        self.assertEqual(report['maximum_daily_orders'], 9)
        self.assertEqual(report['days_reaching_nine'], 2)

    def test_invalid_or_outside_period_fills_rejected(self):
        for fills in ([fill('OTHER')], [fill('BUY', '2026-09-24')], [fill('BUY')] * 13):
            with self.assertRaises(ValueError):
                order_coverage(fills, ['2026-09-25'], 12, 0)

    def test_first_difference_does_not_require_different_timestamps(self):
        first, second = fill('BUY'), fill('BUY', quantity='2')
        result = first_fill_difference([first], [second])
        self.assertFalse(result['equal'])
        self.assertEqual(result['common_fills'], 0)
        self.assertEqual(result['left_next']['At'], result['right_next']['At'])
        self.assertTrue(first_fill_difference([first], [first])['equal'])


if __name__ == '__main__':
    unittest.main()
