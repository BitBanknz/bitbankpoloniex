package bot

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestCovCycleNoLiquidMarkets(t *testing.T) {
	e := engine(t)
	mk := market()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{mk})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: mk.Symbol, Amount: "1", TS: time.Now().UnixMilli()}})
		default:
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	if err := e.Cycle(context.Background()); err == nil || !strings.Contains(err.Error(), "no liquid markets") {
		t.Fatalf("expected no-liquid-markets, got %v", err)
	}
	s, _ := e.read()
	if !s.LastCycle.IsZero() {
		t.Fatal("cycle with no markets must not record progress")
	}
}

func TestCovCycleSettlesPendingPaper(t *testing.T) {
	e := engine(t)
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	o, err := BuildOrder(market(), book(), "BUY", "pending-1", d("25"), d("0"), .003)
	if err != nil {
		t.Fatal(err)
	}
	s.Pending = &Pending{Order: o, Decision: "k", Source: "t", Created: time.Now().UTC()}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	mk := market()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{mk})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: mk.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}})
		case "/markets/ETH_USDT/orderBook":
			json.NewEncoder(w).Encode(book())
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	e.Config.PredictionURL = srv.URL + "/prediction"
	err = e.Cycle(context.Background())
	if err == nil || !strings.Contains(err.Error(), "paused") {
		t.Fatalf("expected paused entries, got %v", err)
	}
	after, _ := e.read()
	if after.Pending != nil {
		t.Fatal("paper pending was not settled")
	}
	if len(after.Fills) != 1 || !after.Holdings["ETH_USDT"].Quantity.IsPositive() {
		t.Fatalf("pending settlement lost ledger effects: %+v", after.Fills)
	}
}

func TestCovCycleStopLossSellsWhilePaused(t *testing.T) {
	e := engine(t)
	s, _ := e.read()
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.01"), Peak: d("4000"), Entered: time.Now().Add(-100 * time.Hour)}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	mk := market()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{mk})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: mk.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}})
		case "/markets/ETH_USDT/orderBook":
			json.NewEncoder(w).Encode(book())
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	e.Config.PredictionURL = srv.URL + "/prediction"
	err := e.Cycle(context.Background())
	if err == nil || !strings.Contains(err.Error(), "paused") {
		t.Fatalf("expected paused error after stop exit, got %v", err)
	}
	after, _ := e.read()
	if len(after.Fills) != 1 || after.Fills[0].Order.Side != "SELL" {
		t.Fatalf("stop exit did not record a SELL fill: %+v", after.Fills)
	}
	if _, held := after.Holdings["ETH_USDT"]; held {
		t.Fatal("full stop exit must clear the position")
	}
	if !after.Cooldown["ETH_USDT"].After(time.Now()) {
		t.Fatal("full exit must set a future cooldown")
	}
}

func TestCovCycleTimedExitViaFallback(t *testing.T) {
	e := engine(t)
	e.Config.Slots = 1
	now := time.Now()
	m1 := acceptedFixture(now)
	m2 := acceptedFixture(now)
	m2.Symbol = "AAA_USDT"
	m2.Hash = m2.checksum()
	if err := Save(filepath.Join(e.Config.StateDir, "models.json"), map[string]Model{"ETH_USDT": m1, "AAA_USDT": m2}); err != nil {
		t.Fatal(err)
	}
	s, _ := e.read()
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.01"), Peak: d("2000"), Entered: now.Add(-100 * time.Hour)}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	bars := candles(500)
	raw := [][]any{}
	for _, b := range bars {
		raw = append(raw, []any{float64(b.Low), float64(b.High), float64(b.Open), float64(b.Close), float64(b.Volume), 0, 0, 0, 0, 0, 0, 0, b.Start, b.Start + 3600000 - 1})
	}
	aaa := market()
	aaa.Symbol = "AAA_USDT"
	aaa.Base = "AAA"
	mk := market()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{mk, aaa})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: mk.Symbol, Amount: "2000000", TS: time.Now().UnixMilli()}, {Symbol: aaa.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}})
		case "/markets/ETH_USDT/orderBook", "/markets/AAA_USDT/orderBook":
			json.NewEncoder(w).Encode(book())
		case "/markets/ETH_USDT/candles", "/markets/AAA_USDT/candles":
			json.NewEncoder(w).Encode(raw)
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	e.Config.PredictionURL = srv.URL + "/prediction"
	if err := e.Cycle(context.Background()); err != nil {
		t.Fatal(err)
	}
	after, _ := e.read()
	if len(after.Fills) != 2 || after.Fills[0].Order.Side != "SELL" || after.Fills[1].Order.Side != "BUY" {
		t.Fatalf("expected timed SELL then rotation BUY, got %+v", after.Fills)
	}
	if _, held := after.Holdings["ETH_USDT"]; held {
		t.Fatal("timed exit must clear the stale position")
	}
	if !after.Holdings["AAA_USDT"].Quantity.IsPositive() {
		t.Fatal("rotation entry must hold the new target")
	}
	if after.LastSource != "go_boosted_fallback" {
		t.Fatalf("wrong source %q", after.LastSource)
	}
}

func TestCovTradeDedupe(t *testing.T) {
	e := engine(t)
	s, _ := e.read()
	hour := time.Now().UTC().Truncate(time.Hour)
	if err := e.trade(context.Background(), &s, market(), book(), "BUY", hour, "t"); err != nil {
		t.Fatal(err)
	}
	if err := e.trade(context.Background(), &s, market(), book(), "BUY", hour, "t"); err != nil {
		t.Fatal(err)
	}
	if s.OrdersToday != 1 || len(s.Fills) != 1 {
		t.Fatalf("duplicate decision key resubmitted: orders=%d fills=%d", s.OrdersToday, len(s.Fills))
	}
}

func TestCovTradeDailyCap(t *testing.T) {
	e := engine(t)
	s, _ := e.read()
	s.OrdersToday = e.Config.MaxOrdersDay
	hour := time.Now().UTC().Truncate(time.Hour)
	if err := e.trade(context.Background(), &s, market(), book(), "BUY", hour, "t"); err != nil {
		t.Fatal(err)
	}
	if s.OrdersToday != e.Config.MaxOrdersDay || len(s.Fills) != 0 {
		t.Fatal("daily order cap must suppress the trade silently")
	}
}

func TestCovTradeStopFile(t *testing.T) {
	e := engine(t)
	s, _ := e.read()
	os.WriteFile(filepath.Join(e.Config.StateDir, "STOP"), []byte("stop"), 0600)
	hour := time.Now().UTC().Truncate(time.Hour)
	err := e.trade(context.Background(), &s, market(), book(), "BUY", hour, "t")
	if err == nil || !strings.Contains(err.Error(), "STOP") {
		t.Fatalf("expected STOP rejection, got %v", err)
	}
	if s.OrdersToday != 0 || len(s.Fills) != 0 {
		t.Fatal("STOP trade must not touch the ledger")
	}
}

func TestCovTradeStaleBookIsNoop(t *testing.T) {
	e := engine(t)
	s, _ := e.read()
	b := book()
	b.TS = 0
	hour := time.Now().UTC().Truncate(time.Hour)
	if err := e.trade(context.Background(), &s, market(), b, "BUY", hour, "t"); err != nil {
		t.Fatalf("stale book must be a silent no-op, got %v", err)
	}
	if s.OrdersToday != 0 || len(s.Fills) != 0 {
		t.Fatal("stale book must not place an order")
	}
}

func TestCovSubmitSellFullExitCooldown(t *testing.T) {
	e := engine(t)
	s, _ := e.read()
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.01"), Peak: d("2000"), Entered: time.Now().Add(-time.Hour)}
	o, err := BuildOrder(market(), book(), "SELL", "sell-all", d("0"), d("0.01"), .003)
	if err != nil {
		t.Fatal(err)
	}
	before := s.Cash
	if err := e.submit(context.Background(), &s, o, "exit-decision", "t"); err != nil {
		t.Fatal(err)
	}
	if s.Pending != nil || !s.Processed["exit-decision"] || len(s.Fills) != 1 {
		t.Fatal("paper submit must record the fill and clear pending")
	}
	if _, held := s.Holdings["ETH_USDT"]; held {
		t.Fatal("selling the full position must clear holdings")
	}
	if !s.Cooldown["ETH_USDT"].After(time.Now()) {
		t.Fatal("full exit must set a future cooldown")
	}
	if !s.Cash.GreaterThan(before) {
		t.Fatal("SELL proceeds must increase cash")
	}
}

func covResolveServer(t *testing.T, lookup OrderResult, lookupCode int, trades []Trade) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/orders/cid:") {
			if lookupCode != 200 {
				w.WriteHeader(lookupCode)
				return
			}
			json.NewEncoder(w).Encode(lookup)
			return
		}
		if strings.HasSuffix(r.URL.Path, "/trades") {
			json.NewEncoder(w).Encode(trades)
			return
		}
		w.WriteHeader(404)
	}))
}

func covPendingOrder() Order {
	return Order{Symbol: "ETH_USDT", Side: "BUY", Price: "2000", Quantity: "0.01", ClientID: "bbp-x", Type: "LIMIT", TimeInForce: "IOC", AccountType: "SPOT"}
}

func TestCovResolveNilPendingNoop(t *testing.T) {
	e := engine(t)
	e.Client.BaseURL = "http://127.0.0.1:1"
	s, _ := e.read()
	if err := e.resolve(context.Background(), &s); err != nil {
		t.Fatalf("nil pending must be a no-op, got %v", err)
	}
}

func TestCovResolveIdentityMismatch(t *testing.T) {
	e := engine(t)
	o := covPendingOrder()
	srv := covResolveServer(t, OrderResult{ID: "o1", ClientID: "other", Symbol: o.Symbol, Side: o.Side, State: "FILLED", FilledQuantity: "0.01", FilledAmount: "20"}, 200, nil)
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	s, _ := e.read()
	s.Pending = &Pending{Order: o}
	if err := e.resolve(context.Background(), &s); err == nil || !strings.Contains(err.Error(), "identity mismatch") {
		t.Fatalf("expected identity mismatch, got %v", err)
	}
	if s.Pending == nil {
		t.Fatal("failed reconciliation must retain pending")
	}
}

func TestCovResolveNonTerminal(t *testing.T) {
	e := engine(t)
	o := covPendingOrder()
	srv := covResolveServer(t, OrderResult{ID: "o1", ClientID: o.ClientID, Symbol: o.Symbol, Side: o.Side, State: "OPEN", FilledQuantity: "0", FilledAmount: "0"}, 200, nil)
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	s, _ := e.read()
	s.Pending = &Pending{Order: o}
	if err := e.resolve(context.Background(), &s); err == nil || !strings.Contains(err.Error(), "not terminal") {
		t.Fatalf("expected non-terminal block, got %v", err)
	}
	if s.Pending == nil {
		t.Fatal("blocked order must stay pending")
	}
}

func TestCovResolveTotalsMismatch(t *testing.T) {
	e := engine(t)
	o := covPendingOrder()
	srv := covResolveServer(t, OrderResult{ID: "order-1", ClientID: o.ClientID, Symbol: o.Symbol, Side: o.Side, State: "FILLED", FilledQuantity: "0.01", FilledAmount: "20"}, 200,
		[]Trade{{ID: "t1", OrderID: "order-1", Symbol: o.Symbol, Side: o.Side, Quantity: "0.005", Amount: "10", FeeCurrency: "USDT", FeeAmount: "0"}})
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	s, _ := e.read()
	s.Pending = &Pending{Order: o}
	if err := e.resolve(context.Background(), &s); err == nil || !strings.Contains(err.Error(), "not yet reconciled") {
		t.Fatalf("expected totals mismatch, got %v", err)
	}
	if s.Pending == nil {
		t.Fatal("unreconciled order must stay pending")
	}
}

func TestCovResolveCanceledZeroFill(t *testing.T) {
	e := engine(t)
	o := covPendingOrder()
	srv := covResolveServer(t, OrderResult{ID: "o1", ClientID: o.ClientID, Symbol: o.Symbol, Side: o.Side, State: "CANCELED", FilledQuantity: "0", FilledAmount: "0"}, 200, nil)
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	s, _ := e.read()
	s.Pending = &Pending{Order: o}
	if err := e.resolve(context.Background(), &s); err != nil {
		t.Fatal(err)
	}
	if s.Pending != nil || len(s.Fills) != 0 {
		t.Fatal("canceled zero fill must clear pending without a fill")
	}
}

func TestCovAccountReadyRejections(t *testing.T) {
	var marginUsed, borrowed, openOrders string
	spots := 1
	borrowedList := func() []Borrow {
		if borrowed == "" {
			return []Borrow{}
		}
		return []Borrow{{Currency: "USDT", Borrowed: borrowed}}
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		enc := json.NewEncoder(w)
		switch {
		case strings.HasSuffix(r.URL.Path, "accountMargin"):
			enc.Encode(Margin{Used: marginUsed, Maintenance: "0", Free: "50", Value: "100"})
		case strings.HasSuffix(r.URL.Path, "borrowStatus"):
			enc.Encode(borrowedList())
		case strings.HasSuffix(r.URL.Path, "orders"):
			if openOrders == "" {
				enc.Encode([]OrderResult{})
			} else {
				enc.Encode([]OrderResult{{Symbol: "ETH_USDT", Side: "BUY", State: openOrders}})
			}
		default:
			accts := []Account{}
			for range spots {
				accts = append(accts, Account{Type: "SPOT", Balances: []Balance{{Currency: "USDT", Available: "100", Hold: "0"}}})
			}
			if spots == 0 {
				accts = []Account{{Type: "MARGIN", Balances: []Balance{{Currency: "USDT", Available: "100", Hold: "0"}}}}
			}
			enc.Encode(accts)
		}
	}))
	defer srv.Close()
	cases := []struct {
		name   string
		setup  func()
		expect string
	}{
		{"margin", func() { marginUsed, borrowed, openOrders, spots = "1", "", "", 1 }, "margin exposure"},
		{"borrowed", func() { marginUsed, borrowed, openOrders, spots = "0", "1", "", 1 }, "borrowed assets"},
		{"open", func() { marginUsed, borrowed, openOrders, spots = "0", "", "OPEN", 1 }, "open exchange orders"},
		{"none", func() { marginUsed, borrowed, openOrders, spots = "0", "", "", 0 }, "exactly one spot"},
		{"two", func() { marginUsed, borrowed, openOrders, spots = "0", "", "", 2 }, "exactly one spot"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			tc.setup()
			e := engine(t)
			e.Client.BaseURL = srv.URL
			err := e.Ready(context.Background())
			if err == nil || !strings.Contains(err.Error(), tc.expect) {
				t.Fatalf("expected %q, got %v", tc.expect, err)
			}
		})
	}
}

func TestCovStoreSaveErrorsAndLockContention(t *testing.T) {
	dir := t.TempDir()
	unlock, err := Lock(dir)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Lock(dir); err == nil || !strings.Contains(err.Error(), "another process") {
		t.Fatalf("second lock must be refused, got %v", err)
	}
	unlock()
	if _, err := Lock(dir); err != nil {
		t.Fatalf("lock must release, got %v", err)
	}
	if err := Save(filepath.Join(dir, "s.json"), make(chan int)); err == nil {
		t.Fatal("unmarshalable value must fail Save")
	}
	blocker := filepath.Join(dir, "file")
	os.WriteFile(blocker, []byte("x"), 0600)
	if err := Save(filepath.Join(blocker, "s.json"), map[string]int{"a": 1}); err == nil {
		t.Fatal("Save through a file path must fail")
	}
}

func covCandleRow(start int64, low, high, open, close string) []any {
	return []any{low, high, open, close, "10", 0, 0, 0, 0, 0, 0, 0, start, start + 3600000 - 1}
}

func TestCovArchiveQuarantineAndResume(t *testing.T) {
	mk := market()
	base := time.Now().UTC().Truncate(time.Hour).Add(-6 * time.Hour).UnixMilli()
	good1 := covCandleRow(base, "99", "101", "100", "100")
	good2 := covCandleRow(base+3600000, "99", "101", "100", "100")
	bad := covCandleRow(base+2*3600000, "99", "101", "100", "999")
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.Contains(r.URL.Path, "candles"):
			calls++
			if calls == 1 {
				json.NewEncoder(w).Encode([][]any{good1, good2, bad})
			} else {
				json.NewEncoder(w).Encode([][]any{})
			}
		case strings.HasSuffix(r.URL.Path, "ticker24h"):
			json.NewEncoder(w).Encode([]Ticker{{Symbol: mk.Symbol, Amount: "200000", TS: time.Now().UnixMilli()}})
		default:
			json.NewEncoder(w).Encode([]Market{mk})
		}
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	root := t.TempDir()
	st, err := c.archiveSymbol(context.Background(), root, "ETH_USDT", "HOUR_1")
	if err != nil {
		t.Fatal(err)
	}
	if st.Quarantined != 1 || !st.Complete || st.Rows != 2 {
		t.Fatalf("bad quarantine accounting: %+v", st)
	}
	if _, err := os.Stat(filepath.Join(root, "ETH_USDT", "candles.csv")); err != nil {
		t.Fatal("CSV output missing")
	}
	resumed, err := c.archiveSymbol(context.Background(), root, "ETH_USDT", "HOUR_1")
	if err != nil {
		t.Fatal(err)
	}
	if !resumed.Complete || resumed.Rows != 2 {
		t.Fatalf("resume must reload recorded pages: %+v", resumed)
	}
	os.WriteFile(filepath.Join(root, "ETH_USDT", "status.json"), []byte("{"), 0600)
	if _, err := c.archiveSymbol(context.Background(), root, "ETH_USDT", "HOUR_1"); err == nil {
		t.Fatal("corrupt status must fail")
	}
}

func TestCovArchiveFailuresAndLock(t *testing.T) {
	mk := market()
	aaa := market()
	aaa.Symbol = "AAA_USDT"
	aaa.Base = "AAA"
	base := time.Now().UTC().Truncate(time.Hour).Add(-6 * time.Hour).UnixMilli()
	rows := [][]any{covCandleRow(base, "99", "101", "100", "100"), covCandleRow(base+3600000, "99", "101", "100", "100")}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.Contains(r.URL.Path, "candles"):
			json.NewEncoder(w).Encode(rows)
		case strings.HasSuffix(r.URL.Path, "ticker24h"):
			now := time.Now().UnixMilli()
			json.NewEncoder(w).Encode([]Ticker{{Symbol: mk.Symbol, Amount: "200000", TS: now}, {Symbol: aaa.Symbol, Amount: "200000", TS: now}})
		default:
			json.NewEncoder(w).Encode([]Market{mk, aaa})
		}
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	root := t.TempDir()
	unlock, err := Lock(root)
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Archive(context.Background(), root, "HOUR_1", 0); err == nil || !strings.Contains(err.Error(), "another process") {
		t.Fatalf("Archive under contention must fail, got %v", err)
	}
	unlock()
	root2 := t.TempDir()
	if err := c.Archive(context.Background(), root2, "HOUR_1", 1); err == nil || !strings.Contains(err.Error(), "archive failures") {
		t.Fatalf("expected archive failures, got %v", err)
	}
	var manifest map[string]ArchiveStatus
	if err := Load(filepath.Join(root2, "manifest.json"), &manifest); err != nil || len(manifest) != 1 {
		t.Fatalf("manifest must record the trimmed universe: %v %+v", err, manifest)
	}
}

func covRawRow(t *testing.T, vals ...any) []json.RawMessage {
	t.Helper()
	out := make([]json.RawMessage, 0, len(vals))
	for _, v := range vals {
		b, err := json.Marshal(v)
		if err != nil {
			t.Fatal(err)
		}
		out = append(out, b)
	}
	return out
}

func TestCovParseArchiveDAY1(t *testing.T) {
	now := time.Now()
	day := now.UTC().Truncate(24 * time.Hour).Add(-48 * time.Hour).UnixMilli()
	short := [][]json.RawMessage{covRawRow(t, "1", "2", "3")}
	if _, err := parseArchive(short, now, 86400000); err == nil || !strings.Contains(err.Error(), "short archive") {
		t.Fatalf("expected short row error, got %v", err)
	}
	clock := [][]json.RawMessage{covRawRow(t, "99", "101", "100", "100", "10", 0, 0, 0, 0, 0, 0, 0, day, day+100)}
	if _, err := parseArchive(clock, now, 86400000); err == nil || !strings.Contains(err.Error(), "daily clock") {
		t.Fatalf("expected daily clock error, got %v", err)
	}
}

func TestCovForecastErrors(t *testing.T) {
	now := time.Now()
	bars := candles(200)
	tampered := acceptedFixture(now)
	tampered.Ensemble.Bias = .5
	if _, err := tampered.Forecast(bars, now); err == nil || !strings.Contains(err.Error(), "absent, expired") {
		t.Fatalf("expected invalid-model error, got %v", err)
	}
	valid := acceptedFixture(now)
	stale := append(append([]Candle{}, bars...), Candle{Start: bars[len(bars)-1].Start + 2*3600000, Open: 100, High: 101, Low: 99, Close: 100, Volume: 1})
	if _, err := valid.Forecast(stale, now); err == nil || !strings.Contains(err.Error(), "clock invalid") {
		t.Fatalf("expected clock error, got %v", err)
	}
	if _, err := valid.Forecast(bars, now); err != nil {
		t.Fatalf("control forecast must succeed, got %v", err)
	}
}

func covDailyRows(t *testing.T, agoDays []int) [][]any {
	t.Helper()
	dayMs := int64(86400000)
	yesterday := time.Now().UTC().Truncate(24 * time.Hour).Add(-24 * time.Hour).UnixMilli()
	rows := [][]any{}
	for _, d := range agoDays {
		start := yesterday - int64(d)*dayMs
		rows = append(rows, []any{"99", "101", "100", "100", "10", 0, 0, 0, 0, 0, 0, 0, start, start + dayMs - 1})
	}
	return rows
}

func TestCovDailyHistoryErrors(t *testing.T) {
	var rows [][]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(rows)
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	ago := []int{}
	for i := range 205 {
		if i != 100 {
			ago = append(ago, i)
		}
	}
	rows = covDailyRows(t, ago)
	if _, err := c.DailyHistory(context.Background(), "ETH_USDT"); err == nil || !strings.Contains(err.Error(), "gap") {
		t.Fatalf("expected daily gap, got %v", err)
	}
	staleAgo := []int{}
	for i := range 205 {
		staleAgo = append(staleAgo, i+2)
	}
	rows = covDailyRows(t, staleAgo)
	if _, err := c.DailyHistory(context.Background(), "ETH_USDT"); err == nil || !strings.Contains(err.Error(), "stale") {
		t.Fatalf("expected stale history, got %v", err)
	}
	rows = [][]any{}
	if _, err := c.DailyHistory(context.Background(), "ETH_USDT"); err == nil || !strings.Contains(err.Error(), "insufficient") {
		t.Fatalf("expected insufficient history, got %v", err)
	}
	c.BaseURL = "http://127.0.0.1:1"
	if _, err := c.DailyHistory(context.Background(), "ETH_USDT"); err == nil {
		t.Fatal("transport failure must fail DailyHistory")
	}
}

func TestCovBuildOrderRejections(t *testing.T) {
	wide := book()
	wide.Asks = []string{"2100", "10"}
	wide.Bids = []string{"2000", "10"}
	if _, err := BuildOrder(market(), wide, "BUY", "id", d("25"), d("0"), .003); err == nil || !strings.Contains(err.Error(), "spread") {
		t.Fatalf("expected spread rejection, got %v", err)
	}
	if _, err := BuildOrder(market(), book(), "HOLD", "id", d("25"), d("0"), .003); err == nil || !strings.Contains(err.Error(), "side") {
		t.Fatalf("expected side rejection, got %v", err)
	}
	strict := market()
	strict.Limits.MinAmount = "1000000"
	if _, err := BuildOrder(strict, book(), "BUY", "id", d("25"), d("0"), .003); err == nil || !strings.Contains(err.Error(), "size limit") {
		t.Fatalf("expected size-limit rejection, got %v", err)
	}
	bogus := book()
	bogus.Asks = []string{"bogus", "10"}
	if _, err := BuildOrder(market(), bogus, "BUY", "id", d("25"), d("0"), .003); err == nil || !strings.Contains(err.Error(), "ask") {
		t.Fatalf("expected invalid-ask rejection, got %v", err)
	}
}

func TestCovClientGuards(t *testing.T) {
	c := NewClient("k", "s")
	if _, err := c.Place(context.Background(), Order{Symbol: "ETH_USDT", Side: "BUY", Type: "LIMIT", TimeInForce: "IOC", AccountType: "SPOT", ClientID: "id", AllowBorrow: true}); err == nil || !strings.Contains(err.Error(), "unsafe order") {
		t.Fatalf("expected unsafe-order guard, got %v", err)
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" {
			json.NewEncoder(w).Encode(OrderResult{ID: "placed-1", ClientID: "id", Symbol: "ETH_USDT", Side: "BUY", State: "OPEN"})
			return
		}
		json.NewEncoder(w).Encode([]Account{})
	}))
	defer srv.Close()
	c.BaseURL = srv.URL
	got, err := c.Place(context.Background(), Order{Symbol: "ETH_USDT", Side: "BUY", Type: "LIMIT", TimeInForce: "IOC", AccountType: "SPOT", Price: "2000", Quantity: "0.01", ClientID: "id"})
	if err != nil || got.ID != "placed-1" {
		t.Fatalf("live place round-trip failed: %v %+v", err, got)
	}
	redir := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/elsewhere", http.StatusFound)
	}))
	defer redir.Close()
	c.BaseURL = redir.URL
	if _, err := c.Balances(context.Background()); err == nil {
		t.Fatal("redirect must be refused")
	}
	if _, err := FetchPrediction(context.Background(), "http://example.com/x"); err == nil || !strings.Contains(err.Error(), "HTTPS") {
		t.Fatalf("expected endpoint-scheme rejection, got %v", err)
	}
}
