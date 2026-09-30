"""Authenticate a failed consumer's committed prefix before recovered replay."""
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


class Prefix:
    def __init__(self, root, protocol_sha, last_index, last_sha):
        self.root = Path(root)
        assert sha(self.root / 'protocol.json') == protocol_sha
        self.protocol = read(self.root / 'protocol.json')
        assert self.protocol['first_index'] == 0
        assert self.protocol['external_orders'] is False
        assert type(last_index) is int and 0 <= last_index < 10080
        self.last = last_index
        self.receipts = {}
        previous = protocol_sha
        for index in range(last_index + 1):
            path = self.root / f'batch_{index:05d}.receipt.json'
            receipt = read(path)
            assert receipt['source_index'] == index and receipt['previous_sha256'] == previous
            assert receipt['external_orders'] is False and receipt['actual_decision_commit_claimed'] is False
            assert receipt['source_available_before_compute'] is True
            for kind in ('input', 'output'):
                assert sha(self.root / f'batch_{index:05d}.{kind}.json.gz') == receipt[kind + '_sha256']
            previous = sha(path)
            self.receipts[index] = dict(sha256=previous, receipt=receipt)
        assert previous == last_sha
        assert not (self.root / f'batch_{last_index + 1:05d}.receipt.json').exists()

    def verify(self, index, packet, provenance, proposals):
        assert index in self.receipts
        entry = self.receipts[index]
        assert sha(self.root / f'batch_{index:05d}.receipt.json') == entry['sha256']
        decoded = {}
        for kind in ('input', 'output'):
            path = self.root / f'batch_{index:05d}.{kind}.json.gz'
            assert sha(path) == entry['receipt'][kind + '_sha256']
            decoded[kind] = json.loads(gzip.decompress(path.read_bytes()))
        assert decoded['input'] == dict(packet=packet, provenance=provenance), ('prefix input changed', index)
        assert decoded['output'] == proposals, ('prefix output changed', index)
        assert entry['receipt']['logical_ns'] == (packet['NowNS'] if packet else None)
        return dict(verified=True, original_receipt_sha256=entry['sha256'], source_index=index)
