"""Bind the completed interim audit and diagnostics without changing old evidence."""
import json
import os
from pathlib import Path
import time

from capture import HERE, OUT, save, sha


def read(path):
    return json.loads(path.read_text())


def main():
    completed = OUT / "completed_v2"
    root = completed / "audit"
    trace = OUT.parent / "poloniex_driver_trace_isolation_v3"
    checked = {}

    def check(path, expected):
        path = Path(path)
        actual = sha(path)
        assert actual == expected, str(path)
        checked[str(path)] = actual

    def check_map(mapping, base=None):
        for name, expected in mapping.items():
            check(Path(name) if base is None else base / name, expected)

    proof = read(root / "verification.json")
    assert proof["verified"] and proof["through_index"] == 3297
    assert sum(proof["native_cycles"].values()) == 38880
    assert sum(proof["baseline_cycles"].values()) == 19440
    check_map(proof["hashes"])
    check_map(proof["output_hashes"], root)
    assert len(proof["trace_reconstructions"]) == 1
    for event in proof["trace_reconstructions"]:
        check(event["file"], event["sha256"])

    capture = read(OUT / "capture.verified.json")
    assert capture["verified"] and capture["transport_version"] == 3
    check(OUT / "capture_v3.tar.zst", capture["archive_sha256"])
    check(OUT / "mirror/manifest.json", capture["manifest_sha256"])
    check(OUT / "mirror/remote_status.json", capture["remote_status_sha256"])
    check(OUT / "capture_v3_registration.json", capture["registration_sha256"])

    coverage = read(OUT / "source_coverage/verification.json")
    assert coverage["verified"] and coverage["cross_batch_receipt_chronology_verified"]
    assert coverage["source_batches"] == 3260 and coverage["unusable_source_batches"] == 0
    check_map(coverage["hashes"])
    check(OUT / "source_coverage/minutes.jsonl", coverage["minutes_sha256"])

    pipeline = read(completed / "pipeline_finished.json")
    assert pipeline["verified"]
    check(HERE / "run_v2.py", pipeline["pipeline_sha256"])

    for filename, code, code_key in (
        ("comparison.json", "summarize.py", "summarizer_sha256"),
        ("signal_quote_diagnostic.json", "diagnose_signals.py", "diagnostic_sha256"),
        ("report.json", "report_results.py", "reporter_sha256"),
    ):
        result = read(root / filename)
        check(HERE / code, result[code_key])
        check(root / "verification.json", result.get("verification_sha256") or result["verified_source_audit_sha256"])
    report = read(root / "report.json")
    assert report["verified"] and report["equal_paired_account_rows"] == 28980
    assert report["all_four_strategy_variants_have_identical_financial_paths_at_each_fee"]
    check_map(report["plot_hashes"], root)
    explanation = read(root / "path_explanation.json")
    assert explanation["verified"] and explanation["counts"]["forecast_account_cycles"] == 1440
    check_map(explanation["hashes"])

    driver = read(trace / "verification.json")
    assert driver["verified"] and driver["source_engine_unchanged"]
    assert driver["all_financial_fields_exact"] and driver["recorded_root_trace_reproduced"]
    check_map(driver["input_hashes"])
    check_map(driver["artifact_hashes"], trace)
    race = read(trace / "race/verification.json")
    assert race["verified"] and race["native_race_cases"] == 100
    assert race["unmarked_probes_rejected"] == 100
    check_map(race["hashes"])
    check(trace / "race/engine.test", race["binary_sha256"])
    fixture = read(trace / "fixture_provenance.json")
    original = OUT.parent / "poloniex_quote_aware_v1/paired_replay_v2"
    check(original / "cycles.jsonl.gz", fixture["fixture_sha256"])
    check(original / "verification.json", fixture["original_fixture_verification_sha256"])

    # Do not recurse into the mirror symlink or duplicate its 25,990-file manifest.
    artifacts = set(HERE.glob("*.py"))
    docs = HERE.parents[1] / "docs"
    for name in ("2026-09-26-future-prefix-comparison-protocol.md",
                 "2026-09-26-native-trace-reconstruction-protocol.md",
                 "2026-09-26-future-prefix-comparison-results.md"):
        artifacts.add(docs / name)
    for folder in (completed, OUT / "audit", OUT / "trace_2062", OUT / "source_coverage", trace):
        for parent, dirs, files in os.walk(folder, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(parent) / name).is_symlink()]
            for name in files:
                path = Path(parent) / name
                if not path.is_symlink():
                    artifacts.add(path)
    artifacts.update(path for path in OUT.iterdir() if path.is_file() and path.suffix in (".json", ".log", ".txt"))
    artifact_hashes = {str(path): sha(path) for path in sorted(artifacts)}
    save(completed / "completion.json", {
        "verified": True, "at_ns": time.time_ns(), "fixed_prefix_complete": True,
        "seven_day_study_complete": False, "through_index": 3297,
        "candidate_native_cycles": 38880, "baseline_native_cycles": 19440,
        "explicit_trace_reconstructions": 1, "equal_paired_account_rows": 28980,
        "profitability_established": False, "deployment_qualified": False,
        "live_changed": False, "ongoing_studies_changed": False,
        "upstream_hash_checks": checked, "artifact_hashes": artifact_hashes,
    })
    print(json.dumps({"verified": True, "upstream_hash_checks": len(checked),
                      "artifacts_bound": len(artifact_hashes), "deployment_qualified": False}))


if __name__ == "__main__":
    main()
