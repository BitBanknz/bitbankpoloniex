"""Export native-account equity paths, merging only exactly equal plotted series."""
from datetime import datetime, timezone
import gzip
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as dates
import matplotlib.pyplot as plt

from common import ARMS, OUT, read, save, sha


def main():
    root = OUT / 'audit'
    proof = read(root / 'verification.json')
    assert proof['verified']
    path = root / 'paired_equity.jsonl.gz'
    assert sha(path) == proof['output_hashes'][str(path)]
    rows = [json.loads(line) for line in gzip.open(path, 'rt')]
    times = [datetime.fromtimestamp(row['now_ns'] / 1e9, timezone.utc) for row in rows]
    figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, sharey=True, constrained_layout=True)
    plotted = []
    for axis, fee in zip(axes, (30, 40, 60), strict=True):
        grouped = {}
        for model in ('observed', 'ample'):
            for arm in ARMS:
                values = tuple(row['equity'][model][str(fee)][arm] for row in rows)
                grouped.setdefault((model, values), []).append(arm)
        for (model, values), arms in grouped.items():
            label = model + ': ' + ' + '.join(arms)
            axis.plot(times, [float(value) if value is not None else float('nan') for value in values],
                      label=label, linewidth=1.35, linestyle='--' if model == 'ample' else '-')
            plotted.append(dict(fee_bps=fee, model=model, arms=arms))
        axis.axhline(495, color='#888888', linewidth=.6, alpha=.7)
        axis.set_title(f'{fee} bps per side', loc='left', fontsize=10)
        axis.set_ylabel('Equity (USDT)')
        axis.grid(alpha=.2)
        axis.legend(loc='lower left', fontsize=8)
    axes[-1].xaxis.set_major_formatter(dates.DateFormatter('%b %d %H:%M', tz=timezone.utc))
    axes[-1].set_xlabel('Observed capture time (UTC)')
    figure.suptitle('Depth-only simulation diagnostic — fixed recorded prices and signals\nReused paper data; ample depth is hypothetical', fontsize=13)
    output = OUT / 'depth_equity.png'
    assert not output.exists()
    figure.savefig(output, dpi=150)
    plt.close(figure)
    save(OUT / 'chart.json', dict(input_sha256=sha(path), output_sha256=sha(output), plotted=plotted,
                                 nanosecond_precision_used_for_audit=True, plot_clock_precision_only='microseconds'))
    print('DEPTH_ABLATION_CHART', str(output), flush=True)


if __name__ == '__main__':
    main()
