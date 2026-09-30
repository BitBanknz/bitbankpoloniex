import base64
from copy import deepcopy
from decimal import Decimal
import hashlib
import unittest
import verify


class VerificationTests(unittest.TestCase):
    def record(self):
        raw=b'{"value":1}'
        return dict(name='ranks',url=verify.ENDPOINTS[0][1],method='GET',credentials_used=False,
            body_b64=base64.b64encode(raw).decode(),body_bytes=len(raw),body_sha256=hashlib.sha256(raw).hexdigest(),
            request_started_ns=100,response_received_ns=200,monotonic_started_ns=1000,monotonic_received_ns=1100,
            wall_clock_stable=True,status=200,error=None,body_truncated=False)
    def test_body_corruption_rejected(self):
        r=self.record();r['body_b64']=base64.b64encode(b'{"value":2}').decode()
        with self.assertRaisesRegex(AssertionError,'body integrity'):verify.decode_record(r,verify.ENDPOINTS[0],0)
    def test_wrong_endpoint_rejected(self):
        r=self.record();r['url']='https://example.com'
        with self.assertRaisesRegex(AssertionError,'endpoint identity'):verify.decode_record(r,verify.ENDPOINTS[0],0)
    def test_clock_flag_corruption_rejected(self):
        r=self.record();r['response_received_ns']+=6_000_000_000
        with self.assertRaisesRegex(AssertionError,'clock stability'):verify.decode_record(r,verify.ENDPOINTS[0],0)
    def test_reordered_requests_rejected(self):
        with self.assertRaisesRegex(AssertionError,'request ordering'):verify.decode_record(self.record(),verify.ENDPOINTS[0],101)
    def test_http_error_never_produces_data(self):
        r=self.record();r['status']=503
        self.assertIsNone(verify.decode_record(r,verify.ENDPOINTS[0],0))
    def test_forecast_expiry_and_no_forward_fill(self):
        p=dict(available=True,venue='POLONIEX',mode='research_rank_forecast',issued_at='2026-09-24T00:00:00Z',execution_hour='2026-09-24T01:00:00Z',rank_scores={'TRXUSDT':1})
        execution=verify.timestamp(p['execution_hour'])
        self.assertIsNone(verify.ranks_at(p,execution-1))
        self.assertEqual(verify.ranks_at(p,execution),{'TRX_USDT':Decimal(1)})
        self.assertIsNone(verify.ranks_at(p,execution+verify.HOUR))
        self.assertIsNone(verify.ranks_at(None,execution))
    def test_malformed_or_unsorted_depth_rejected(self):
        for values in (['1'],['2','1','1','1'],['NaN','1'],['1','-1']):
            with self.assertRaises(AssertionError):verify.levels(values,True)
    def fixtures(self):
        now=verify.timestamp('2026-09-24T01:00:00Z')
        market=dict(symbol='TRX_USDT',state='NORMAL',quoteCurrencyName='USDT',symbolTradeLimit=dict(priceScale=2,quantityScale=2,minQuantity='.01',minAmount='1',maxQuantity='0',maxAmount='0'))
        ticker=dict(amount='100000',ts=now//1_000_000)
        book=dict(asks=['100.20','10'],bids=['100','10'],ts=now//1_000_000)
        return market,ticker,book,now
    def test_freshness_and_spread_constraints(self):
        m,t,b,now=self.fixtures()
        self.assertTrue(verify.feasibility(m,t,b,now)['quote_feasible'])
        b['asks'][0]='100.31';self.assertIn('spread',verify.feasibility(m,t,b,now)['reasons'])
        b['ts']-=30_001;self.assertIn('book_age',verify.feasibility(m,t,b,now)['reasons'])
    def test_small_depth_below_exchange_minimum(self):
        m,t,b,now=self.fixtures();b['asks'][1]='.01'
        reasons=verify.feasibility(m,t,b,now)['reasons']
        self.assertIn('minAmount',reasons);self.assertIn('zero_size',reasons)
    def test_rounding_and_account_scope(self):
        r=verify.feasibility(*self.fixtures())
        self.assertEqual(r['hypothetical_buy_price'],'100.20')
        self.assertEqual(r['hypothetical_buy_quantity'],'0.48')
        self.assertEqual(r['hypothetical_buy_amount'],'48.0960')
        self.assertFalse(r['account_gates_checked'])


if __name__=='__main__':unittest.main()
