import copy
import unittest
from continuity import verify

def state():
    return dict(AccountBacked=True,Schema='poloniex-bot-v1',Mode='live',Budget='489.1312417736',
        Pending=None,LastCycle='2026-09-28T11:00:00Z',Fills=[dict(id='old')],
        Processed={'old-decision':True},Cooldown={'OLD':'2026-09-29T01:00:00Z'},
        HighWater='505',Halted='',Day='2026-09-28',OrdersToday=4,DayStart='499',Cash='233',
        Holdings={'ETH_USDT':dict(Imported=False,Quantity='.03',Entered='2026-09-25T01:00:00Z',Peak='2700')},
        Equity=[dict(At='2026-09-28T10:00:00Z',Value='498'),dict(At='2026-09-28T11:00:00Z',Value='499')])

class Continuity(unittest.TestCase):
    def test_completed_cycle_with_updated_current_mark(self):
        before=state();after=copy.deepcopy(before);after['LastCycle']='2026-09-28T11:01:00Z'
        after['Equity'][-1]['Value']='500';after['Holdings']['ETH_USDT']['Peak']='2710'
        self.assertEqual(verify(before,after)['added_fills'],0)

    def test_new_fill_prefix_is_retained(self):
        before=state();after=copy.deepcopy(before);after['LastCycle']='2026-09-28T11:01:00Z'
        after['Fills'].append(dict(id='new'));after['OrdersToday']+=1
        self.assertEqual(verify(before,after)['added_fills'],1)

    def test_reset_budget_fill_history_decisions_and_pending_rejected(self):
        for key,value in [('Budget','495'),('Fills',[]),('Processed',{}),('Pending',{'order':'unresolved'}),
                          ('HighWater','490'),('OrdersToday',0),('Cash','495'),('Holdings',{})]:
            with self.subTest(key=key):
                before=state();after=copy.deepcopy(before);after['LastCycle']='2026-09-28T11:01:00Z';after[key]=value
                with self.assertRaises(AssertionError):verify(before,after)

    def test_closed_marks_and_cooldown_cannot_change(self):
        for kind in ('mark','cooldown'):
            before=state();after=copy.deepcopy(before);after['LastCycle']='2026-09-28T11:01:00Z'
            if kind=='mark':after['Equity'][0]['Value']='1000'
            else:after['Cooldown']['OLD']='2026-09-28T01:00:00Z'
            with self.assertRaises(AssertionError):verify(before,after)

if __name__=='__main__':unittest.main()
