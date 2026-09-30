"""Corruption and complete-matrix checks for the independent research audit."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from account_reference_v2 import Check,verify
from audit import summarize
from build import ROOT


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old=Path('/tmp/claude-1000/topup0924')
        cls.state=json.loads((old/'ledger_fee0.003_bonus0.json').read_text())
        cls.row=next(r for r in map(json.loads,(old/'results.jsonl').read_text().splitlines()) if r['Days']==0 and r['Fee']==.003 and r['SlotTopUp']==0)
        cls.case=dict(fee=.003,variant=0,cooldown=72,cycles=12)
        cls.fixture=json.loads((ROOT/'data/frontier_20260912/ledger/fixture.json').read_text())
        cls.markets=json.loads((ROOT/'data/frontier_20260912/ledger/markets.json').read_text())

    def run_reference(self,state):return verify(state,self.row,self.case,self.fixture,self.markets,Check())
    def test_original_passes(self):self.assertTrue(self.run_reference(self.state)['verified'])
    def test_wrong_fee_rejected(self):
        s=deepcopy(self.state);s['Fills'][0]['Fee']='0'
        with self.assertRaises(AssertionError):self.run_reference(s)
    def test_wrong_price_rejected(self):
        s=deepcopy(self.state);s['Fills'][0]['Order']['price']='1'
        with self.assertRaises(AssertionError):self.run_reference(s)
    def test_missing_mark_rejected(self):
        s=deepcopy(self.state);s['Equity'].pop(5)
        with self.assertRaises(AssertionError):self.run_reference(s)
    def test_changed_fill_clock_rejected(self):
        s=deepcopy(self.state);s['Fills'][0]['At']='2026-01-14T01:00:46Z'
        with self.assertRaises(AssertionError):self.run_reference(s)
    def test_wrong_final_holding_rejected(self):
        s=deepcopy(self.state);s['Holdings'][next(iter(s['Holdings']))]['Quantity']='999'
        with self.assertRaises(AssertionError):self.run_reference(s)


class GateTests(unittest.TestCase):
    def cases(self):
        results=[]
        for days in (0,28,56):
            for fee in (.003,.004,.006):
                for variant in (0,1,2):
                    r=dict(return_pct='2' if variant==2 else '1',max_drawdown_pct='1',initial_budget_drawdown_pct='1',fills=1,topups=0,fees='.1',same_cycle_sell_then_topup=0,halted=False,dust=[])
                    results.append(dict(case=dict(days=days,fee=fee,variant=variant),accounts=[dict(r) for _ in range({0:1,28:9,56:5}[days])]))
        return results
    def test_complete_dominating_candidate(self):self.assertTrue(summarize(self.cases())['research_screen_passed'])
    def test_missing_expensive_cell_rejected(self):
        with self.assertRaises(AssertionError):summarize(self.cases()[:-1])
    def test_high_cost_regression_fails(self):
        c=self.cases();next(x for x in c if x['case']==dict(days=0,fee=.006,variant=2))['accounts'][0]['return_pct']='.5'
        self.assertFalse(summarize(c)['research_screen_passed'])
    def test_tail_regression_fails_despite_higher_mean(self):
        c=self.cases();next(x for x in c if x['case']==dict(days=28,fee=.003,variant=2))['accounts'][0]['return_pct']='-1'
        self.assertFalse(summarize(c)['research_screen_passed'])


if __name__=='__main__':unittest.main()
