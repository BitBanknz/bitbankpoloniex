import unittest
import numpy as np
import pandas as pd
from evaluate import simulate,weights

class SimulationTests(unittest.TestCase):
    def data(self,n=30):
        return {k:pd.DataFrame(np.full((n,2),100.)) for k in ['open','low','high']}
    def test_cash_never_borrows_for_fees(self):
        d=self.data();w=np.zeros((30,2));w[:,0]=1
        r,m=simulate(w,d,0,20)
        self.assertEqual(m['borrow_cost_initial_equity'],0)
        self.assertLess(m['return'],0)
        self.assertGreater(m['return'],-.01)
    def test_existing_eth_keeps_collateral_and_charges_overlay_debt(self):
        d=self.data();w=np.zeros((30,2));w[:,0]=1;w[:,1]=.25
        r,m=simulate(w,d,0,20,eth=0,initial_eth=True)
        self.assertGreater(m['borrow_cost_initial_equity'],0)
        self.assertLess(m['return'],0)
    def test_missing_held_price_fails(self):
        d=self.data();d['open'].iloc[8,0]=np.nan;w=np.zeros((30,2));w[:,0]=.5
        with self.assertRaises(ValueError):simulate(w,d,0,20)
    def test_liquidation_is_terminal(self):
        d=self.data();d['low'].iloc[3,:]=1.;w=np.ones((30,2));w[:]*=.625
        r,m=simulate(w,d,0,20)
        self.assertEqual(m['liquidations'],1)
        self.assertEqual(len(r),19)
        self.assertTrue(np.all(r[3:]==0))
    def test_future_prices_do_not_change_prior_returns(self):
        d=self.data();w=np.zeros((30,2));w[:,0]=.5;r,_=simulate(w,d,0,20)
        for k in d:d[k].iloc[15:,:]*=2
        changed,_=simulate(w,d,0,20)
        np.testing.assert_equal(r[:12],changed[:12])
if __name__=='__main__':unittest.main()
