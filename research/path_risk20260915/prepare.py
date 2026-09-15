#!/usr/bin/env python3
"""Freeze public hourly inputs and overlays for paired fallback risk auditing."""
from collections import deque
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path('/vfast/data/trading_research_20260915/poloniex_path_risk')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def main():
    assert not (OUT/'paired_inputs.json').exists()
    paths = sorted((ROOT/'data/archive-hourly').glob('*/candles.csv'))
    sources = {str(p): sha(p) for p in paths}
    for p in [Path(__file__), Path(__file__).with_name('replay_test.go.txt'),
              ROOT/'docs/2026-09-15-fallback-path-risk-prereg.md', ROOT/'internal/bot/model.go']:
        sources[str(p)] = sha(p)
    save(OUT/'paired_inputs.json', sources)
    boundary = int(datetime(2026, 9, 15, tzinfo=timezone.utc).timestamp()*1000)
    panels, excluded = {}, {}
    for path in paths:
        rows = deque(maxlen=3000)
        try:
            with path.open() as file:
                for row in csv.DictReader(file):
                    start = int(datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).timestamp()*1000)
                    if start+3600000 > boundary:
                        continue
                    values = {k.title(): float(row[k]) for k in ('open','high','low','close')}
                    values.update(Start=start, Volume=0.)  # unused by this feature/model family
                    if not all(math.isfinite(v) for v in values.values()):
                        raise ValueError('nonfinite candle')
                    rows.append(values)
            if len(rows) != 3000:
                raise ValueError('fewer than 3000 completed bars')
            if any(r['Open'] <= 0 or r['Close'] <= 0 for r in rows):
                raise ValueError('nonpositive open/close')
            if any(b['Start']-a['Start'] != 3600000 for a,b in zip(rows, list(rows)[1:])):
                raise ValueError('noncontiguous final 3000 hours')
            panels[path.parent.name] = list(rows)
        except (ValueError, KeyError) as error:
            excluded[path.parent.name] = str(error)
    save(OUT/'histories.json', panels)
    save(OUT/'history_receipt.json', dict(as_of_ms=boundary, source_files=len(paths),
        included=list(panels), excluded=excluded, rows_per_history=3000, histories_sha256=sha(OUT/'histories.json')))
    bot_dir = Path(subprocess.check_output(['go','list','-f','{{.Dir}}','./internal/bot'], cwd=ROOT, text=True).strip())
    (OUT/'bot_test.go.before').write_bytes(subprocess.check_output(['git','show','14cf0c6:internal/bot/bot_test.go'],cwd=ROOT))
    (OUT/'empty_test.go.txt').write_text('package bot\n')
    test = Path(__file__).with_name('replay_test.go.txt')
    shutil.copyfile(test, OUT/'replay_test.go.txt')
    replacement = {str(bot_dir/'zz_path_risk_audit_test.go'): str(OUT/'replay_test.go.txt')}
    save(OUT/'corrected_overlay.json', dict(Replace=replacement))
    old = dict(replacement)
    old.update({str(bot_dir/'model.go'):str(OUT/'model.go.before'),
                str(bot_dir/'bot_test.go'):str(OUT/'bot_test.go.before'),
                str(bot_dir/'model_path_risk_test.go'):str(OUT/'empty_test.go.txt')})
    save(OUT/'old_overlay.json', dict(Replace=old))
    assert all(sha(Path(p)) == h for p,h in sources.items())
    print('HISTORIES',len(panels),'EXCLUDED',len(excluded),flush=True)


if __name__ == '__main__':
    main()
