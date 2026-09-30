"""Check the remaining fixtures after finding the corrected clock-seed defect."""
import gzip
import json
from pathlib import Path
import time

from build import OUT, read, save, sha
from clock_fixture_correction import causal, stamp


def main():
    original=OUT/'regressions/cycles.jsonl.gz'
    proof=read(OUT/'regressions/verification.json')
    assert sha(original)==proof['cycles_sha256']
    corrected=OUT/'clock_fixture_correction/cycles.json'
    correction=read(OUT/'clock_fixture_correction/verification.json')
    assert correction['verified'] and sha(corrected)==correction['cycles_sha256']
    rows=[json.loads(line) for line in gzip.decompress(original.read_bytes()).splitlines()]
    retained=[row for row in rows if row['label']!='forecast_clock_change']
    assert len(retained)==228
    retained.extend(read(corrected));assert len(retained)==240
    checked=0
    for row in retained:
        request=row['input'];states=[request['Before'],row['output']['State']]
        for state in states:
            if state is None:continue
            causal({**request,'Before':state})
            times=[stamp(fill['At']) for fill in state['Fills'] or []]
            assert times==sorted(times) and all(value<=request['NowNS'] for value in times)
            checked+=1
    save(OUT/'clock_fixture_correction/all_fixture_clocks.json',dict(verified=True,at_ns=time.time_ns(),
        valid_cases=240,states_checked=checked,prior_cycle_equity_entry_and_fill_clocks_causal=True,
        superseded_invalid_cases=12,hashes={str(p):sha(p) for p in [Path(__file__),original,corrected,
        OUT/'regressions/verification.json',OUT/'clock_fixture_correction/verification.json']}))
    print(json.dumps(dict(verified=True,valid_cases=240,states_checked=checked)),flush=True)


if __name__=='__main__':main()
