"""Seal launch and initial correctness evidence, not the ongoing seven-day result."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = Path('/vfast/data/trading_research_20260924')
OUT = BASE / 'poloniex_prospective_replacement_20260927_v2'
REPORT = REPO / 'docs/2026-09-27-prospective-replacement-results.md'
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p:json.loads(Path(p).read_bytes())


def main():
    package = read(OUT / 'package_verification.json'); assert package['verified']
    for mapping in (package['hashes'], package['artifacts']):
        for p, h in mapping.items(): assert sha(p) == h
    launch = read(OUT / 'remote_launch_response.json'); receipt = read(OUT / 'remote_launch_receipt.json')
    assert receipt['returncode'] == 0 and sha(OUT / 'remote_launch_response.json') == receipt['response_sha256']
    assert sha(OUT / 'remote_launch.py.txt') == receipt['script_sha256']
    prefix = read(OUT / 'first_three/verification.json'); assert prefix['verified']
    assert prefix['native_replayed_transitions'] == prefix['independent_decimal_transitions'] == 36
    for p, h in prefix['hashes'].items(): assert sha(p) == h
    health = read(OUT / 'health_response.json')
    assert all(not any(name.startswith('failure_') for name in r) and 'stopped.json' not in r for r in health['studies'].values())
    start = datetime.fromtimestamp(launch['start_ns']/1e9, timezone.utc).isoformat()
    end = datetime.fromtimestamp(launch['end_exclusive_ns']/1e9, timezone.utc).isoformat()
    fills = sum(row['fills'] for v in prefix['workers'].values() for row in v['checks'])
    lines = ['# Poloniex prospective research replacement launched', '',
        'A separate public recorder and two v2 paper workers are running. The original September 24 archives, accounts, failures and protocols remain intact. No live trading strategy or real order changed.', '',
        'The original paper workers both exited after an unavailable held TRX quote. Their native engines had completed protective cycles, but the old wrapper rejected that outcome before publishing its receipt. The public recorder later stopped on a detected wall-clock discontinuity. SSH connectivity subsequently recovered; the stopped processes were confirmed by a read-only check.', '',
        f'The new interval starts **{start}** and ends **{end}**, covering 10,080 one-minute source slots. Both paper workers started before index zero, from matching flat 495-USDT accounts. Each compares control and quote-aware selection at 30/40/60-bps fees; one has the common stop guard and one is unguarded. This retains all twelve fee/selection/guard combinations.', '',
        'The native binaries and strategies are unchanged. The new worker uses the previously tested completed-cycle fix, preserving unavailable valuations and protective actions on missing-held-quote or latched-risk outcomes. The earlier five outcome tests, twelve inherited worker checks and 30-transition synthetic publication fixture remain authenticated. Eleven unchanged recorder tests passed before this launch. An initial packaging attempt ran 33 passing recorder/verifier tests but stopped on an incorrect expected-count assertion; that attempt and source are retained.', '',
        f'The fixed first-three-batch audit checked **{prefix["public_requests"]} public response records**, all source/protocol identities, availability clocks and receipt chains. It reproduced all **36 native account transitions** and independently checked the same **36 Decimal cash/quantity/fee/valuation transitions**. Those batches contained **{fills} modeled fills**. These initial checks establish launch and replay correctness only; they do not complete the seven-day comparison or qualify profitability.', '',
        'At the subsequent captured health observation, the collector and both workers had processed six source batches without a gap or failure. This is point-in-time evidence, not a guarantee of future uptime. The original Binance paper study was not restarted or altered.', '',
        'The recorder still stops on clock discontinuity, rate limits and resource bounds. The paper workers retain all missing slots and unavailable marks. No automatic restart, historical backfill, account reset, private API request or credential transfer was introduced. Paper IOC execution remains an observed-book assumption, and actual compute times remain separate from logical source-availability times.', '',
        'The full comparison remains pending until its fixed end. It must report all twelve paths, missing data, fees, turnover, open holdings and available marked drawdown. Seven days cannot establish the owner’s rolling-28-day risk limit or long-run alpha; no deployment eligibility is claimed.', '',
        f'Protocol: [2026-09-27-prospective-replacement-protocol.md](2026-09-27-prospective-replacement-protocol.md). Local evidence: `{OUT}`.', '',
        'Remote research roots:', '']
    lines += ['- `'+r['root']+'`' for r in launch['launches']]
    with REPORT.open('x') as stream: stream.write('\n'.join(lines)+'\n')
    bound = {**package['hashes'], **prefix['hashes']}
    for p in [REPORT, *HERE.glob('*.py')]: bound[str(p)] = sha(p)
    for dirname in ('poloniex_remote_incident_20260927_v1',):
        for p in (BASE / dirname).iterdir():
            if p.is_file(): bound[str(p)] = sha(p)
    artifacts = {str(p):sha(p) for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    result = dict(verified=True, at_ns=time.time_ns(), hashes=bound, artifacts=artifacts,
                  scope='New launch and fixed first-three-batch audit; seven-day comparison still running',
                  future_comparison_complete=False, external_orders=False, live_trading_changed=False,
                  source_start_ns=launch['start_ns'], source_end_exclusive_ns=launch['end_exclusive_ns'])
    with (OUT / 'completion.json').open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print('REPLACEMENT_LAUNCH_SEALED', len(bound), len(artifacts), sha(OUT / 'completion.json'), flush=True)


if __name__ == '__main__': main()
