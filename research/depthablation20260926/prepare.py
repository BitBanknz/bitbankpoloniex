"""Authenticate the fixed control and verify both adapter paths before replay."""
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from bookmodel import transform
from common import HERE, OUT, PARENT, REPO, SOURCE, Native, causal, daily_budget, parent_hash, read, save, sha, transition


def main():
    OUT.mkdir(exist_ok=False)
    parent = read(PARENT / 'completion.json')
    assert parent['verified'] and parent['observed_native_cycles'] == 28980
    # Bind the entire earlier study before consuming its fixed accounts.
    for key in ('artifact_hashes', 'upstream_hash_checks'):
        for path, digest in parent[key].items():
            assert sha(path) == digest, path
    dependencies = [REPO / 'research/quoteaware20260924/native.py',
                    REPO / 'research/quoteaware20260924/receipt_rules.py',
                    REPO / 'research/futurecompare20260926/reference.py',
                    REPO / 'research/exitreserve20260926/checks_v2.py',
                    REPO / 'research/exitreserve20260926/build.py',
                    REPO / 'research/futureworker20260926/outcomes.py',
                    PARENT / 'completion.json', PARENT / 'observed/engine.test',
                    PARENT / 'observed/engine_race.test', PARENT / 'observed_accounts/verification.json',
                    PARENT / 'observed_accounts/paths.jsonl', PARENT / 'observed_accounts/summary.json',
                    PARENT / 'observed_accounts/final_states.json', PARENT / 'regressions_v3/cycles.jsonl.gz',
                    SOURCE / 'capture.verified.json', SOURCE / 'mirror/manifest.json',
                    REPO / 'docs/2026-09-26-depth-ablation-protocol.md']
    dependencies += sorted(p for p in HERE.iterdir() if p.is_file())
    hashes = {str(path): sha(path) for path in dependencies}
    save(OUT / 'registration.json', dict(at_ns=time.time_ns(), hashes=hashes,
        parent_completion_sha256=sha(PARENT / 'completion.json'), first_index=78, through_index=3297,
        fee_bps=[30, 40, 60], policies=['baseline', 'cap9', 'reserve3'], diagnostic_only=True))
    for label, argv in (
        ('adapter_tests', [sys.executable, str(HERE / 'test_bookmodel.py')]),
        ('focused_lint', ['/home/lee/.pyenv/shims/ruff', 'check', '--select', 'E9,F63,F7,F82', str(HERE)]),
    ):
        result = subprocess.run(argv, cwd=HERE, capture_output=True, text=True)
        save(OUT / (label + '.json'), dict(argv=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        assert result.returncode == 0, (label, result.stderr, result.stdout)
    parent_hash(PARENT / 'regressions_v3/cycles.jsonl.gz')
    records = [json.loads(line) for line in gzip.open(PARENT / 'regressions_v3/cycles.jsonl.gz', 'rt')]
    assert len(records) == 256
    temp = Path(tempfile.mkdtemp(prefix='depth-ablation-checks-', dir='/dev/shm'))
    old_tmp = os.environ.get('TMPDIR')
    os.environ['TMPDIR'] = str(temp)
    native, race = Native(PARENT / 'observed/engine.test'), Native(PARENT / 'observed/engine_race.test')
    count = 0
    try:
        with gzip.open(OUT / 'regressions.jsonl.gz', 'wt') as stream:
            for i, row in enumerate(records):
                for mode in ('identity', 'ample'):
                    request = deepcopy(row['input'])
                    request['Responses'], changes = transform(request['Responses'], request['NowNS'], mode)
                    causal(request['Before'], request['NowNS'])
                    answer = native.apply(request)
                    causal(answer['State'], request['NowNS'])
                    accounting = transition(request['Before'], answer['State'], request['Config']['FeeRate'], request['Responses'], request['NowNS'], True)
                    budget = daily_budget(request['Before'], answer['State'], request['Config'], request['NowNS'])
                    if mode == 'identity':
                        assert request == row['input']
                        for key in ('ID', 'State', 'Report', 'Paused', 'CycleError'):
                            assert answer[key] == row['output'][key], (i, key)
                        assert sorted(answer['Paths']) == sorted(row['output']['Paths'])
                    else:
                        repeated = race.apply(request)
                        for key in ('ID', 'State', 'Report', 'Paused', 'CycleError'):
                            assert repeated[key] == answer[key], (i, key)
                        assert sorted(repeated['Paths']) == sorted(answer['Paths'])
                    stream.write(json.dumps(dict(fixture=i, mode=mode, changes=changes, input=request,
                        output=answer, accounting=accounting, budget=budget), sort_keys=True) + '\n')
                    count += 1
    finally:
        native.close()
        race.close()
        if old_tmp is None:
            os.environ.pop('TMPDIR', None)
        else:
            os.environ['TMPDIR'] = old_tmp
        shutil.rmtree(temp)
    assert count == 512 and all(sha(path) == digest for path, digest in hashes.items())
    save(OUT / 'preflight.json', dict(verified=True, at_ns=time.time_ns(), native_accounting_cases=512,
        identity_full_output_cases=256, abundant_depth_race_cases=256, native_source_changed=False,
        registration_sha256=sha(OUT / 'registration.json'), regressions_sha256=sha(OUT / 'regressions.jsonl.gz')))
    print('DEPTH_ABLATION_PREFLIGHT', count, flush=True)


if __name__ == '__main__':
    main()
