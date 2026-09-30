from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import shadow

BASE=Path('/vfast/data/trading_research_20260924')
MIRROR=BASE/'poloniex_public_retention_first_prefix_v1/mirror'
ROWS=[json.loads(line) for line in gzip.decompress((BASE/'poloniex_quote_aware_v1/paired_replay_v2/cycles.jsonl.gz').read_bytes()).splitlines()]


class ShadowTests(unittest.TestCase):
    def test_all_native_money_transitions(self):
        for row in ROWS:
            r=row['input'];a=row['output'];shadow.check_money(r['Before'],a['State'],str(r['Config']['FeeRate']),r['Responses'],r['NowNS'])
    def test_source_expiry_is_not_forward_filled(self):
        p={'source_start_ns':json.loads((MIRROR/'protocol.json').read_text())['start_ns']}
        packet,provenance=shadow.load_capture(MIRROR,4,p)
        self.assertEqual(packet['Responses']['/prediction']['Status'],503)
        self.assertFalse(provenance['actual_decision_commit_claimed'])
    def test_exact_source_receipt_time(self):
        p={'source_start_ns':json.loads((MIRROR/'protocol.json').read_text())['start_ns']}
        packet,proof=shadow.load_capture(MIRROR,0,p)
        receipt=json.loads((MIRROR/'minute_00000.receipt.json').read_text())
        self.assertEqual(packet['NowNS'],receipt['complete_after_ns'])
        self.assertEqual(proof['archive_sha256'],receipt['archive_sha256'])
    def test_fee_corruption(self):self.corrupt(lambda s:s['Fills'][0].update(Fee='0'))
    def test_cash_corruption(self):self.corrupt(lambda s:s.update(Cash='495'))
    def test_quantity_corruption(self):self.corrupt(lambda s:next(iter(s['Holdings'].values())).update(Quantity='1'))
    def test_pending_intent_rejected(self):self.corrupt(lambda s:s.update(Pending={}))
    def test_borrow_order_rejected(self):self.corrupt(lambda s:s['Fills'][0]['Order'].update(allowBorrow=True))
    def test_day_cap_rejected(self):self.corrupt(lambda s:s.update(OrdersToday=13))
    def corrupt(self,fn):
        row=deepcopy(ROWS[0]);r=row['input'];s=row['output']['State'];fn(s)
        with self.assertRaises(AssertionError):shadow.check_money(r['Before'],s,str(r['Config']['FeeRate']),r['Responses'],r['NowNS'])
    def test_stale_or_missing_mark_is_unavailable(self):
        row=deepcopy(ROWS[0]);r=row['input'];s=row['output']['State']
        symbol=next(iter(s['Holdings']));r['Responses']['/markets/'+symbol+'/orderBook']['Body']['ts']-=60_000
        self.assertIsNone(shadow.post_mark(s,r['Responses'],r['NowNS']))
    def test_crossed_book_is_not_a_valuation(self):
        row=deepcopy(ROWS[0]);r=row['input'];s=row['output']['State']
        symbol=next(iter(s['Holdings']));r['Responses']['/markets/'+symbol+'/orderBook']['Body']['asks'][0]='0.000001'
        self.assertIsNone(shadow.post_mark(s,r['Responses'],r['NowNS']))
    def test_immutable_commit_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'receipt.json';shadow.publish(p,b'first')
            with self.assertRaises(FileExistsError):shadow.publish(p,b'second')
            self.assertEqual(p.read_bytes(),b'first')


if __name__=='__main__':unittest.main()
