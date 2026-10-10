# Live binary provenance and the 2026-10-10 09:06Z SIGKILL

## Provenance (resolved)

Live `bitbankpoloniex-live` runs `bin/bitbankpoloniex` sha256
`6b10fdb6eea0ab795446668dc47b61b08312b88792b4094161b9cf5ce4913eb2` (go1.25.0, `-trimpath`,
`CGO_ENABLED=0`, no VCS stamp). Source is commit `f3aa665` ("Sim/live fidelity"), recorded by
`548034f` on `origin/main`. It was missed because local `main` (69fc1f2) is behind `origin/main`
and carries unrelated uncommitted edits; the prod checkout is not a git tree.

`deploy/release/build-live.sh` rebuilds it byte-identically (verified locally with go1.25.0 and on
prod via `GOTOOLCHAIN=go1.25.0`). Branch `release/live-6b10fdb6` = `548034f` + this record.

```
git worktree add /tmp/live6b10 release/live-6b10fdb6 && /tmp/live6b10/deploy/release/build-live.sh /tmp/bpx && cmp /tmp/bpx bin/bitbankpoloniex
```

`-buildvcs=false` is required when building outside a clean checkout; with VCS stamping the hash differs.

## 09:06:04Z SIGKILL (cause: uid-wide kill, actor not recorded)

- Not OOM: earlyoom reported 47% RAM / 60% swap free each minute through 09:05:55; no kernel
  `oom-kill`, no earlyoom kill line. The live unit peaked at 18 MB.
- Not a watchdog: the unit has no `WatchdogSec`/`RuntimeMaxSec`; journal shows
  `Main process exited, code=killed, status=9/KILL` with no systemd-initiated stop.
- Signature: between 09:06:04.77 and 09:06:07 every process owned by `administrator` (uid 1000)
  died with SIGKILL: 62 systemd units (all `User=administrator`, incl. bitbankgo, all three
  Poloniex traders, mojojojo-runner, papers, bitbank-collector), every supervisord program, and
  all administrator ssh/tmux sessions (`last`: pts/1, pts/3, pts/11 ended 09:06:04-05). Root and
  other-uid processes (cutedsl, earlyoom, supervisord, sshd) survived. This is the pattern of
  `kill(-1, SIGKILL)` run as uid 1000 (or root `pkill -9 -u administrator`).
- The actor is not identifiable: auditd only watches config files and `/tmp` execs; no session
  log (codex/claude, all users) contains a uid-wide kill. Context at the time: memory-pressure
  "critical" from host-monitor, ~70 `agent-job-*` coding-agent scopes/min running as uid 1000
  from `codex-infinity-site`, someone running `sudo fuser -v /dev/nvidia*` and restarting
  text-generator/omniserve at 09:05 (NVIDIA userland 595.99 vs kernel module 595.84 mismatch).
- Recovery: `Restart=on-failure`, `RestartSec=300` restarted live at 09:11:05; the 11:01:57 reboot
  was a manual `sudo systemctl reboot` (kernel 6.8.0-146); live restarted 11:08:12 with the same
  binary/argv. No pending intent existed (IOC-only engine).

Recommendations (not applied, host-wide): run the trader under a dedicated uid so agent or
operator mass-kills of `administrator` cannot reach it; add an audit rule for `kill` with
`a0=-1` (`-a always,exit -F arch=b64 -S kill -F a0=0xffffffffffffffff -k masskill`) to name the
actor next time; consider `RestartSec=60` for faster protective-exit recovery.
