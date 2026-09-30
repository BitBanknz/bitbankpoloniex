"""Adversarial checks for the fixed selection gates and causal divergence claims."""
from copy import deepcopy
from decimal import Decimal as D
import unittest

from assessment import first_difference, gates, summarize


def accounts():
    rows = []
    for value in (1, 2, 3):
        row = {"arms": {}, "risk": {}}
        for arm in ("baseline", "cap9", "reserve3"):
            row["arms"][arm] = {
                "return_pct": str(value + (arm == "reserve3")),
                "fills": value,
                "fees": "0.1",
            }
            row["risk"][arm] = {
                "full_drawdown_pct": "9" if arm == "reserve3" else "10",
                "rolling_28d_drawdown_pct": "8",
            }
        rows.append(row)
    return rows


def fill(index, side="BUY", day="2026-09-24"):
    return {"At": f"{day}T01:{index:02d}:00Z", "Order": {"side": side, "symbol": "AAA_USDT"},
            "Quantity": "1"}


class ScreenTests(unittest.TestCase):
    def test_positive_controls_and_gate_denominators(self):
        for days, count in ((0, 13), (28, 17), (56, 17)):
            checks = gates(accounts(), days)
            self.assertEqual(len(checks), count)
            self.assertTrue(all(checks.values()))

    def test_tied_mean_cannot_advance(self):
        rows = accounts()
        for row in rows:
            row["arms"]["cap9"] = deepcopy(row["arms"]["reserve3"])
        self.assertFalse(gates(rows, 0)["cap9:higher_mean"])

    def test_positive_mean_is_separate_from_beating_controls(self):
        rows = accounts()
        for row in rows:
            for arm in row["arms"]:
                row["arms"][arm]["return_pct"] = "-1" if arm == "reserve3" else "-2"
        checks = gates(rows, 0)
        self.assertTrue(checks["baseline:higher_mean"])
        self.assertTrue(checks["cap9:higher_mean"])
        self.assertFalse(checks["positive_mean"])

    def test_tail_loss_vetoes_larger_average(self):
        rows = accounts()
        for row, value in zip(rows, (0, 2, 10), strict=True):
            row["arms"]["reserve3"]["return_pct"] = str(value)
        checks = gates(rows, 28)
        self.assertTrue(checks["baseline:higher_mean"])
        self.assertFalse(checks["baseline:worst_return_pct_nonregression"])
        self.assertFalse(checks["baseline:p10_return_pct_nonregression"])
        self.assertFalse(checks["baseline:two_improving_windows"])
        self.assertFalse(checks["baseline:gain_concentration_at_most_80pct"])

    def test_concentration_boundary_is_inclusive(self):
        rows = accounts()[:2]
        for row, gain in zip(rows, (1, 4), strict=True):
            row["arms"]["reserve3"]["return_pct"] = str(D(row["arms"]["baseline"]["return_pct"]) + gain)
        self.assertTrue(gates(rows, 28)["baseline:gain_concentration_at_most_80pct"])
        rows[1]["arms"]["reserve3"]["return_pct"] = "6.000000000000000001"
        self.assertFalse(gates(rows, 28)["baseline:gain_concentration_at_most_80pct"])

    def test_risk_boundaries_are_inclusive_and_separate(self):
        rows = accounts()
        rows[0]["risk"]["reserve3"] = {"full_drawdown_pct": "40", "rolling_28d_drawdown_pct": "35"}
        checks = gates(rows, 0)
        self.assertTrue(checks["sampled_rolling_28d_dd_at_most_35"])
        self.assertTrue(checks["sampled_full_dd_at_most_40"])
        self.assertFalse(checks["baseline:max_dd_nonregression"])
        rows[0]["risk"]["reserve3"] = {"full_drawdown_pct": "40.000000000000000001", "rolling_28d_drawdown_pct": "35.000000000000000001"}
        checks = gates(rows, 0)
        self.assertFalse(checks["sampled_rolling_28d_dd_at_most_35"])
        self.assertFalse(checks["sampled_full_dd_at_most_40"])

    def test_summary_uses_worst_account_and_exact_fees(self):
        rows = accounts()
        rows[1]["risk"]["reserve3"]["full_drawdown_pct"] = "20"
        summary = summarize(rows, "reserve3")
        self.assertEqual(D(summary["maximum_drawdown_pct"]), D(20))
        self.assertEqual(D(summary["fees"]), D("0.3"))
        self.assertEqual(summary["fills"], 6)

    def test_first_reserved_sale_after_nine_shared_orders(self):
        common = [fill(i) for i in range(9)]
        result = first_difference({"Fills": common}, {"Fills": [*common, fill(10, "SELL")]}, "cap9")
        self.assertEqual((result["common_fills"], result["orders_before"], result["side"]), (9, 9, "SELL"))

    def test_first_skipped_baseline_buy_after_nine_shared_orders(self):
        common = [fill(i) for i in range(9)]
        result = first_difference({"Fills": [*common, fill(10)]}, {"Fills": [*common, fill(11, "SELL")]}, "baseline")
        self.assertEqual((result["orders_before"], result["side"]), (9, "BUY"))

    def test_divergence_rejects_wrong_side_count_day_or_order(self):
        common = [fill(i) for i in range(9)]
        for a, b in (
            (common, [*common, fill(10)]),
            (common[:8], [*common[:8], fill(10, "SELL")]),
            (common, [*common, fill(10, "SELL", "2026-09-25")]),
            ([*common, fill(10)], [*common, fill(10, "SELL")]),
            ([*common, fill(9)], [*common, fill(10, "SELL")]),
        ):
            with self.assertRaises(AssertionError):
                first_difference({"Fills": a}, {"Fills": b}, "cap9")

    def test_equal_fills_require_complete_state_equality(self):
        a = {"Fills": [fill(0)], "Cash": "100"}
        self.assertTrue(first_difference(a, deepcopy(a), "cap9")["equal"])
        with self.assertRaises(AssertionError):
            first_difference(a, {**a, "Cash": "99"}, "cap9")


if __name__ == "__main__":
    unittest.main()
