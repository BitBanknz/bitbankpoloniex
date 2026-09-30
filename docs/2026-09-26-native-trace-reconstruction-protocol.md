# Explicit reconstruction of one unattributed localhost request

The first full prefix audit stopped at unguarded source index 2062,
`quote_aware_fee30`: every native financial field matched, but the captured
request trace contained one additional `/` request. Inventory of all 38,880
saved account outputs found exactly this one unrequested path. None of the
engine's allowed public routes is `/`. The old test server records any inbound
public GET before looking up its response, including unrelated callers.

Forty replays (twenty with a reused process and twenty with fresh processes)
matched all financial fields, and none reproduced `/`. A controlled root probe
against a private driver with unchanged engine source reproduces the recorded
trace exactly and changes no financial output. A separate driver candidate uses
a fresh internal request marker per cycle; unmarked root and known-route probes
receive 403 and do not enter its trace. Fifty prior native cases per driver and
six probe cases preserve all financial outputs. The original probe's sender is
unknown; no actor attribution is claimed.

Keep the failed audit and every original file. The replacement auditor retains
all original binary, source, account, fee, cash, quantity, mark and state checks.
Use the same frozen native binaries for every financial cycle. If the recorded
trace differs, permit only the exact inventoried case above, only when every
financial field already matches and the sole difference is the one `/` path.
Run the controlled-probe driver on that exact input and require every financial
field and the complete recorded path multiset to match. Retain both native
answers and the reconstruction receipt. Any other discrepancy remains fatal.
This is not a tolerance change, a retry until returns improve, or a claim that
the original request's sender has been identified.

The replacement may verify the two independent studies concurrently, joining
both before advancing to the next source minute. Give each thread its own copy
of the same Decimal context. Retain the original output row order and the fixed
source cutoff 3297. No frozen study, live process or trading rule changes.
