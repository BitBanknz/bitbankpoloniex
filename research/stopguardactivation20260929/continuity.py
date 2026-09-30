"""Check retained live history and account identity across a code-only restart."""
from datetime import datetime
from decimal import Decimal as D

def stamp(value):return datetime.fromisoformat(value.replace('Z','+00:00'))

def verify(before,after):
    for key in ('AccountBacked','Schema','Mode','Budget'):
        assert after[key]==before[key],('account_identity_changed',key)
    assert after['Pending'] is None,'pending intent requires reconciliation'
    assert stamp(after['LastCycle'])>stamp(before['LastCycle'])
    assert after['Fills'][:len(before['Fills'])]==before['Fills'],'historical fills changed'
    assert len(after['Fills'])>=len(before['Fills'])
    for key,value in before['Processed'].items():
        assert after['Processed'].get(key)==value,('processed decision lost',key)
    for key,value in before['Cooldown'].items():
        assert key in after['Cooldown'] and stamp(after['Cooldown'][key])>=stamp(value),('cooldown shortened',key)
    assert D(after['HighWater'])>=D(before['HighWater']),'high-water mark reset'
    if before['Halted']:assert after['Halted']==before['Halted'],'halt cleared'
    if after['Day']==before['Day']:
        assert after['OrdersToday']>=before['OrdersToday'],'daily counter reset'
        if not before.get('DayStartPending',False):assert after['DayStart']==before['DayStart']
    old_equity=before.get('Equity',[]);new_equity=after.get('Equity',[])
    if old_equity:
        assert new_equity
        offset=0
        if new_equity[0]['At']!=old_equity[0]['At']:
            assert len(old_equity)==len(new_equity)==9600,'equity history truncated'
            offset=next(i for i,row in enumerate(old_equity) if row['At']==new_equity[0]['At'])
            assert offset==1,'unexpected history truncation during restart'
        closed=old_equity[offset:-1]
        assert new_equity[:len(closed)]==closed,'closed equity history changed'
        assert stamp(new_equity[-1]['At'])>=stamp(old_equity[-1]['At'])
    added=after['Fills'][len(before['Fills']):]
    if not added:
        assert after['Cash']==before['Cash'],'cash changed without a fill'
        assert set(after['Holdings'])==set(before['Holdings']),'holding set changed without a fill'
        for symbol,position in before['Holdings'].items():
            for key in ('Imported','Quantity','Entered'):
                assert after['Holdings'][symbol][key]==position[key],('holding changed without a fill',symbol,key)
            assert D(after['Holdings'][symbol]['Peak'])>=D(position['Peak'])
    return dict(verified=True,previous_fills=len(before['Fills']),current_fills=len(after['Fills']),
        added_fills=len(added),budget=after['Budget'],pending=None,
        history_preserved=True,last_cycle=after['LastCycle'])
