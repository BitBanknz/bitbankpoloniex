from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from prefix import Prefix, sha


def encoded(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


class PrefixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'protocol.json').write_bytes(encoded(dict(first_index=0, external_orders=False)))
        self.protocol = sha(self.root / 'protocol.json')
        self.packet = dict(NowNS=10, Accounts=[dict(ID='a', Before=None)])
        self.provenance = dict(source_index=0, available_at_ns=10)
        self.proposals = [dict(ID='a', State=dict(Cash='495', HighWater='495'))]
        for kind, value in [('input', dict(packet=self.packet, provenance=self.provenance)), ('output', self.proposals)]:
            (self.root / f'batch_00000.{kind}.json.gz').write_bytes(gzip.compress(encoded(value), mtime=0))
        self.receipt = dict(source_index=0, previous_sha256=self.protocol, external_orders=False,
                            actual_decision_commit_claimed=False, source_available_before_compute=True, logical_ns=10,
                            input_sha256=sha(self.root / 'batch_00000.input.json.gz'), output_sha256=sha(self.root / 'batch_00000.output.json.gz'))
        (self.root / 'batch_00000.receipt.json').write_bytes(encoded(self.receipt))
        self.last = sha(self.root / 'batch_00000.receipt.json')

    def tearDown(self):
        self.temp.cleanup()

    def prefix(self):
        return Prefix(self.root, self.protocol, 0, self.last)

    def test_matching_prefix_and_state_mutation(self):
        prefix = self.prefix()
        self.assertTrue(prefix.verify(0, self.packet, self.provenance, self.proposals)['verified'])
        for field in ('Cash', 'HighWater'):
            bad = deepcopy(self.proposals)
            bad[0]['State'][field] = '500'
            with self.assertRaises(AssertionError):
                prefix.verify(0, self.packet, self.provenance, bad)
        bad = deepcopy(self.packet)
        bad['Accounts'][0]['Before'] = dict(Cash='495')
        with self.assertRaises(AssertionError):
            prefix.verify(0, bad, self.provenance, self.proposals)

    def test_hash_chain_and_unexpected_continuation(self):
        for field, value in [('previous_sha256', '0' * 64), ('source_index', 1), ('external_orders', True),
                             ('input_sha256', '0' * 64), ('source_available_before_compute', False)]:
            bad = {**self.receipt, field:value}
            (self.root / 'batch_00000.receipt.json').write_bytes(encoded(bad))
            with self.assertRaises(AssertionError):
                self.prefix()
        (self.root / 'batch_00000.receipt.json').write_bytes(encoded(self.receipt))
        (self.root / 'batch_00001.receipt.json').write_text('{}')
        with self.assertRaises(AssertionError):
            self.prefix()

    def test_gap_carries_no_synthetic_output(self):
        source = dict(packet=None, provenance=dict(reason='market_metadata_unavailable'))
        (self.root / 'batch_00000.input.json.gz').write_bytes(gzip.compress(encoded(source), mtime=0))
        (self.root / 'batch_00000.output.json.gz').write_bytes(gzip.compress(encoded([]), mtime=0))
        self.receipt.update(logical_ns=None, input_sha256=sha(self.root / 'batch_00000.input.json.gz'), output_sha256=sha(self.root / 'batch_00000.output.json.gz'))
        (self.root / 'batch_00000.receipt.json').write_bytes(encoded(self.receipt))
        self.last = sha(self.root / 'batch_00000.receipt.json')
        prefix = self.prefix()
        self.assertTrue(prefix.verify(0, None, source['provenance'], [])['verified'])
        with self.assertRaises(AssertionError):
            prefix.verify(0, None, source['provenance'], self.proposals)

    def test_committed_files_cannot_change_after_open(self):
        prefix = self.prefix()
        (self.root / 'batch_00000.output.json.gz').write_bytes(gzip.compress(encoded([]), mtime=0))
        with self.assertRaises(AssertionError):
            prefix.verify(0, self.packet, self.provenance, self.proposals)


if __name__ == '__main__':
    unittest.main()
