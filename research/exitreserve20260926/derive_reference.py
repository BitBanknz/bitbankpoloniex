"""Pin the inherited account oracle and add only explicit order-budget assertions."""
from build import BASE,HERE,REPO,read,save,sha


def main():
    source=REPO/'research/protectiveclock20260926/account_reference.py'
    proof=read(BASE/'poloniex_protective_clock_v1/completion.json')
    # The previous completion binds this source directly or through upstream hashes.
    maps=[v for v in proof.values() if isinstance(v,dict)]
    assert any(mapping.get(str(source))==sha(source) for mapping in maps)
    changes=[
        ('require_stop_guard=False, actual_stop_hour=False):',
         'require_stop_guard=False, actual_stop_hour=False, max_orders_day=12, exit_order_reserve=0):'),
        ("    assert state['Schema']=='poloniex-bot-v1'", "    assert 0<=exit_order_reserve<=max_orders_day\n    assert state['Schema']=='poloniex-bot-v1'"),
        ('                assert daily_orders<12 and amount<=MAX_ORDER',
         "                assert daily_orders<max_orders_day,('total_order_budget',daily_orders,max_orders_day)\n                assert amount<=MAX_ORDER"),
        ("                if side=='BUY':\n                    if held",
         "                if side=='BUY':\n                    assert daily_orders<max_orders_day-exit_order_reserve,('buy_order_budget',daily_orders,max_orders_day,exit_order_reserve)\n                    if held")]
    text=source.read_text()
    for old,new in changes:
        assert text.count(old)==1,old
        text=text.replace(old,new)
    target=HERE/'account_reference.py'
    with target.open('x') as file:file.write(text)
    save(HERE/'reference_derivation.json',dict(source=str(source),source_sha256=sha(source),
        target=str(target),target_sha256=sha(target),replacements=changes))


if __name__=='__main__':main()
