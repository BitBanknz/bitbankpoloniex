"""Fixed distribution gates, sampled calendar drawdown and first-divergence proofs."""
from collections import deque
from decimal import Decimal as D
from checks_v2 import ns,DAY


def drawdowns(points,initial=D(495)):
    if not points or any(b[0]<=a[0] for a,b in zip(points,points[1:])):
        raise ValueError('strictly increasing marks required')
    if not initial.is_finite() or initial<=0 or any(not value.is_finite() or value<=0 for _,value in points):
        raise ValueError('positive finite values required')
    # Funded starting cash is an explicit initial point at the first mark time.
    sequence=[(points[0][0],initial),*points]
    peaks=deque();high=initial;full=D(0);rolling=D(0)
    for at,value in sequence:
        high=max(high,value);full=max(full,(high-value)/high*100)
        while peaks and peaks[0][0]<at-28*DAY:peaks.popleft()
        while peaks and peaks[-1][1]<=value:peaks.pop()
        peaks.append((at,value))
        rolling=max(rolling,(peaks[0][1]-value)/peaks[0][1]*100)
    return dict(full_drawdown_pct=str(full),rolling_28d_drawdown_pct=str(rolling))


def quantile(values,p):
    ordered=sorted(values);position=D(len(ordered)-1)*p;index=int(position)
    if index==len(ordered)-1:return ordered[index]
    return ordered[index]+(ordered[index+1]-ordered[index])*(position-index)


def summarize(accounts,arm):
    returns=[D(row['arms'][arm]['return_pct']) for row in accounts]
    return dict(mean_return_pct=str(sum(returns)/len(returns)),median_return_pct=str(quantile(returns,D('.5'))),
                p10_return_pct=str(quantile(returns,D('.1'))),worst_return_pct=str(min(returns)),
                maximum_drawdown_pct=str(max(D(row['risk'][arm]['full_drawdown_pct']) for row in accounts)),
                maximum_rolling_28d_drawdown_pct=str(max(D(row['risk'][arm]['rolling_28d_drawdown_pct']) for row in accounts)),
                fills=sum(row['arms'][arm]['fills'] for row in accounts),fees=str(sum(D(row['arms'][arm]['fees']) for row in accounts)))


def gates(accounts,days):
    candidate=summarize(accounts,'reserve3');result={}
    result['positive_mean']=D(candidate['mean_return_pct'])>0
    result['sampled_rolling_28d_dd_at_most_35']=D(candidate['maximum_rolling_28d_drawdown_pct'])<=35
    result['sampled_full_dd_at_most_40']=D(candidate['maximum_drawdown_pct'])<=40
    for arm in ('baseline','cap9'):
        control=summarize(accounts,arm)
        result[arm+':higher_mean']=D(candidate['mean_return_pct'])>D(control['mean_return_pct'])
        for name in ('median_return_pct','p10_return_pct','worst_return_pct'):
            result[arm+':'+name+'_nonregression']=D(candidate[name])>=D(control[name])
        result[arm+':max_dd_nonregression']=D(candidate['maximum_drawdown_pct'])<=D(control['maximum_drawdown_pct'])
        if days:
            gains=[D(row['arms']['reserve3']['return_pct'])-D(row['arms'][arm]['return_pct']) for row in accounts]
            positive=[x for x in gains if x>0]
            result[arm+':two_improving_windows']=len(positive)>=2
            result[arm+':gain_concentration_at_most_80pct']=bool(positive) and max(positive)<=sum(positive)*D('.8')
    return result


def first_difference(left,right,comparison):
    a,b=left['Fills'] or [],right['Fills'] or []
    offset=0
    while offset<min(len(a),len(b)) and a[offset]==b[offset]:offset+=1
    if offset==len(a)==len(b):
        assert left==right,'equal fill paths produced different native states'
        return dict(equal=True,common_fills=offset)
    if comparison=='cap9':
        assert offset<len(b),'candidate removed an earlier matched-control fill'
        first=b[offset];assert first['Order']['side']=='SELL'
        assert offset==len(a) or ns(first['At'])<ns(a[offset]['At'])
        daily=sum(f['At'][:10]==first['At'][:10] for f in b[:offset])
        assert daily==9,'first reserved sell did not follow exhausted matched allowance'
    elif comparison=='baseline':
        assert offset<len(a),'candidate added an earlier baseline fill'
        first=a[offset];assert first['Order']['side']=='BUY'
        assert offset==len(b) or ns(first['At'])<ns(b[offset]['At'])
        daily=sum(f['At'][:10]==first['At'][:10] for f in a[:offset])
        assert daily==9,'first skipped baseline buy was not at the reserve boundary'
    else:raise ValueError('unknown comparison')
    return dict(equal=False,common_fills=offset,at=first['At'],symbol=first['Order']['symbol'],
                side=first['Order']['side'],quantity=first['Quantity'],orders_before=daily)
