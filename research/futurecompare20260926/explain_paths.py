"""Explain identical strategy paths using authenticated, observed account states.

This is an outcome diagnostic, not a new strategy or a flat-account replay.
"""
from collections import Counter
from decimal import Decimal as D
import gzip
import json
from pathlib import Path
import time

from capture import OUT, save, sha


def read(path):
    return json.loads(path.read_text())


def main():
    root = OUT / "completed_v2/audit"
    proof = read(root / "verification.json")
    report = read(root / "report.json")
    capture = read(OUT / "capture.verified.json")
    assert proof["verified"] and report["verified"]
    assert sha(root / "verification.json") == report["verification_sha256"]
    assert sha(OUT / "mirror/manifest.json") == capture["manifest_sha256"]
    for name, digest in proof["output_hashes"].items():
        assert sha(root / name) == digest
    manifest = read(OUT / "mirror/manifest.json")

    def packet_file(name):
        path = OUT / "mirror" / name
        assert sha(path) == manifest[name]["sha256"], name
        return json.loads(gzip.decompress(path.read_bytes()))

    diagnostic = read(root / "signal_quote_diagnostic.json")
    assert diagnostic["verified_source_audit_sha256"] == sha(root / "verification.json")
    counters = Counter()
    minute_rows = []
    for row in diagnostic["rows"]:
        index = row["index"]
        wanted = set(row["rank_targets"])
        for study in ("unguarded", "guarded"):
            packet = packet_file(f"{study}/batch_{index:05d}.input.json.gz")["packet"]
            outputs = {
                answer["ID"]: answer
                for answer in packet_file(f"{study}/batch_{index:05d}.output.json.gz")
            }
            for account in packet["Accounts"]:
                before = account["Before"]
                held = set(before.get("Holdings") or {})
                after = outputs[account["ID"]]["State"]
                new = after["Fills"][len(before.get("Fills") or []):]
                counters["forecast_account_cycles"] += 1
                if wanted <= held:
                    counters["all_rank_targets_already_held"] += 1
                else:
                    counters["unheld_rank_targets_present"] += 1
                    assert index == 1384 and not held
                    assert all(row["quote_checks"][s]["quote_feasible"] for s in wanted)
                    assert {f["Order"]["symbol"] for f in new} == wanted
                    assert all(f["Order"]["side"] == "BUY" for f in new)
                counters["new_fill_events"] += len(new)
                minute_rows.append({
                    "index": index, "study": study, "account": account["ID"],
                    "rank_targets": row["rank_targets"], "holdings_before": sorted(held),
                    "orders_before": before["OrdersToday"], "day_before": before["Day"],
                    "orders_after": after["OrdersToday"], "day_after": after["Day"],
                    "new_fills": len(new),
                })

    # A deliberately conservative stop check: the final recorded peak is at
    # least as high as an earlier peak for these continuously held, unsold assets.
    state = read(root / "final_states.json")["unguarded"]["control_fee30"]
    assert all(fill["Order"]["side"] == "BUY" for fill in state["Fills"])
    final_peaks = {symbol: D(holding["Peak"]) for symbol, holding in state["Holdings"].items()}
    minima = {symbol: None for symbol in final_peaks}
    held_observations = 0
    for line in (root / "paths.jsonl").open():
        row = json.loads(line)
        if row["study"] != "unguarded" or row["account"] != "control_fee30" or not row["marks"]:
            continue
        assert set(row["marks"]) == set(final_peaks)
        assert not row["unpriced"]
        held_observations += 1
        for symbol, bid in row["marks"].items():
            ratio = D(bid) / final_peaks[symbol]
            minima[symbol] = ratio if minima[symbol] is None else min(minima[symbol], ratio)
    assert counters["forecast_account_cycles"] == 120 * 12
    assert counters["all_rank_targets_already_held"] == 119 * 12
    assert counters["unheld_rank_targets_present"] == 12
    assert all(value > D("0.90") for value in minima.values())

    inputs = [Path(__file__), root / "verification.json", root / "report.json",
              root / "signal_quote_diagnostic.json", OUT / "mirror/manifest.json"]
    save(root / "path_explanation.json", {
        "verified": True, "at_ns": time.time_ns(), "diagnostic_after_outcomes": True,
        "hashes": {str(path): sha(path) for path in inputs},
        "counts": dict(counters), "forecast_account_minutes": minute_rows,
        "first_entry_index": 1384, "same_three_targets_throughout": True,
        "all_three_first_entry_quotes_feasible": True,
        "held_bid_observations": held_observations,
        "minimum_bid_over_final_peak": {key: str(value) for key, value in minima.items()},
        "protective_stop_cannot_have_triggered_at_captured_bids": True,
        "does_not_test_unobserved_intraminute_prices": True,
        "new_performance_evidence": False, "deployment_qualified": False,
    })
    print(json.dumps({"verified": True, "counts": dict(counters),
                      "minimum_bid_over_final_peak": {k: str(v) for k, v in minima.items()}}))


if __name__ == "__main__":
    main()
