from copy import deepcopy
from decimal import Decimal as D
import unittest

from audit import initialize, reconcile

NOW = 1790211645000000000


def source(bid):
    return {'/markets/AAA_USDT/orderBook': {'Status': 200, 'Body': {'bids': [bid, '1000'], 'ts': NOW // 1000000}}}


def row(side='BUY', quantity='1', price='10', amount='10', fee='0.03', cash='484.97', bid='9.9', equity='494.87'):
    fill = {'At': '2026-09-24T01:00:45Z', 'Order': {'symbol': 'AAA_USDT', 'side': side, 'price': price, 'quantity': quantity},
            'Quantity': quantity, 'Amount': amount, 'Fee': fee}
    return dict(now_ns=NOW, dust=[], new_fills=[fill], fees=fee, turnover=amount, cash=cash,
                marks={'AAA_USDT': bid}, unpriced=[], equity=equity)


class AccountAuditTests(unittest.TestCase):
    def test_buy_and_partial_sale_hand_calculated_cash_and_inventory(self):
        state = initialize()
        reconcile(state, row(), source('9.9'), 30)
        self.assertEqual(state['cash'], D('484.97'))
        self.assertEqual(state['dd'], (D(495) - D('494.87')) / 495 * 100)
        sale = row('SELL', '.4', '11', '4.4', '.0132', '489.3568', '10.9', '495.8968')
        reconcile(state, sale, source('10.9'), 30)
        self.assertEqual(state['positions'], {'AAA_USDT': D('.6')})
        self.assertEqual(state['fees'], D('.0432'))
        self.assertEqual(state['last_equity'], D('495.8968'))

    def test_fee_and_source_mark_mutations_rejected(self):
        for changed in ('fee', 'price', 'quantity'):
            value = deepcopy(row())
            if changed == 'fee':
                value['new_fills'][0]['Fee'] = '.030000000000000001'
            elif changed == 'quantity':
                value['new_fills'][0]['Order']['quantity'] = '2'
            else:
                value['marks']['AAA_USDT'] = '10'
            with self.assertRaises(AssertionError):
                reconcile(initialize(), value, source('9.9'), 30)

    def test_unpriced_position_does_not_carry_equity_forward(self):
        state = initialize()
        reconcile(state, row(), source('9.9'), 30)
        missing = dict(now_ns=NOW, dust=[], new_fills=[], fees='0', turnover='0', cash='484.97',
                       marks={}, unpriced=['AAA_USDT'], equity=None)
        reconcile(state, missing, {}, 30)
        self.assertIsNone(state['last_equity'])
        self.assertEqual(state['unmarked'], 1)

    def test_dust_removal_does_not_invent_cash(self):
        state = initialize()
        reconcile(state, row(), source('9.9'), 30)
        removed = dict(now_ns=NOW, dust=[dict(symbol='AAA_USDT', quantity='1')], new_fills=[],
                       fees='0', turnover='0', cash='484.97', marks={}, unpriced=[], equity='484.97')
        reconcile(state, removed, {}, 30)
        self.assertFalse(state['positions'])
        self.assertEqual(state['cash'], D('484.97'))
        self.assertEqual(state['last_equity'], D('484.97'))


if __name__ == '__main__':
    unittest.main()
