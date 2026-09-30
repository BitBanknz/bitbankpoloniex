"""Accept completed native paper cycles; reject unrelated or incomplete errors."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import re

RISK='drawdown or daily loss limit; operator review required'
PAUSED='BitBank unavailable and no accepted fallback; entries paused'

def ns(value):
    m=re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z',value)
    assert m is not None,'invalid UTC cycle clock'
    seconds=int(datetime.strptime(m[1],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
    return seconds*1_000_000_000+int((m[2] or '').ljust(9,'0'))

def book_available(responses,symbol,now):
    response=responses.get('/markets/'+symbol+'/orderBook',{})
    book=response.get('Body',{})
    if response.get('Status')!=200 or not isinstance(book,dict):return False
    try:
        ts=int(book.get('ts',0));bids=book['bids'];asks=book['asks']
        if not (0<ts<=now//1_000_000+5000 and ts>=now//1_000_000-30000) or len(bids)<2 or len(asks)<2:return False
        bid=Decimal(bids[0]);ask=Decimal(asks[0])
        return bid.is_finite() and ask.is_finite() and 0<bid<=ask
    except (KeyError,ValueError,TypeError,InvalidOperation):return False

def completed_cycle(before,answer,responses,now):
    state=answer['State'];error=answer['CycleError'];paused=answer['Paused']
    assert state['Schema']=='poloniex-bot-v1' and state['Mode']=='paper' and state['AccountBacked'] is False
    assert state['Pending'] is None and ns(state['LastCycle'])==now,'native cycle did not complete at logical clock'
    assert before is None or ns(before['LastCycle'])<now,'non-increasing account cycle clock'
    old=(before or {}).get('Fills') or [];fills=state['Fills'] or []
    assert fills[:len(old)]==old,'fill prefix changed'
    missing=sorted(s for s in (before or {}).get('Holdings',{}) if not book_available(responses,s,now))
    new=fills[len(old):];source=state['LastSource'];halted=state['Halted']
    if error=='':
        assert paused is False and not missing and halted=='' and source=='bitbank_rotation'
        kind='ready'
    elif error==PAUSED:
        assert paused is True and not missing and halted=='' and source=='waiting_for_execution_or_validated_fallback'
        kind='entries_paused'
    elif missing and error=='held books unavailable ('+','.join(missing)+'); entries paused; protective stops checked':
        assert paused is False and source=='incomplete_quotes_protective_exits'
        assert halted==((before or {}).get('Halted') or '') and halted in ('',RISK)
        kind='incomplete_valuation'
    elif error=='ledger halted: '+RISK+'; protective stops checked':
        assert paused is False and not missing and source=='risk_halt_protective_exits' and halted==RISK
        kind='risk_halt'
    else:raise AssertionError('unexpected or inconsistent native cycle error: '+error)
    if kind!='ready':
        assert all(f['Order']['side']=='SELL' and f['Order']['symbol'] not in missing for f in new),'entry or unavailable-book fill in protective-only cycle'
    return dict(kind=kind,unavailable_held_symbols=missing,logical_ns=now,completed=True)
