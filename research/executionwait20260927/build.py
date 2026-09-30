"""Derive a recovery-only worker; leave both failed studies immutable."""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
OLD = Path('/vfast/data/trading_research_20260924/poloniex_prospective_replacement_20260927_v2/package/worker')


def main():
    target = HERE / 'worker'
    target.mkdir()
    for name in ('native.py', 'receipt_rules.py'):
        shutil.copyfile(OLD / name, target / name)
    for name in ('outcomes.py', 'prefix.py'):
        shutil.copyfile(HERE / name, target / name)
    text = (OLD / 'shadow.py').read_text()
    text = text.replace('from native import Native', 'from native import Native\nfrom prefix import Prefix')
    text = text.replace("p['format']=='poloniex-fixed-future-replay-v2'", "p['format']=='poloniex-captured-recovery-v1'")
    old = "    assert p['registered_at_ns']<p['source_start_ns']+p['first_index']*MINUTE\n    assert time.time_ns()<p['source_start_ns']+p['first_index']*MINUTE,'must launch before first future capture'"
    new = """    assert p['first_index']==0 and p['registered_at_ns']>p['source_start_ns']
    assert p['recovered_observed_data'] is True and p['original_prospective_study_failed'] is True
    assert p['source_end_exclusive_ns']==p['source_start_ns']+10080*MINUTE
    assert time.time_ns()<p['source_end_exclusive_ns'],'source retention period already ended'
    prefix=Prefix(p['original_root'],p['original_protocol_sha256'],p['prefix_last_index'],p['prefix_last_receipt_sha256'])
    original=prefix.protocol
    for key in ('accounts','source_root','source_protocol_sha256','source_start_ns','source_end_exclusive_ns','variant','first_index','last_index'):
        assert p[key]==original[key],('recovery configuration changed',key)
    assert p['files']['observed_cycle.test']==original['files']['observed_cycle.test']"""
    assert old in text
    text = text.replace(old, new)
    old = "            name=f'batch_{index:05d}';input_path=root/(name+'.input.json.gz');output_path=root/(name+'.output.json.gz')"
    new = """            prefix_check=prefix.verify(index,packet,provenance,proposals) if index<=prefix.last else None
            name=f'batch_{index:05d}';input_path=root/(name+'.input.json.gz');output_path=root/(name+'.output.json.gz')"""
    assert old in text
    text = text.replace(old, new)
    old = "                actual_decision_commit_claimed=False,external_orders=False)"
    new = "                actual_decision_commit_claimed=False,external_orders=False,recovered_observed_data=True,original_prefix_check=prefix_check)"
    assert text.count(old) == 1
    text = text.replace(old, new)
    text = text.replace('"""Frozen future-data replay; observed-book paper fills, not submitted orders.',
                        '"""Recovered captured-data replay after a failed consumer; no submitted orders.')
    (target / 'shadow.py').write_text(text)
    print('RECOVERY_WORKER_DERIVED', target, flush=True)


if __name__ == '__main__':
    main()
