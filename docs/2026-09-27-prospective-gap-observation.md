# One retained public-data gap in the Poloniex forward study

At source index 97, scheduled **2026-09-26T22:49:15+00:00**, six public API requests failed with temporary DNS resolution errors: market metadata and five order books. The recorder attempted and retained all eleven requests, so its capture-gap counter stayed zero. Both paper consumers correctly rejected the batch because market metadata was unavailable and counted one unusable-data gap each.

The local rank endpoint returned 503 in the surrounding minutes too; those otherwise valid batches were handled as paused entries. The distinguishing failure at index 97 was the unavailable market metadata. This was not an omitted source slot, a worker exception or a silent account restart. Source index 98 again supplied market metadata, and both workers continued.

Read-only snapshots retain source and consumer batches 96, 97 and 98, their protocols, receipt chains and worker source: 46 manifested files. All 33 public responses were decoded and authenticated. Each gap output is an empty proposal list, with no logical decision timestamp or fabricated account mark. Each of the twelve account states supplied to batch 98 equals its recorded state after batch 96 exactly. Native replays and independent Decimal checks verify the 24 neighboring account transitions.

This is a local handoff audit. The pre-batch-96 account states are inherited snapshots; it does not independently replay the entire earlier prefix, fill in the missing minute or validate the completed seven-day comparison. The missing minute remains in each consumer's denominator. Original archives, processes, protocol end dates and account states were unchanged, with no backfill or new orders.

At the health observation on 2026-09-26 23:25 UTC, all three workers were present at 134 batches, with no worker failure files: recorder gaps 0, guarded consumer gaps 1, unguarded consumer gaps 1. These counters measure different failure classes and should not be conflated. The prospective study remains open through 2026-10-03 21:12:15 UTC.

Evidence: `/vfast/data/trading_research_20260924/poloniex_gap_observation_20260927_v1`. See [the ongoing replacement protocol/results](2026-09-27-prospective-replacement-results.md).
