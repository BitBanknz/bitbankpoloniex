from copy import deepcopy
from decimal import Decimal as D
import random
import unittest

from bookmodel import levels, projection, transform

NOW = 1790211645000000000
PATH = '/markets/AAA_USDT/orderBook'


def packet():
    return {PATH: {'Status': 200, 'Body': {'ts': NOW // 1000000, 'time': 123,
            'bids': ['10', '1', '9.999', '0', '9.998', '2'],
            'asks': ['10.01', '3', '10.011', '4']}},
            '/prediction': {'Status': 503, 'Body': {}},
            '/markets': {'Status': 200, 'Body': [{'symbol': 'AAA_USDT'}]}}


class BookModelTests(unittest.TestCase):
    def test_identity_and_input_immutability(self):
        original = packet()
        before = deepcopy(original)
        actual, changes = transform(original, NOW, 'identity')
        self.assertEqual(actual, original)
        self.assertIsNot(actual, original)
        self.assertFalse(any(row['changed'] for row in changes))
        transform(original, NOW)
        self.assertEqual(original, before)

    def test_exact_projection_and_ample_floor(self):
        original = packet()
        actual, changes = transform(original, NOW)
        self.assertEqual(projection(actual), projection(original))
        self.assertEqual(changes[0]['quantity_floor'], '4901')
        self.assertEqual(changes[0]['changed_levels'], 4)
        self.assertEqual(actual[PATH]['Body']['bids'][3], '0')
        self.assertEqual(actual['/prediction'], original['/prediction'])

    def test_unavailable_invalid_and_stale_are_not_repaired(self):
        for key, value in (('bids', ['11', '1']), ('bids', ['10', '-1']),
                           ('asks', ['10.02', '1', '10.01', '1']),
                           ('asks', ['NaN', '1']), ('bids', ['10', 'Infinity']),
                           ('bids', ['10', 1]), ('asks', [10.01, '1']),
                           ('bids', ['10']), ('ts', 0), ('ts', True),
                           ('ts', NOW // 1000000 - 30001), ('ts', NOW // 1000000 + 5001)):
            original = packet()
            original[PATH]['Body'][key] = value
            actual, changes = transform(original, NOW)
            self.assertEqual(actual, original)
            self.assertFalse(changes[0]['changed'])
        original = packet()
        original[PATH]['Status'] = 503
        self.assertEqual(transform(original, NOW)[0], original)

    def test_native_millisecond_freshness_boundaries(self):
        for offset in (-30000, 5000):
            original = packet()
            original[PATH]['Body']['ts'] += offset
            self.assertTrue(transform(original, NOW)[1][0]['changed'])

    def test_preserve_zero_sides_and_existing_large_sizes(self):
        original = packet()
        original[PATH]['Body']['asks'] = ['10.01', '0']
        original[PATH]['Body']['bids'] = ['10', '999999']
        actual, _ = transform(original, NOW)
        self.assertEqual(actual, original)

    def test_model_name_is_explicit(self):
        with self.assertRaises(ValueError):
            transform(packet(), NOW, 'optimistic_auto')

    def test_200_seeded_price_scales_preserve_prices_and_exceed_order_size(self):
        rng = random.Random(20260926)
        for _ in range(200):
            price = D(rng.randint(1000, 2000)).scaleb(rng.randint(-12, 4))
            original = packet()
            original[PATH]['Body']['bids'] = [str(price), '0.0001']
            original[PATH]['Body']['asks'] = [str(price * D('1.001')), '0.0001']
            actual, _ = transform(original, NOW)
            self.assertEqual(projection(actual), projection(original))
            for side in ('bids', 'asks'):
                p, quantity = levels(actual[PATH]['Body'][side], side == 'asks')[0]
                self.assertGreaterEqual(p * quantity * D('.1'), 4900)


if __name__ == '__main__':
    unittest.main()
