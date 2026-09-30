"""Native fixtures plus adversarial corruptions for the independent accountant."""
from copy import deepcopy
import unittest
from reference import transition,mark
from audit import BINARIES
from native import Native
from replay_v2 import synthetic,config

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.now,self.responses=synthetic()
        self.natives={label:Native(pair[0]) for label,pair in BINARIES.items()}
    def tearDown(self):
        for native in self.natives.values():native.close()
    def apply(self,label,before=None,responses=None):
        return self.natives[label].apply(dict(ID='fixture',NowNS=self.now,Config=config(False,'.003'),Before=before,Responses=responses or self.responses))['State']
    def initialize(self):
        return self.apply('unguarded',responses={**self.responses,'/prediction':dict(Status=503,Body={})})
    def test_fees_open_positions_and_reject_corruption(self):
        state=self.apply('unguarded');v=transition(None,state,'.003',self.responses,self.now,False)
        self.assertEqual(len(v['new_fills']),3);self.assertNotEqual(v['equity'],state['Cash'])
        for field in ('Cash','Fee','Quantity','price'):
            broken=deepcopy(state)
            if field=='Cash':broken['Cash']='495'
            elif field=='price':broken['Fills'][0]['Order']['price']='9'
            else:broken['Fills'][0][field]='12345'
            with self.subTest(field=field),self.assertRaises(AssertionError):transition(None,broken,'.003',self.responses,self.now,False)
        responses=deepcopy(self.responses);responses['/markets/AAA_USDT/orderBook']['Body']['ts']-=60_000
        equity,missing,_=mark(state,responses,self.now)
        self.assertIsNone(equity);self.assertEqual(missing,['AAA_USDT'])
    def test_dust_is_explicitly_removed(self):
        before=self.initialize();before['Cash']='494.9'
        before['Holdings']['DDD_USDT']=dict(Imported=False,Quantity='.01',Peak='10',Entered='2026-09-23T01:00:00Z')
        responses={**self.responses,'/prediction':dict(Status=503,Body={})}
        after=self.apply('unguarded',before,responses)
        v=transition(before,after,'.003',responses,self.now,False)
        self.assertEqual(len(v['dust']),1);self.assertEqual(v['dust'][0]['value'],'0.10')
        self.assertEqual(v['new_fills'],[]);self.assertEqual(v['equity'],'494.9')
    def test_stop_buy_conflict_detected_and_guarded(self):
        before=self.initialize();before['Cash']='475'
        before['Holdings']['AAA_USDT']=dict(Imported=False,Quantity='2',Peak='12',Entered='2026-09-23T01:00:00Z')
        # A shallow bid permits only a partial protective reduction.
        responses=deepcopy(self.responses);responses['/markets/AAA_USDT/orderBook']['Body']['bids']=['10','1']
        original=self.apply('unguarded',before,responses);guarded=self.apply('guarded',before,responses)
        a=transition(before,original,'.003',responses,self.now,False)
        b=transition(before,guarded,'.003',responses,self.now,True)
        self.assertEqual(len(a['below_stop_buys']),1);self.assertEqual(b['below_stop_buys'],[])
        with self.assertRaises(AssertionError):transition(before,original,'.003',responses,self.now,True)

if __name__=='__main__':unittest.main()
