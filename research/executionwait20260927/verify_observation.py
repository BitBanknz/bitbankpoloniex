"""Independently rerun the recovered suffix from the authenticated old state."""
import gzip
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
OUT = Path('/vfast/data/trading_research_20260924/poloniex_execution_wait_recovery_20260927_v1')
MIRROR = OUT / 'observation/mirror'
OLD = OUT / 'capture_v2/mirror'
sys.path.insert(0, str(HERE.parent / 'futurecompare20260926'))
from audit import BINARIES
from reference import transition
sys.path.insert(0, str(HERE / 'worker'))
from native import Native
import shadow
from outcomes import completed_cycle


def unpack(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def main():
    status = shadow.read(MIRROR / 'status.json')
    assert status['indices'] == list(range(172, status['indices'][-1] + 1))
    launch = shadow.read(OUT / 'remote_launch.json')
    manifest = shadow.read(MIRROR / 'manifest.json')
    for name, value in manifest.items():
        path = MIRROR / name
        assert path.stat().st_size == value['bytes'] and shadow.sha(path) == value['sha256']
    results = dict(at_ns=time.time_ns(), indices=status['indices'], variants={}, external_orders=False)
    for label, pair in BINARIES.items():
        root = MIRROR / label
        p = shadow.read(root / 'protocol.json')
        assert shadow.sha(root / 'protocol.json') == launch['protocols'][label]['sha256']
        assert shadow.sha(pair[0]) == p['files']['observed_cycle.test']
        assert shadow.sha(MIRROR / 'source/protocol.json') == p['source_protocol_sha256']
        for name, digest in p['files'].items():
            if name != 'observed_cycle.test':
                assert shadow.sha(root / name) == digest
        previous = shadow.sha(root / 'protocol.json')
        for index in range(status['indices'][-1] + 1):
            path = root / f'batch_{index:05d}.receipt.json'
            r = shadow.read(path)
            assert r['source_index'] == index and r['previous_sha256'] == previous and r['external_orders'] is False
            assert r['recovered_observed_data'] is True and r['actual_decision_commit_claimed'] is False
            assert r['source_available_before_compute'] is True
            if index <= 172:
                original = shadow.read(OLD / label / f'batch_{index:05d}.receipt.json')
                assert r['original_prefix_check'] == dict(verified=True, source_index=index,
                    original_receipt_sha256=shadow.sha(OLD / label / f'batch_{index:05d}.receipt.json'))
                assert r['logical_ns'] == original['logical_ns']
                # Same host, encoder and gzip settings: compressed bytes also match.
                assert all(r[k + '_sha256'] == original[k + '_sha256'] for k in ('input', 'output'))
            else:
                assert r['original_prefix_check'] is None
            previous = shadow.sha(path)
        assert previous == status['studies'][label]['last_receipt_sha256']
        states = {a['ID']:a['State'] for a in unpack(OLD / label / 'batch_00171.output.json.gz')}
        native = Native(pair[0])
        rows = []
        try:
            for index in status['indices']:
                name = f'batch_{index:05d}'
                receipt = shadow.read(root / (name + '.receipt.json'))
                for kind in ('input', 'output'):
                    assert shadow.sha(root / (name + '.' + kind + '.json.gz')) == receipt[kind + '_sha256']
                packet, provenance = shadow.load_capture(MIRROR / 'source', index, p)
                answers = []
                checks = []
                if packet:
                    packet['Accounts'] = [dict(ID=a['id'], Config=a['config'], Before=states.get(a['id'])) for a in p['accounts']]
                    for account in packet['Accounts']:
                        answer = native.apply({**account, 'NowNS':packet['NowNS'], 'Responses':packet['Responses']})
                        answer['CycleOutcome'] = completed_cycle(account['Before'], answer, packet['Responses'], packet['NowNS'])
                        answer['MoneyCheck'] = shadow.check_money(account['Before'], answer['State'], account['Config']['FeeRate'], packet['Responses'], packet['NowNS'])
                        answer['PostCycleBidEquity'] = shadow.post_mark(answer['State'], packet['Responses'], packet['NowNS'])
                        checked = transition(account['Before'], answer['State'], account['Config']['FeeRate'], packet['Responses'], packet['NowNS'], label == 'guarded')
                        checks.append(checked)
                        answers.append(answer)
                assert unpack(root / (name + '.input.json.gz')) == dict(packet=packet, provenance=provenance)
                assert unpack(root / (name + '.output.json.gz')) == answers
                for answer in answers:
                    states[answer['ID']] = answer['State']
                rows.append(dict(index=index, outcomes=[a['CycleOutcome']['kind'] for a in answers], gap=packet is None, checks=checks))
            target = OUT / (label + '_recovered_suffix.json.gz')
            with target.open('xb') as stream:
                stream.write(gzip.compress(shadow.encode(dict(rows=rows, final_states=states)), mtime=0))
            results['variants'][label] = dict(verified=True, through_index=status['indices'][-1],
                receipt_chain=previous, suffix_transitions=sum(len(r['checks']) for r in rows),
                suffix_gaps=[r['index'] for r in rows if r['gap']], fills=sum(len(r['new_fills']) for row in rows for r in row['checks']),
                outcomes=sorted({v for r in rows for v in r['outcomes']}), suffix_proof_sha256=shadow.sha(target),
                final_states={key:dict(cash=state['Cash'], holdings=state['Holdings'], high_water=state['HighWater'], fills=len(state['Fills'] or [])) for key, state in states.items()})
        finally:
            native.close()
    with (OUT / 'recovery_verified.json').open('xb') as stream:
        stream.write(shadow.encode(results))
    print('RECOVERY_SUFFIX_VERIFIED', {k:{n:v[n] for n in ('through_index','suffix_transitions','fills','outcomes')} for k,v in results['variants'].items()}, flush=True)


if __name__ == '__main__':
    main()
