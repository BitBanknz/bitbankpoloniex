from copy import deepcopy
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'futurecompare20260926'))
from audit import BINARIES
from reference import transition
from native import Native
from replay_v2 import synthetic,config
sys.path.insert(0,str(HERE))
from outcomes import completed_cycle,future_execution,ns


class WaitingTests(unittest.TestCase):
    def setUp(self):
        _,self.responses=synthetic();self.execution=ns('2026-09-24T01:00:00Z')
        self.drivers={name:Native(pair[0]) for name,pair in BINARIES.items()}
    def tearDown(self):
        for driver in self.drivers.values():driver.close()
    def apply(self,label,now,before=None,responses=None):
        responses=deepcopy(self.responses if responses is None else responses)
        for path,r in responses.items():
            if path.endswith('/orderBook') or path=='/markets/ticker24h':
                if isinstance(r['Body'],list):
                    for ticker in r['Body']:ticker['ts']=now//1_000_000
                else:r['Body']['ts']=now//1_000_000
        answer=self.drivers[label].apply(dict(ID='execution-wait-fixture',NowNS=now,Config=config(False,'.003'),Before=before,Responses=responses))
        outcome=completed_cycle(before,answer,responses,now)
        money=transition(before,answer['State'],'.003',responses,now,label=='guarded')
        return answer,outcome,money,responses
    def test_native_execution_boundary_and_expiry(self):
        for label in self.drivers:
            before,outcome,money,_=self.apply(label,self.execution-1)
            self.assertEqual(outcome['kind'],'waiting_execution');self.assertEqual(money['new_fills'],[])
            ready,outcome,_,_=self.apply(label,self.execution,before['State']);self.assertEqual(outcome['kind'],'ready')
            later,outcome,_,_=self.apply(label,self.execution+1,ready['State']);self.assertEqual(outcome['kind'],'ready')
            _,outcome,_,_=self.apply(label,self.execution+3600_000_000_000,later['State']);self.assertEqual(outcome['kind'],'entries_paused')
    def test_native_protective_sale_while_waiting(self):
        for label in self.drivers:
            before,_,_,_=self.apply(label,self.execution-120_000_000_000)
            before=before['State'];before['Cash']='475';before['Holdings']['DDD_USDT']=dict(Imported=False,Quantity='2',Peak='12',Entered='2026-09-23T00:00:00Z')
            answer,outcome,money,responses=self.apply(label,self.execution-60_000_000_000,before)
            self.assertEqual(outcome['kind'],'waiting_execution');self.assertEqual([f['Order']['side'] for f in money['new_fills']],['SELL'])
            answer['State']['Fills'][-1]['Order']['side']='BUY'
            with self.assertRaises(AssertionError):completed_cycle(before,answer,responses,self.execution-60_000_000_000)
    def test_malformed_or_inconsistent_wait_is_rejected(self):
        now=self.execution-1;answer,_,_,responses=self.apply('guarded',now)
        for mutation in [lambda r:r['/prediction'].update(Status=503),lambda r:r['/prediction']['Body'].update(available=False),
                         lambda r:r['/prediction']['Body'].update(rank_scores={}),lambda r:r['/prediction']['Body'].update(rank_scores={'AAAUSDT':float('nan')}),
                         lambda r:r['/prediction']['Body'].update(rank_scores={'AAA_USDT':1}),lambda r:r['/prediction']['Body'].update(execution_hour='2026-09-24T02:00:00Z'),
                         lambda r:r['/prediction']['Body'].update(issued_at='2026-09-25T00:00:00Z',execution_hour='2026-09-25T01:00:00Z')]:
            bad=deepcopy(responses);mutation(bad);self.assertFalse(future_execution(bad,now))
            with self.assertRaises(AssertionError):completed_cycle(None,answer,bad,now)
        for mutation in [lambda a:a.update(Paused=True),lambda a:a['State'].update(Halted='operator stop'),lambda a:a['State'].update(LastSource='unknown')]:
            bad=deepcopy(answer);mutation(bad)
            with self.assertRaises(AssertionError):completed_cycle(None,bad,responses,now)
        self.assertFalse(future_execution(responses,self.execution));self.assertFalse(future_execution(responses,ns('2026-09-23T23:59:59Z')))


if __name__=='__main__':unittest.main()
