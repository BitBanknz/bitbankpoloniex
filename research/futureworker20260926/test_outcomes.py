from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[0]/'futurecompare20260926'))
from reference import transition
from audit import BINARIES
from native import Native
from replay_v2 import synthetic,config
from outcomes import completed_cycle,ns,RISK

class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.now,self.responses=synthetic();self.now+=123456789
        self.drivers={label:Native(pair[0]) for label,pair in BINARIES.items()}
    def tearDown(self):
        for driver in self.drivers.values():driver.close()
    def apply(self,label,before,responses,now=None):
        return self.drivers[label].apply(dict(ID='outcome-fixture',NowNS=self.now if now is None else now,Config=config(False,'.003'),Before=before,Responses=responses))
    def initialize(self,label):
        return self.apply(label,None,{**self.responses,'/prediction':dict(Status=503,Body={})},self.now-60_000_000_000)['State']
    def verify(self,label,before,answer,responses,now=None):
        now=self.now if now is None else now
        outcome=completed_cycle(before,answer,responses,now)
        money=transition(before,answer['State'],'.003',responses,now,label=='guarded')
        return outcome,money
    def test_normal_and_no_signal(self):
        for label in self.drivers:
            for available in (True,False):
                responses=self.responses if available else {**self.responses,'/prediction':dict(Status=503,Body={})}
                answer=self.apply(label,None,responses);outcome,_=self.verify(label,None,answer,responses)
                self.assertEqual(outcome['kind'],'ready' if available else 'entries_paused')
                self.assertEqual(ns(answer['State']['LastCycle']),self.now)
    def test_missing_held_book_preserves_stop_and_next_cycle(self):
        for label in self.drivers:
            before=self.initialize(label);before['Cash']='400';before['Day']='2026-09-23'
            before['Holdings']={
                'AAA_USDT':dict(Imported=False,Quantity='1',Peak='10',Entered='2026-09-23T00:00:00Z'),
                'DDD_USDT':dict(Imported=False,Quantity='2',Peak='12',Entered='2026-09-23T00:00:00Z')}
            responses=deepcopy(self.responses);responses['/markets/AAA_USDT/orderBook']=dict(Status=503,Body={})
            answer=self.apply(label,before,responses);outcome,money=self.verify(label,before,answer,responses)
            self.assertEqual(outcome['kind'],'incomplete_valuation');self.assertEqual(outcome['unavailable_held_symbols'],['AAA_USDT'])
            self.assertIsNone(money['equity']);self.assertTrue(answer['State']['DayStartPending'])
            self.assertEqual([(f['Order']['symbol'],f['Order']['side']) for f in money['new_fills']],[('DDD_USDT','SELL')])
            later=self.now+60_000_000_000;fresh=deepcopy(self.responses)
            for name,response in fresh.items():
                if name.endswith('/orderBook'):response['Body']['ts']=later//1_000_000
            after=self.apply(label,answer['State'],fresh,later);next_outcome,next_money=self.verify(label,answer['State'],after,fresh,later)
            self.assertEqual(next_outcome['kind'],'ready');self.assertIsNotNone(next_money['equity'])
            self.assertFalse(after['State'].get('DayStartPending',False))
    def test_risk_halt_remains_latched_with_protective_sales(self):
        for label in self.drivers:
            before=self.initialize(label);before['Cash']='400';before['HighWater']='700'
            before['Holdings']['DDD_USDT']=dict(Imported=False,Quantity='2',Peak='12',Entered='2026-09-23T00:00:00Z')
            answer=self.apply(label,before,self.responses);outcome,money=self.verify(label,before,answer,self.responses)
            self.assertEqual(outcome['kind'],'risk_halt');self.assertEqual(answer['State']['Halted'],RISK)
            self.assertEqual([f['Order']['side'] for f in money['new_fills']],['SELL'])
            later=self.now+60_000_000_000
            next_answer=self.apply(label,answer['State'],self.responses,later)
            next_outcome,next_money=self.verify(label,answer['State'],next_answer,self.responses,later)
            self.assertEqual(next_outcome['kind'],'risk_halt');self.assertEqual(next_money['new_fills'],[])
    def test_incomplete_and_unexpected_errors_are_rejected(self):
        before=self.initialize('guarded');responses={**self.responses,'/markets':dict(Status=503,Body={})}
        failed=self.apply('guarded',before,responses)
        with self.assertRaises(AssertionError):completed_cycle(before,failed,responses,self.now)
        ready=self.apply('guarded',None,self.responses)
        for change in [lambda a:a.update(CycleError='unexpected failure'),lambda a:a.update(Paused=True),
                       lambda a:a['State'].update(LastCycle=before['LastCycle']),lambda a:a['State'].update(Halted='operator stop'),
                       lambda a:a.update(CycleError='held books unavailable (INVENTED_USDT); entries paused; protective stops checked')]:
            broken=deepcopy(ready);change(broken)
            with self.assertRaises(AssertionError):completed_cycle(None,broken,self.responses,self.now)
        with self.assertRaises(AssertionError):completed_cycle(None,ready,self.responses,self.now+1)
    def test_protective_only_buy_is_rejected(self):
        before=self.initialize('guarded');before['Cash']='400';before['HighWater']='700'
        before['Holdings']['DDD_USDT']=dict(Imported=False,Quantity='2',Peak='12',Entered='2026-09-23T00:00:00Z')
        answer=self.apply('guarded',before,self.responses)
        self.assertEqual(completed_cycle(before,answer,self.responses,self.now)['kind'],'risk_halt')
        answer['State']['Fills'][-1]['Order']['side']='BUY'
        with self.assertRaises(AssertionError):completed_cycle(before,answer,self.responses,self.now)

if __name__=='__main__':unittest.main()
