"""Source availability, native state replay, and independent Decimal transitions."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = Path('/vfast/data/trading_research_20260924')
OUT = BASE / 'poloniex_prospective_replacement_20260927_v2'
PREFIX = OUT / 'first_three'
MIRROR = PREFIX / 'mirror'
sys.path.insert(0, str(REPO / 'research/futurecompare20260926'))
from reference import transition, rules
from native import Native

BINARIES = {
    'unguarded':BASE / 'poloniex_quote_aware_v1/driver/candidate/observed_cycle.test',
    'guarded':BASE / 'poloniex_stop_topup_guard_v1/observed/engine.test'}
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p:json.loads(Path(p).read_bytes())
gz = lambda p:json.loads(gzip.decompress(Path(p).read_bytes()))


def main():
    captured = read(PREFIX / 'capture_verified.json'); assert captured['verified']
    assert sha(PREFIX / 'snapshot.tar.gz') == captured['transfer']['archive_sha256']
    assert sha(MIRROR / 'manifest.json') == captured['manifest_sha256']
    manifest = read(MIRROR / 'manifest.json')
    for path, value in manifest.items(): assert sha(MIRROR / path) == value['sha256']
    launch = read(OUT / 'remote_launch_response.json')
    assert launch['original_protocols_unchanged'] and not launch['external_orders'] and not launch['credentials_used']
    protocols = {}; source = MIRROR / 'source'
    for label, root in [('source',source),('unguarded',MIRROR/'unguarded'),('guarded',MIRROR/'guarded')]:
        p = read(root / 'protocol.json'); protocols[label] = p
        observed = read(root / 'launch.json'); started = read(root / 'started.json')
        assert p == launch['protocols'][observed['root']]
        assert observed['protocol_sha256'] == started['protocol_sha256'] == sha(root / 'protocol.json')
        assert p['registered_at_ns'] <= observed['at_ns'] <= started['at_ns'] < launch['start_ns']
        if label == 'source':
            assert p['recorder_sha256'] == sha(root / 'recorder.py')
            assert p['protocol_document_sha256'] == sha(root / 'PROTOCOL.md')
            assert p['format'] == 'poloniex-public-receipts-v1' and p['slots'] == 10080
            assert p['start_ns'] == launch['start_ns'] and p['end_exclusive_ns'] == launch['end_exclusive_ns']
            assert p['end_exclusive_ns'] == p['start_ns'] + 10080*rules.MINUTE
        else:
            assert p['format'] == 'poloniex-fixed-future-replay-v2' and p['first_index'] == 0 and p['last_index'] == 10079
            assert p['source_start_ns'] == launch['start_ns'] and p['source_protocol_sha256'] == sha(source / 'protocol.json')
            for filename, digest in p['files'].items():
                assert sha(BINARIES[label] if filename == 'observed_cycle.test' else root / filename) == digest
            assert not p['external_orders'] and not p['actual_decision_commit_claimed']
            assert all(a['config']['Mode'] == 'paper' for a in p['accounts']) and len(p['accounts']) == 6
    assert protocols['unguarded']['accounts'] == protocols['guarded']['accounts']
    packets = []; public_requests = 0
    for index in range(3):
        stem = f'minute_{index:05d}'; r = read(source / (stem+'.receipt.json'))
        assert r['index'] == index and r['scheduled_ns'] == launch['start_ns']+index*rules.MINUTE
        assert r['archive'] == stem+'.jsonl.gz' and sha(source / r['archive']) == r['archive_sha256']
        records = [json.loads(line) for line in gzip.decompress((source / r['archive']).read_bytes()).splitlines()]
        assert r['planned_requests'] == r['attempted_requests'] == len(records) == 11 and r['complete']
        responses = {}; previous = r['scheduled_ns']
        for record, endpoint in zip(records, rules.ENDPOINTS):
            assert r['scheduled_ns'] <= record['request_started_ns'] < r['scheduled_ns'] + 45_000_000_000
            value = rules.decode_record(record, endpoint, previous); previous = record['response_received_ns']
            assert record['wall_clock_stable']
            path = '/prediction' if record['name'] == 'ranks' else record['url'].split('api.poloniex.com',1)[1].split('?',1)[0]
            responses[path] = dict(Status=record['status'], Body=value) if value is not None else dict(Status=503, Body={})
        assert r['first_request_ns'] == records[0]['request_started_ns'] and r['last_receipt_ns'] == previous
        assert previous <= r['complete_after_ns'] <= captured['transfer']['ended_ns']
        assert responses['/markets']['Status'] == responses['/markets/ticker24h']['Status'] == 200
        packets.append(dict(NowNS=r['complete_after_ns'], Responses=responses))
        public_requests += len(records)
    outputs = {}; total_checks = 0
    for label in ('unguarded','guarded'):
        root = MIRROR / label; p = protocols[label]; states = {}; previous = sha(root / 'protocol.json')
        native = Native(BINARIES[label]); checks = []; outcomes = Counter()
        try:
            for index, expected in enumerate(packets):
                stem = f'batch_{index:05d}'; receipt = read(root / (stem+'.receipt.json'))
                assert receipt['source_index'] == index and receipt['previous_sha256'] == previous
                assert receipt['input_sha256'] == sha(root / (stem+'.input.json.gz')) and receipt['output_sha256'] == sha(root / (stem+'.output.json.gz'))
                previous = sha(root / (stem+'.receipt.json'))
                item = gz(root / (stem+'.input.json.gz')); packet = item['packet']; answers = gz(root / (stem+'.output.json.gz'))
                assert packet['NowNS'] == expected['NowNS'] and packet['Responses'] == expected['Responses']
                assert item['provenance']['receipt_sha256'] == sha(source / f'minute_{index:05d}.receipt.json')
                assert receipt['logical_ns'] == expected['NowNS'] <= receipt['computed_started_ns'] <= receipt['computed_complete_ns'] <= captured['transfer']['ended_ns']
                assert receipt['source_available_before_compute'] and not receipt['external_orders'] and not receipt['actual_decision_commit_claimed']
                assert len(packet['Accounts']) == len(answers) == 6
                for spec, request, answer in zip(p['accounts'], packet['Accounts'], answers):
                    aid = spec['id']; assert request == dict(ID=aid, Config=spec['config'], Before=states.get(aid)) and answer['ID'] == aid
                    replay = native.apply({**request, **expected})
                    for field in ('State','CycleError','Paused'): assert replay[field] == answer[field], ('native mismatch',label,index,aid,field)
                    v = transition(states.get(aid), answer['State'], spec['config']['FeeRate'], expected['Responses'], expected['NowNS'], label == 'guarded')
                    assert v['equity'] == answer['PostCycleBidEquity']
                    assert len(v['new_fills']) == answer['MoneyCheck']['new_fills']
                    states[aid] = answer['State']; outcomes[answer['CycleOutcome']['kind']] += 1; total_checks += 1
                    checks.append(dict(index=index, account=aid, equity=v['equity'], fills=len(v['new_fills']), fees=v['fees']))
        finally: native.close()
        outputs[label] = dict(verified=True, batches=3, transitions=len(checks), checks=checks, outcomes=dict(outcomes), last_receipt_sha256=previous)
    assert total_checks == 36
    bound = {str(p):sha(p) for p in [Path(__file__), REPO/'research/futurecompare20260926/reference.py', Path(rules.__file__),
              Path(sys.modules['native'].__file__), *BINARIES.values(), PREFIX/'capture_verified.json', OUT/'remote_launch_response.json']}
    result = dict(verified=True, at_ns=time.time_ns(), public_requests=public_requests, native_replayed_transitions=total_checks,
                  independent_decimal_transitions=total_checks, workers=outputs, hashes=bound,
                  first_three_only=True, complete_comparison=False, live_trading_changed=False, external_orders=False)
    with (PREFIX / 'verification.json').open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print('FIRST_THREE_VERIFIED', total_checks, flush=True)


if __name__ == '__main__': main()
