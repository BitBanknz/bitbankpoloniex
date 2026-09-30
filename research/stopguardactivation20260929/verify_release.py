"""Reauthenticate the previously qualified guard before authorized activation."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import tarfile
import time

OLD=Path('/vfast/data/trading_research_20260924/poloniex_stop_topup_guard_v1')
OUT=Path('/vfast/data/trading_research_20260929/poloniex_stop_guard_activation_v1')
CANDIDATE='4cc9122477f3e5c6e030ecf5df4aaf73ceb4bf31c3747208944c737f99d44805'
BASELINE='eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')

def main():
    OUT.mkdir(exist_ok=False)
    package=OLD/'release_package'
    packaged=read(OLD/'packaging_verification.json')
    validation=read(OLD/'release_candidate/validation.json')
    independent=read(OLD/'independent_verification.json')
    parity=read(OLD/'release_candidate/parity/verification.json')
    baseline=read(OLD/'release_source_rebuild/verification.json')
    assert all(p['verified'] for p in (packaged,validation,independent,parity))
    assert baseline['byte_identical_to_live'] and baseline['binary_sha256']==BASELINE
    assert packaged['candidate_sha256']==validation['binary_sha256']==parity['live_binary_sha256']==CANDIDATE
    assert packaged['rollback_sha256']==validation['baseline_binary_sha256']==BASELINE
    assert sha(packaged['archive'])==packaged['archive_sha256']
    assert sha(package/'manifest.json')==packaged['manifest_sha256']
    assert sha(package/'SHA256SUMS')==packaged['checksum_file_sha256']
    manifest=read(package/'manifest.json')
    assert manifest['candidate_sha256']==CANDIDATE and manifest['rollback_sha256']==BASELINE
    hashes={str(package/name):digest for name,digest in manifest['files'].items()}
    hashes[str(package/'manifest.json')]=packaged['manifest_sha256']
    hashes[str(package/'SHA256SUMS')]=packaged['checksum_file_sha256']
    for path,digest in hashes.items():assert sha(path)==digest,path
    with tarfile.open(packaged['archive'],'r:gz') as archive:
        seen=set()
        for member in archive:
            assert member.isfile() and member.name.startswith('release_package/')
            name=member.name.removeprefix('release_package/')
            assert name not in seen and '..' not in Path(name).parts
            assert hashlib.sha256(archive.extractfile(member).read()).hexdigest()==hashes[str(package/name)]
            seen.add(name)
        assert len(seen)==packaged['payload_files']==len(hashes)
    assert sha(package/'bin/bitbankpoloniex-guard')==CANDIDATE
    assert sha(package/'bin/bitbankpoloniex-rollback')==BASELINE
    for name,digest in validation['sources'].items():
        assert sha(OLD/'release_candidate/source'/name)==sha(package/'source'/name)==digest
    registration=read(OLD/'release_candidate/registration.json')
    assert registration['changed_files']==['internal/bot/engine.go']
    assert registration['patch_sha256']==sha(package/'guard.patch')
    for path,digest in independent['hashes'].items():assert sha(path)==digest,path
    for path,digest in read(OLD/'run_inputs.json').items():assert sha(path)==digest,path
    assert parity['all_complete_ledgers_and_reports_byte_identical']
    assert parity['historical_accounts']==independent['accounts']==len(parity['proofs'])==45
    assert sha(OLD/'release_candidate/parity/inputs.json')==parity['input_manifest_sha256']
    for path,digest in read(OLD/'release_candidate/parity/inputs.json').items():assert sha(path)==digest,path
    for record in parity['proofs']:
        assert sha(record['actual'])==sha(record['reference'])==record['sha256']
    ledger_count=0
    for path in (OLD/'independent_audit').glob('*.json'):
        for row in read(path)['accounts']:
            for side in ('control','guard'):
                assert sha(row[side+'_path'])==row[side+'_sha256']
            assert not row['guard']['below_stop_buys'];ledger_count+=1
    assert ledger_count==45 and independent['maximum_metric_error']=='0'
    assert independent['below_stop_buys_before']==21 and independent['below_stop_buys_after']==0
    assert independent['all_group_mean_returns_nondecreasing'] and independent['control_violations_rejected_by_guard_reference']
    assert len(independent['groups'])==9
    improved=0
    for group in independent['groups']:
        a=group['control'];b=group['guard']
        assert D(b['mean_return_pct'])>=D(a['mean_return_pct'])
        assert D(b['maximum_drawdown_pct'])<=D(35)
        improved+=D(b['mean_return_pct'])>D(a['mean_return_pct'])
    assert improved==6
    tests={}
    for label in ('suite','race','vet'):
        result=read(OLD/'release_candidate'/(label+'.json'))
        log=OLD/'release_candidate'/(label+'.log')
        assert result['returncode']==0 and sha(log)==result['log_sha256']
        if label!='vet':
            events=[json.loads(line) for line in log.read_text().splitlines() if line.startswith('{')]
            passed=sum(e['Action']=='pass' and bool(e.get('Test')) for e in events)
            assert passed==102 and not any(e['Action'] in ('skip','fail') for e in events)
            tests[label]=passed
        else:tests[label]='passed'
    for p in [Path(__file__),OLD/'packaging_verification.json',OLD/'release_candidate/validation.json',
              OLD/'independent_verification.json',OLD/'release_candidate/parity/verification.json',
              OLD/'release_source_rebuild/verification.json']:
        hashes[str(p)]=sha(p)
    save(OUT/'qualification_verified.json',dict(verified=True,at_ns=time.time_ns(),hashes=hashes,
        candidate_sha256=CANDIDATE,baseline_sha256=BASELINE,archive=packaged['archive'],
        archive_sha256=packaged['archive_sha256'],historical_accounts=45,improved_group_means=improved,
        groups=independent['groups'],comparisons=independent['comparisons'],tests=tests,
        negative_account_comparisons=independent['changed_cases_with_lower_return'],
        below_stop_buys_before=21,below_stop_buys_after=0,historical_reuse=True,
        new_strategy_alpha_claimed=False,live_prerequisites_pending=True,live_changed=False))
    print('QUALIFICATION_REAUTHENTICATED',ledger_count,'accounts',tests,flush=True)

if __name__=='__main__':main()
