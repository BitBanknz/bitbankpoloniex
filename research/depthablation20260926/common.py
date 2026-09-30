"""Fixed paths and authenticated dependencies for a depth-only diagnostic."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = Path('/vfast/data/trading_research_20260924')
OUT = BASE / 'poloniex_depth_ablation_v1'
PARENT = BASE / 'poloniex_exit_reserve_v1'
SOURCE = BASE / 'poloniex_future_prefix_3297_v1'
ARMS = {'baseline': (12, 0), 'cap9': (9, 0), 'reserve3': (12, 3)}
sys.path.insert(0, str(REPO / 'research/exitreserve20260926'))
from checks_v2 import causal, daily_budget  # noqa: E402
sys.path.insert(0, str(REPO / 'research/quoteaware20260924'))
from native import Native  # noqa: E402
sys.path.insert(0, str(REPO / 'research/futurecompare20260926'))
from reference import transition  # noqa: E402


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def parent_hash(path):
    proof = read(PARENT / 'completion.json')
    bindings = {**proof['upstream_hash_checks'], **proof['artifact_hashes']}
    expected = bindings[str(path)]
    assert sha(path) == expected, str(path)
    return expected
