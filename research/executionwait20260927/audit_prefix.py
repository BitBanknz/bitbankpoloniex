"""Recompute every original state, then cross the failed forecast boundary."""
import gzip
import importlib.util
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
OUT = Path('/vfast/data/trading_research_20260924/poloniex_execution_wait_recovery_20260927_v1')
MIRROR = OUT / 'capture_v2/mirror'
sys.path.insert(0, str(HERE.parent / 'futurecompare20260926'))
from audit import BINARIES
from reference import transition
sys.path.insert(0, str(HERE / 'worker'))
from native import Native
from prefix import Prefix
import shadow
from outcomes import completed_cycle


def main():
    assert Path(shadow.__file__).resolve() == HERE / 'worker/shadow.py'
    assert Path(sys.modules['outcomes'].__file__).resolve() == HERE / 'worker/outcomes.py'
    spec = importlib.util.spec_from_file_location('old_outcomes', MIRROR / 'unguarded/outcomes.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    manifest = shadow.read(MIRROR / 'manifest.json')
    for name, value in manifest.items():
        path = MIRROR / name
        assert path.stat().st_size == value['bytes'] and shadow.sha(path) == value['sha256']
    result = dict(started_ns=time.time_ns(), captured_files=len(manifest), variants={})
    for label, pair in BINARIES.items():
        root = MIRROR / label
        p = shadow.read(root / 'protocol.json')
        assert shadow.sha(pair[0]) == p['files']['observed_cycle.test']
        assert shadow.sha(MIRROR / 'source/protocol.json') == p['source_protocol_sha256']
        for name, digest in p['files'].items():
            if name != 'observed_cycle.test':
                assert shadow.sha(root / name) == digest
        prefix = Prefix(root, shadow.sha(root / 'protocol.json'), 172, shadow.sha(root / 'batch_00172.receipt.json'))
        native = Native(pair[0])
        states = {}
        rows = []
        try:
            for index in range(175):
                packet, provenance = shadow.load_capture(MIRROR / 'source', index, p)
                proposals = []
                money = []
                if packet is not None:
                    packet['Accounts'] = [dict(ID=a['id'], Config=a['config'], Before=states.get(a['id'])) for a in p['accounts']]
                    for account in packet['Accounts']:
                        answer = native.apply({**account, 'NowNS':packet['NowNS'], 'Responses':packet['Responses']})
                        answer['CycleOutcome'] = completed_cycle(account['Before'], answer, packet['Responses'], packet['NowNS'])
                        answer['MoneyCheck'] = shadow.check_money(account['Before'], answer['State'], account['Config']['FeeRate'], packet['Responses'], packet['NowNS'])
                        answer['PostCycleBidEquity'] = shadow.post_mark(answer['State'], packet['Responses'], packet['NowNS'])
                        checked = transition(account['Before'], answer['State'], account['Config']['FeeRate'], packet['Responses'], packet['NowNS'], label == 'guarded')
                        money.append(checked)
                        if index == 173:
                            try:
                                old.completed_cycle(account['Before'], answer, packet['Responses'], packet['NowNS'])
                            except AssertionError:
                                pass
                            else:
                                raise AssertionError('original failure not reproduced')
                            assert answer['CycleOutcome']['kind'] == 'waiting_execution' and checked['new_fills'] == []
                        proposals.append(answer)
                check = prefix.verify(index, packet, provenance, proposals) if index <= 172 else None
                for answer in proposals:
                    states[answer['ID']] = answer['State']
                rows.append(dict(index=index, prefix_check=check, gap=packet is None,
                                 outcomes=[a['CycleOutcome'] for a in proposals], decimal_checks=money))
                if index % 25 == 0 or index >= 171:
                    print('PREFIX_VERIFIED', label, index, flush=True)
            assert [r['index'] for r in rows if r['gap']] == [97]
            assert sum(len(r['decimal_checks']) for r in rows) == 1044
            target = OUT / (label + '_prefix_audit.json.gz')
            with target.open('xb') as stream:
                stream.write(gzip.compress(shadow.encode(dict(rows=rows, final_states=states)), mtime=0))
            result['variants'][label] = dict(verified=True, original_batches=173, gap_indices=[97], original_transitions=1032,
                total_transitions=1044, boundary_transitions=24, audit_sha256=shadow.sha(target),
                binary_sha256=shadow.sha(pair[0]), original_protocol_sha256=shadow.sha(root / 'protocol.json'),
                original_last_receipt_sha256=shadow.sha(root / 'batch_00172.receipt.json'))
        finally:
            native.close()
    result['finished_ns'] = time.time_ns()
    result['source_hashes'] = {str(p):shadow.sha(p) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    with (OUT / 'prefix_verified.json').open('xb') as stream:
        stream.write(shadow.encode(result))
    print('FULL_PREFIX_AND_BOUNDARY_VERIFIED', result['variants'], flush=True)


if __name__ == '__main__':
    main()
