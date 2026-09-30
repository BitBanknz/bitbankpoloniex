"""Package a qualified binary and rollback; never contact or change a service."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

from build import OUT, REPO, sha, save, read


RUNBOOK = r'''# Stop/top-up guard: owner activation package

This package has not been activated. Activating the live service can place
real-money orders and is an owner action. Paper studies remain separate.

Candidate: `bin/bitbankpoloniex-guard`
SHA-256: `4cc9122477f3e5c6e030ecf5df4aaf73ceb4bf31c3747208944c737f99d44805`

Rollback: `bin/bitbankpoloniex-rollback`
SHA-256: `eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec`

Read `RESULTS.md` for all outcomes and limitations. The candidate skips a buy
when the held symbol is currently below its protective stop. It leaves the
existing capped sell and once-per-decision-hour sell behavior unchanged.

## Review and integrity

From this extracted directory run `sha256sum -c SHA256SUMS`. This only checks
files. `guard.patch` is the complete release change. `source/` contains every
Go source/test and module file bound by release validation. Qualification
receipts and test logs are in `evidence/`; full historical inputs remain at
the paths identified by those receipts on the research host.

The exact release base is commit `1ef4429233f550598bd96fdac64aff792f5ec009`.
Its Go 1.25.0 build reproduced the running rollback binary byte-for-byte. The
candidate build uses `CGO_ENABLED=0 GOAMD64=v1`, `GOWORK=off`,
`GOFLAGS=-mod=readonly`, and `go build -buildvcs=true -trimpath` from that Git
checkout with `guard.patch` applied. Building the source snapshot without
the original Git metadata produces a different VCS stamp and binary hash.
Do not rebuild from the stale source directory on the trading server.

## Owner deployment procedure

Host: `administrator@93.127.141.100`
Working directory: `/nvme0n1-disk/code/bitbank-poloniex`
Service: `bitbankpoloniex-live.service`
Installed binary: `bin/bitbankpoloniex`
State: `data/live/state.json`

1. Transfer this complete package into a **new inactive directory** on the
   server, and run `sha256sum -c SHA256SUMS` there. Do not replace the installed
   executable during transfer. Confirm both the installed binary and the
   running process's `/proc/<MainPID>/exe` still match the rollback hash above.
   If either differs, this package's deployment baseline is no longer current.
2. Review the existing unit and process arguments. The qualified configuration
   is live mode, state `data/live`, budget argument 495, max order 49, slots 3,
   cooldown 120 hours, cash reserve 0.4, peak halt 0.25, daily halt 0.08, with
   slot top-up enabled. Preserve all unit settings and credentials. The saved
   account budget is not necessarily the command-line budget; do not reset it.
3. Check for a pending intent, then stop this service. Confirm it is inactive
   and check the persisted pending intent again. If a pending order exists,
   reconcile it before changing binaries. Make a timestamped backup of the
   stopped service's complete `data/live` directory and old executable. Keep
   that snapshot for forensics; do not restore it over newer trading state.
4. Copy the verified candidate to a temporary sibling of the installed binary,
   preserve the installed owner and mode, check its hash again, then rename it
   atomically over `bin/bitbankpoloniex`. Start the existing service with its
   existing unit. Do not delete state, fills, models, halt status or cooldowns.
5. Confirm active/running status, then hash `/proc/<MainPID>/exe` to verify the
   mapped binary is the candidate. Check the next cycle, pending-order status,
   balances and ledger continuity, and inspect logs for startup/reconciliation
   errors. Retain the actual activation timestamp, before/after binary hashes,
   unit identity and state-backup path as a deployment receipt.

## Rollback

Stop the same service; inspect/reconcile any pending order. Preserve its current
state and another forensic snapshot. Install the verified rollback binary
atomically with the same owner/mode, start the existing unit, and verify the
mapped executable has the rollback hash. **Keep the latest ledger and account
state.** Reverting executable code does not reverse fills; restoring the old
state snapshot could cause incorrect quantities or duplicate decisions.

The public recorder and both paper study processes use separate binaries and
directories; this procedure does not require restarting or resetting them.
'''


def main():
    release = OUT / 'release_candidate'
    validation = read(release / 'validation.json')
    parity = read(release / 'parity/verification.json')
    independent = read(OUT / 'independent_verification.json')
    future = read(OUT / 'guarded_future_first_two_audit/verification.json')
    baseline = read(OUT / 'release_source_rebuild/verification.json')
    assert validation['verified'] and baseline['byte_identical_to_live']
    assert parity['all_complete_ledgers_and_reports_byte_identical']
    assert parity['historical_accounts'] == independent['accounts'] == 45
    assert independent['verified'] and independent['below_stop_buys_after'] == 0
    assert future['verified'] and future['unguarded_reference_flat_at_common_start']
    package = OUT / 'release_package'
    package.mkdir(exist_ok=False)

    def copy(source, name):
        destination = package / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert sha(destination) == sha(source)

    copy(release / 'bitbankpoloniex', 'bin/bitbankpoloniex-guard')
    copy(OUT / 'release_source_rebuild/bitbankpoloniex', 'bin/bitbankpoloniex-rollback')
    assert sha(package/'bin/bitbankpoloniex-guard') == validation['binary_sha256']
    assert sha(package/'bin/bitbankpoloniex-rollback') == validation['baseline_binary_sha256']
    for p in (package / 'bin').iterdir():
        p.chmod(0o755)
    copy(release / 'guard.patch', 'guard.patch')
    copy(REPO / 'docs/2026-09-24-stop-topup-guard-results.md', 'RESULTS.md')
    (package / 'README.md').write_text(RUNBOOK)
    for name, expected in validation['sources'].items():
        assert sha(release / 'source' / name) == expected
        copy(release / 'source' / name, 'source/' + name)
    for relative in [
        'independent_verification.json',
        'release_source_rebuild/verification.json',
        'release_source_rebuild/inputs.json',
        'release_candidate/validation.json',
        'release_candidate/registration.json',
        'release_candidate/parity/verification.json',
        'release_candidate/parity/inputs.json',
        'guarded_future_first_two_audit/verification.json',
        'guarded_future_launch/protocol.json',
        'guarded_future_launch/validation.json',
    ]:
        copy(OUT / relative, 'evidence/' + relative)
    for name in ['suite', 'race', 'vet']:
        for suffix in ['json', 'log']:
            copy(release / (name + '.' + suffix), 'evidence/tests/' + name + '.' + suffix)
    for script in ['build.py', 'release.py', 'release_compare.py', 'audit.py',
                   'account_reference.py', 'audit_guarded_future.py', 'package_release.py']:
        copy(Path(__file__).parent / script, 'evidence/research/' + script)

    manifest = dict(created_at_ns=time.time_ns(), live_changed=False,
                    candidate_sha256=validation['binary_sha256'],
                    rollback_sha256=validation['baseline_binary_sha256'],
                    revision=read(release/'registration.json')['revision'],
                    files={str(p.relative_to(package)): sha(p)
                           for p in sorted(package.rglob('*')) if p.is_file()})
    save(package/'manifest.json', manifest)
    checks = {str(p.relative_to(package)): sha(p)
              for p in sorted(package.rglob('*')) if p.is_file()}
    (package/'SHA256SUMS').write_text(''.join(h+'  '+name+'\n' for name,h in checks.items()))
    checked = subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=package,
                             capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    (OUT/'package_checksum_check.log').write_text(checked.stdout)
    archive = OUT/'poloniex-stop-topup-guard-20260924.tar.gz'
    with archive.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w|') as tar:
        for p in sorted(package.rglob('*')):
            if not p.is_file():
                continue
            data = p.read_bytes()
            info = tarfile.TarInfo('release_package/' + str(p.relative_to(package)))
            info.size = len(data)
            info.mode = 0o755 if p.parent.name == 'bin' else 0o644
            tar.addfile(info, io.BytesIO(data))
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        expected = {str(p.relative_to(package)):sha(p) for p in package.rglob('*') if p.is_file()}
        assert len(members) == len(expected)
        for item in members:
            assert item.isfile()
            name = item.name.removeprefix('release_package/')
            assert name in expected
            assert hashlib.sha256(tar.extractfile(item).read()).hexdigest() == expected[name]
    report = dict(verified=True, at_ns=time.time_ns(), live_changed=False,
                  archive=str(archive), archive_sha256=sha(archive),
                  archive_bytes=archive.stat().st_size, payload_files=len(members),
                  manifest_sha256=sha(package/'manifest.json'),
                  checksum_file_sha256=sha(package/'SHA256SUMS'),
                  candidate_sha256=validation['binary_sha256'],
                  rollback_sha256=validation['baseline_binary_sha256'],
                  builder_sha256=sha(__file__))
    save(OUT/'packaging_verification.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
