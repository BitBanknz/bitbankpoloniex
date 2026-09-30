"""Verify exact source ancestry, fixture corrections, and native build evidence."""
import json
from pathlib import Path
import subprocess
import sys
import time

from build import HERE, OUT, PARENT, REPO, read, save, sha


def main():
    folder = OUT / 'source_audit'
    folder.mkdir(exist_ok=False)
    checked = {}

    def check(path, digest):
        assert sha(path) == digest, str(path)
        checked[str(path)] = digest

    for subdir in ('', 'regressions', 'regressions_v2', 'regressions_v3'):
        for path, digest in read(OUT / subdir / 'registration.json')['hashes'].items():
            check(path, digest)
    parent = read(PARENT / 'validation.json')
    current = read(OUT / 'validation.json')
    assert parent['verified'] and current['verified']
    check(PARENT / 'validation.json', current['parent_sha256'])
    for name, digest in parent['sources'].items():
        check(PARENT / 'source' / name, digest)
    for name, digest in current['sources'].items():
        check(OUT / 'source' / name, digest)
    assert set(current['sources']) - set(parent['sources']) == {'internal/bot/exit_reserve_test.go'}
    changed = [name for name, digest in parent['sources'].items() if current['sources'][name] != digest]
    assert changed == ['internal/bot/engine.go'], changed

    for name in ('reference_derivation.json', 'regression_correction_v2.json'):
        proof = read(HERE / name)
        check(proof['source'], proof['source_sha256'])
        check(proof['target'], proof['target_sha256'])
        text = Path(proof['source']).read_text()
        for old, new in proof['replacements']:
            assert text.count(old) == 1
            text = text.replace(old, new)
        assert text == Path(proof['target']).read_text(), name
    correction = read(HERE / 'regression_correction_v3.json')
    for path, digest in correction['hashes'].items():
        check(path, digest)
    for source, target, key in (
        ('checks.py', 'checks_v2.py', 'clock_replacements'),
        ('regressions_v2.py', 'regressions_v3.py', 'runner_replacements'),
    ):
        text = (HERE / source).read_text()
        for old, new in correction[key]:
            assert text.count(old) == 1
            text = text.replace(old, new)
        assert text == (HERE / target).read_text()
    check(OUT / 'regressions/cycles.jsonl.gz', read(HERE / 'regression_correction_v2.json')['original_cycles_sha256'])

    tests = {}
    for label in ('suite', 'race', 'vet', 'observed_build', 'observed_race_build', 'historical_build'):
        proof = read(OUT / (label + '.json'))
        assert proof['returncode'] == 0
        check(OUT / (label + '.log'), proof['log_sha256'])
        if label in ('suite', 'race'):
            events = [json.loads(line) for line in (OUT / (label + '.log')).read_text().splitlines() if line.startswith('{')]
            tests[label] = {action: sum(event.get('Action') == action and 'Test' in event for event in events) for action in ('pass', 'fail', 'skip')}
            assert tests[label] == {'pass': 104, 'fail': 0, 'skip': 0}
    for name in ('observed', 'historical'):
        for path, digest in read(OUT / name / 'verification.json')['hashes'].items():
            check(path, digest)

    # Focused correctness lint; compact legacy research style is not a full Ruff pass.
    commands = {
        'focused_lint': ['/home/lee/.pyenv/shims/ruff', 'check', '--select', 'E9,F63,F7,F82', str(HERE)],
        'selection_tests': [sys.executable, str(HERE / 'test_screen.py')],
    }
    for name, argv in commands.items():
        result = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
        save(folder / (name + '.json'), dict(argv=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        assert result.returncode == 0, (name, result.stderr, result.stdout)
    save(folder / 'verification.json', dict(verified=True, at_ns=time.time_ns(), native_tests=tests,
        changed_parent_sources=changed, new_parent_sources=['internal/bot/exit_reserve_test.go'],
        fixture_corrections_exact=True, financial_formulas_unchanged=True,
        hashes=checked, source_hashes={str(p): sha(p) for p in (Path(__file__), HERE / 'test_screen.py')},
        output_hashes={str(p): sha(p) for p in folder.iterdir() if p.is_file()}))
    print('EXIT_RESERVE_SOURCE_AUDIT', len(checked), flush=True)


if __name__ == '__main__':
    main()
