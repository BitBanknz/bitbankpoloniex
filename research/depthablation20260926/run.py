"""One fee per process, native own-state accounts over the frozen entire prefix."""
import argparse
from collections import Counter
from decimal import Decimal as D
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from bookmodel import projection, transform
from common import ARMS, HERE, OUT, PARENT, SOURCE, Native, causal, daily_budget, read, save, sha, transition


def main(fee):
    assert fee in (30, 40, 60)
    proof = read(OUT / 'preflight.json')
    assert proof['verified']
    registration = read(OUT / 'registration.json')
    assert sha(OUT / 'registration.json') == proof['registration_sha256']
    assert all(sha(path) == digest for path, digest in registration['hashes'].items())
    folder = OUT / ('fee' + str(fee))
    folder.mkdir(exist_ok=False)
    source = SOURCE / 'mirror'
    capture = read(SOURCE / 'capture.verified.json')
    assert sha(source / 'manifest.json') == capture['manifest_sha256']
    manifest = read(source / 'manifest.json')
    aid = 'control_fee' + str(fee)
    states = {arm: None for arm in ARMS}
    stats = {arm: dict(cycles=0, peak=D(495), dd=D(0), fees=D(0), turnover=D(0), buys=0,
                      sells=0, unmarked=0, last_equity=None) for arm in ARMS}
    counters = Counter()
    input_hashes = {}
    temp = Path(tempfile.mkdtemp(prefix='depth-ablation-fee' + str(fee) + '-', dir='/dev/shm'))
    os.environ['TMPDIR'] = str(temp)
    native = Native(PARENT / 'observed/engine.test')
    count = 0
    try:
        with (folder / 'paths.jsonl').open('x') as paths, (folder / 'adapters.jsonl').open('x') as adaptations:
            for index in range(78, 3298):
                name = f'guarded/batch_{index:05d}.input.json.gz'
                path = source / name
                digest = sha(path)
                assert digest == manifest[name]['sha256']
                input_hashes[str(path)] = digest
                stored = json.loads(gzip.decompress(path.read_bytes()))
                packet = stored['packet']
                assert packet['NowNS'] == stored['provenance']['available_at_ns']
                responses, changes = transform(packet['Responses'], packet['NowNS'])
                assert projection(responses) == projection(packet['Responses'])
                counters.update(row['reason'] for row in changes)
                adaptations.write(json.dumps(dict(index=index, now_ns=packet['NowNS'], source_sha256=digest, changes=changes), sort_keys=True) + '\n')
                account = next(account for account in packet['Accounts'] if account['ID'] == aid)
                for arm, (maximum, reserve) in ARMS.items():
                    config = {**account['Config'], 'MaxOrdersDay': maximum, 'ExitOrderReserve': reserve}
                    before = states[arm]
                    request = dict(ID=aid, Config=config, Before=before, NowNS=packet['NowNS'], Responses=responses)
                    causal(before, packet['NowNS'])
                    answer = native.apply(request)
                    causal(answer['State'], packet['NowNS'])
                    money = transition(before, answer['State'], config['FeeRate'], responses, packet['NowNS'], True)
                    budget = daily_budget(before, answer['State'], config, packet['NowNS'])
                    state = answer['State']
                    states[arm] = state
                    stat = stats[arm]
                    stat['cycles'] += 1
                    stat['fees'] += D(money['fees'])
                    stat['turnover'] += D(money['turnover'])
                    stat['buys'] += sum(fill['Order']['side'] == 'BUY' for fill in money['new_fills'])
                    stat['sells'] += sum(fill['Order']['side'] == 'SELL' for fill in money['new_fills'])
                    if money['equity'] is None:
                        stat['unmarked'] += 1
                        stat['last_equity'] = None
                    else:
                        equity = D(money['equity'])
                        stat['peak'] = max(stat['peak'], equity)
                        stat['dd'] = max(stat['dd'], (stat['peak'] - equity) / stat['peak'] * 100)
                        stat['last_equity'] = equity
                    paths.write(json.dumps(dict(index=index, arm=arm, account=aid, now_ns=packet['NowNS'],
                        budget=budget, **money), sort_keys=True) + '\n')
                    count += 1
                if index % 500 == 0:
                    print('DEPTH_ABLATION', fee, index, count, flush=True)
    finally:
        native.close()
        shutil.rmtree(temp)
    assert count == 9660
    for stat in stats.values():
        stat['return_pct'] = None if stat['last_equity'] is None else (stat['last_equity'] - 495) / 495 * 100
    summary = {arm: {key: str(value) if isinstance(value, D) else value for key, value in stat.items()} for arm, stat in stats.items()}
    save(folder / 'summary.json', summary)
    save(folder / 'final_states.json', states)
    assert all(sha(path) == digest for path, digest in registration['hashes'].items())
    save(folder / 'verification.json', dict(verified=True, at_ns=time.time_ns(), fee_bps=fee, native_cycles=count,
        input_hashes=input_hashes, unchanged_price_clock_projection=True, independent_money_and_budget_checks=True,
        adapter_reasons=dict(counters), output_hashes={name: sha(folder / name) for name in
            ('summary.json', 'final_states.json', 'paths.jsonl', 'adapters.jsonl')}, live_changed=False))
    print('DEPTH_ABLATION_VERIFIED', fee, count, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fee-bps', required=True, type=int, choices=(30, 40, 60))
    main(parser.parse_args().fee_bps)
