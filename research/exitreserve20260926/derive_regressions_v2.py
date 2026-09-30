"""Correct only the duplicate-cycle fixture's valuation expectation."""
from build import HERE,OUT,read,save,sha


def main():
    source=HERE/'regressions.py';target=HERE/'regressions_v2.py'
    text=source.read_text()
    changes=[("root=OUT/'regressions';root.mkdir(exist_ok=False)","root=OUT/'regressions_v2';root.mkdir(exist_ok=False)"),
        ("                assert duplicate['State']==saved", """                # The second observation can update the hourly equity mark
                # after first-cycle fees, despite emitting no additional order.
                for key in ('Cash','Holdings','Fills','OrdersToday','Processed','Cooldown','Day','Halted','Budget'):
                    assert duplicate['State'][key]==saved[key]
                assert D(duplicate['State']['Equity'][-1]['Value'])==D(dm['equity'])""")]
    for old,new in changes:
        assert text.count(old)==1
        text=text.replace(old,new)
    with target.open('x') as stream:stream.write(text)
    save(HERE/'regression_correction_v2.json',dict(source=str(source),source_sha256=sha(source),
        target=str(target),target_sha256=sha(target),replacements=changes,
        original_cycles_sha256=sha(OUT/'regressions/cycles.jsonl.gz'),
        reason='Repeated no-fill observation updates hourly equity after the preceding sale fees; cash, inventory, fills and order identity remain unchanged.',
        native_code_changed=False,financial_oracle_changed=False,historical_outcomes_inspected=False))


if __name__=='__main__':main()
