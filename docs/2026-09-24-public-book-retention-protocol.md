# Prospective Poloniex books and rank publications

Collect source evidence for later fixed-policy comparisons. The preceding
historical sizing experiment is complete; these observations cannot change its
results. This recorder does not place orders, load credentials, read private
account ledgers, train models or publish a trading signal.

Run on the existing IP-allowed remote host. Retain the eight registered symbols
BNB/ETC/ETH/PEPE/SUI/TRX/XRP/ZEC against USDT, matching the frozen replay and the
currently published rank universe. Every minute, beginning at the protocol's
explicit start plus 15 seconds into the minute, request these eleven endpoints:
the local public BitBank rank publication, public exchange market contracts,
24-hour tickers and five-level order books for all eight symbols. Preserve raw
response bytes, request/response wall and monotonic clocks, status, transport
errors, truncation flags and SHA256 hashes. Use GET only; redirects and ambient
proxies are disabled. No authentication headers, cookies or private endpoints.

There are exactly **10,080 scheduled slots over seven days**, no backfill and no
automatic restart. A slot more than 45 seconds late is retained as a gap. Each
request has at most ten seconds and must fit the remaining slot deadline.
Requests are sequential with a half-second spacing. HTTP errors, including the
rank endpoint's normal expiry outside its publication window, remain evidence.
Public rate-limit responses 418/429, clock discontinuity or oversized responses
stop collection. Two MiB per body, 16 MiB per batch, **2 GiB total** and **20 GiB
minimum free disk** bound storage. Source/protocol changes also stop collection.
SIGTERM closes the current partial batch and writes a stopped receipt.

Each raw gzip archive is durable before its receipt is published. Atomic,
exclusive publication prevents replacement of existing evidence. `complete`
means all endpoints were attempted; `all_responses_successful` is separate.
Neither field makes the independently fetched quotes an atomic exchange
snapshot. Response clocks record receipt by the collector; future order
decisions still need their own durable timestamps. Later analysis must use
actual source availability, retain missing data and apply the bot's freshness,
spread, volume, lot and depth checks. It must not carry stale ranks forward.

Validate the first complete capture independently, including raw-byte hashes,
receipt ordering, planned endpoint identity and exact book spread/depth values.
Record actual per-symbol market eligibility and the public rank universe.
Subsequent books and forecast vintages support new prospective tests; seven
days alone cannot qualify a long-horizon strategy or certify real IOC fills.

The operational recorder is separate from the live service and existing paper
units. No live strategy setting or account state changes as part of collection.
