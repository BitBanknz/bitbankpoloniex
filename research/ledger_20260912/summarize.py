#!/usr/bin/env python3
"""Evaluate the fixed standalone-ledger progression gates only when complete."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('results', type=Path)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--days', type=int, nargs='+', default=[0,28])
a = p.parse_args()
rows = [json.loads(line) for line in a.results.read_text().splitlines()]
fixture = json.loads(a.fixture.read_text())
hours = fixture['Hours']
expected = {}
for days in a.days:
    bars = days * 24 if days else len(hours)
    expected[days] = [(hours[start]['TS'], hours[min(start+bars, len(hours))-1]['TS'])
                      for start in range(0, len(hours), bars)
                      if min(start+bars, len(hours))-start >= 168]
groups = {}
for row in rows:
    variant = bool(row['DustMode']) if 'DustMode' in row else row['Bonus'] == .4
    key = (row['Days'], row['Fee'], variant)
    groups.setdefault(key, []).append(row)

comparisons, missing = [], []
for days in a.days:
    for fee in [.003, .006]:
        summaries = []
        for variant in [False, True]:
            group = sorted(groups.get((days, fee, variant), []), key=lambda r: r['Start'])
            if [(r['Start'], r['End']) for r in group] != expected[days]:
                missing.append(dict(days=days, fee=fee, variant=variant,
                                    observed=len(group), expected=len(expected[days])))
                summaries.append(None)
                continue
            returns = [r['Report']['ReturnPct'] for r in group]
            summaries.append(dict(mean_return_pct=statistics.mean(returns),
                                  worst_return_pct=min(returns),
                                  maximum_dd_pct=max(r['Report']['MaxDrawdownPct'] for r in group),
                                  fills=sum(r['Report']['Fills'] for r in group),
                                  returns=returns,
                                  drawdowns=[r['Report']['MaxDrawdownPct'] for r in group]))
        if any(s is None for s in summaries):
            continue
        base, candidate = summaries
        gate = dict(mean_improved=candidate['mean_return_pct'] > base['mean_return_pct'] + 1e-10,
                    worst_nonregressing=candidate['worst_return_pct'] >= base['worst_return_pct'] - 1e-10,
                    dd_nonregressing=candidate['maximum_dd_pct'] <= base['maximum_dd_pct'] + 1e-10)
        comparisons.append(dict(days=days, fee=fee, baseline=base, candidate=candidate,
                                gates=gate, passed=all(gate.values())))
report = dict(status='INCOMPLETE' if missing else 'COMPLETE',
              qualifies_for_further_research=not missing and all(r['passed'] for r in comparisons),
              live_promotion=False, comparisons=comparisons, missing=missing,
              fixture_sha256=hashlib.sha256(a.fixture.read_bytes()).hexdigest(),
              results_sha256=hashlib.sha256(a.results.read_bytes()).hexdigest(),
              limitations=fixture['limitations'])
target = a.results.with_name('comparison.json')
target.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['status', 'qualifies_for_further_research', 'missing']}, indent=2))
