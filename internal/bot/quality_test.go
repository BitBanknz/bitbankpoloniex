package bot

import (
	"context"
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func TestNewClientDefaults(t *testing.T) {
	c := NewClient("k", "s")
	if c.BaseURL != ExchangeURL || c.Key != "k" || c.Secret != "s" {
		t.Fatal(c)
	}
	if c.HTTP == nil {
		t.Fatal("nil http client")
	}
}

func TestRequestValidation(t *testing.T) {
	c := NewClient("", "")
	if err := c.request(context.Background(), "GET", "no-slash", nil, nil, false, &struct{}{}); err == nil {
		t.Fatal("bad path accepted")
	}
	if err := c.request(context.Background(), "GET", "/x?y", nil, nil, false, &struct{}{}); err == nil {
		t.Fatal("query path accepted")
	}
	if err := c.request(context.Background(), "GET", "/x", nil, nil, true, &struct{}{}); err == nil {
		t.Fatal("missing creds accepted")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := c.request(ctx, "GET", "/x", nil, nil, false, &struct{}{}); err == nil {
		t.Fatal("canceled ctx accepted")
	}
}

func qmarkets() []Market {
	mk := func(sym, base, quote, state string) Market {
		return Market{Symbol: sym, Base: base, Quote: quote, State: state, Limits: Limits{PriceScale: 2, QuantityScale: 4, MinQuantity: "0.001", MinAmount: "1", MaxQuantity: "10000", MaxAmount: "1000000"}}
	}
	return []Market{mk("ETH_USDT", "ETH", "USDT", "NORMAL"), mk("BTC_USDT", "BTC", "USDT", "PAUSE"), mk("XRP_BTC", "XRP", "BTC", "NORMAL"), mk("DOGE_USDT", "DOGE", "USDT", "NORMAL"), mk("LTC_USDT", "LTC", "USDT", "NORMAL")}
}

func TestUniverseFiltersAndSort(t *testing.T) {
	now := time.Now().UnixMilli()
	tick := func(sym, amt string, ts int64) Ticker { return Ticker{Symbol: sym, Amount: amt, TS: ts} }
	ts := []Ticker{
		tick("ETH_USDT", "200000", now),
		tick("BTC_USDT", "9999999", now),
		tick("XRP_BTC", "9999999", now),
		tick("DOGE_USDT", "10", now),
		tick("LTC_USDT", "not-a-number", now),
		tick("STALE_USDT", "500000", now-10*60*1000),
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "ticker24h") {
			json.NewEncoder(w).Encode(ts)
			return
		}
		json.NewEncoder(w).Encode(qmarkets())
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	got, err := c.Universe(context.Background(), 100000)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Symbol != "ETH_USDT" {
		t.Fatalf("%v", got)
	}
}

func TestUniverseTieBreak(t *testing.T) {
	now := time.Now().UnixMilli()
	mk := qmarkets()[:1]
	mk = append(mk, Market{Symbol: "AAA_USDT", Base: "AAA", Quote: "USDT", State: "NORMAL", Limits: mk[0].Limits})
	ts := []Ticker{{Symbol: "ETH_USDT", Amount: "200000", TS: now}, {Symbol: "AAA_USDT", Amount: "200000", TS: now}}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "ticker24h") {
			json.NewEncoder(w).Encode(ts)
			return
		}
		json.NewEncoder(w).Encode(mk)
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	got, err := c.Universe(context.Background(), 100000)
	if err != nil || len(got) != 2 || got[0].Symbol != "AAA_USDT" || got[1].Symbol != "ETH_USDT" {
		t.Fatalf("%v %v", got, err)
	}
}

func TestBookRejects(t *testing.T) {
	now := time.Now().UnixMilli()
	good := map[string]any{"asks": []string{"2000.01", "10"}, "bids": []string{"2000", "10"}, "time": now, "ts": now}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(good)
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	if _, err := c.Book(context.Background(), "ETH_USDT"); err != nil {
		t.Fatal(err)
	}
	good["ts"] = now - 60000
	if _, err := c.Book(context.Background(), "ETH_USDT"); err == nil {
		t.Fatal("stale book accepted")
	}
	good["ts"] = now
	good["asks"] = []string{"1999", "10"}
	if _, err := c.Book(context.Background(), "ETH_USDT"); err == nil {
		t.Fatal("crossed book accepted")
	}
	good["asks"] = []string{"NaN", "10"}
	if _, err := c.Book(context.Background(), "ETH_USDT"); err == nil {
		t.Fatal("bad ask accepted")
	}
}

func TestBuildOrderSellAndLimits(t *testing.T) {
	m, b := market(), book()
	o, err := BuildOrder(m, b, "SELL", "id", d("25"), d("1"), .003)
	if err != nil {
		t.Fatal(err)
	}
	if o.Price != "2000" {
		t.Fatal(o.Price)
	}
	if _, err = BuildOrder(m, b, "HOLD", "id", d("25"), d("1"), .003); err == nil {
		t.Fatal("bad side accepted")
	}
	if _, err = BuildOrder(m, b, "BUY", "id", d("0.000001"), decimal.Zero, .003); err == nil {
		t.Fatal("dust accepted")
	}
	m.Limits.MaxQuantity = "0.000001"
	if _, err = BuildOrder(m, b, "BUY", "id", d("25"), decimal.Zero, .003); err == nil {
		t.Fatal("max quantity ignored")
	}
	m = market()
	b.Bids[1] = "0"
	if _, err = BuildOrder(m, b, "SELL", "id", d("25"), d("1"), .003); err == nil {
		t.Fatal("empty depth accepted")
	}
}

func TestParseCandlesRejects(t *testing.T) {
	now := time.Now()
	row := func(vals ...any) []json.RawMessage {
		r := make([]json.RawMessage, len(vals))
		for i, v := range vals {
			b, _ := json.Marshal(v)
			r[i] = b
		}
		return r
	}
	if _, err := parseCandles([][]json.RawMessage{row("1")}, now); err == nil {
		t.Fatal("short row accepted")
	}
	bad := row("99", "101", "100", "100", "10", nil, nil, nil, nil, nil, nil, nil, 123, 456)
	if _, err := parseCandles([][]json.RawMessage{bad}, now); err == nil {
		t.Fatal("bad clock accepted")
	}
	future := time.Now().Add(time.Hour).UnixMilli()
	fStart := future / 3600000 * 3600000
	fut := row("99", "101", "100", "100", "10", nil, nil, nil, nil, nil, nil, nil, fStart, fStart+3599999)
	out, err := parseCandles([][]json.RawMessage{fut}, now)
	if err != nil || len(out) != 0 {
		t.Fatalf("%v %v", out, err)
	}
	lastHour := now.Truncate(time.Hour).Add(-time.Hour).UnixMilli()
	ohlc := row("99", "98", "100", "100", "10", nil, nil, nil, nil, nil, nil, nil, lastHour, lastHour+3599999)
	if _, err := parseCandles([][]json.RawMessage{ohlc}, now); err == nil {
		t.Fatal("bad ohlc accepted")
	}
}

func qrow(start int64) []any {
	return []any{"99", "101", "100", "100", "10", nil, nil, nil, nil, nil, nil, nil, start, start + 3599999}
}

func qhistoryServer(t *testing.T, lastCompleted int64, skip map[int64]bool, count int) *httptest.Server {
	t.Helper()
	rows := [][]any{}
	for i := count - 1; i >= 0; i-- {
		s := lastCompleted - int64(i)*3600000
		if skip[s] {
			continue
		}
		rows = append(rows, qrow(s))
	}
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(rows)
	}))
}

func TestHistoryErrors(t *testing.T) {
	last := time.Now().Truncate(time.Hour).Add(-time.Hour).UnixMilli()
	c := NewClient("", "")
	srv := qhistoryServer(t, last, map[int64]bool{last - 3*3600000: true}, 10)
	c.BaseURL = srv.URL
	srv2 := qhistoryServer(t, last, nil, 3)
	defer srv.Close()
	defer srv2.Close()
	if _, err := c.History(context.Background(), "GAP_USDT", 5); err == nil || !strings.Contains(err.Error(), "gap") {
		t.Fatalf("gap: %v", err)
	}
	c.BaseURL = srv2.URL
	if _, err := c.History(context.Background(), "SHORT_USDT", 5); err == nil {
		t.Fatalf("short accepted")
	}
	srv3 := qhistoryServer(t, last-5*3600000, nil, 5)
	defer srv3.Close()
	c.BaseURL = srv3.URL
	if _, err := c.History(context.Background(), "STALE_USDT", 5); err == nil {
		t.Fatalf("stale accepted")
	}
}

func TestFetchPredictionErrors(t *testing.T) {
	if _, err := FetchPrediction(context.Background(), "ftp://x/y"); err == nil {
		t.Fatal("bad scheme accepted")
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(503)
	}))
	defer srv.Close()
	if _, err := FetchPrediction(context.Background(), srv.URL); err == nil {
		t.Fatal("503 accepted")
	}
	srv2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("not json"))
	}))
	defer srv2.Close()
	if _, err := FetchPrediction(context.Background(), srv2.URL); err == nil {
		t.Fatal("bad json accepted")
	}
	dst := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	defer dst.Close()
	redir := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, dst.URL, http.StatusFound)
	}))
	defer redir.Close()
	if _, err := FetchPrediction(context.Background(), redir.URL); err == nil {
		t.Fatal("redirect accepted")
	}
}

func TestStoreEdges(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "s.json")
	if err := Save(p, map[string]int{"a": 1}); err != nil {
		t.Fatal(err)
	}
	f, _ := os.OpenFile(p, os.O_APPEND|os.O_WRONLY, 0600)
	f.WriteString("{}")
	f.Close()
	var v map[string]int
	if Load(p, &v) == nil {
		t.Fatal("trailing content ignored")
	}
	os.WriteFile(p, []byte(`{"unknown":1}`), 0600)
	var sv struct {
		A int `json:"a"`
	}
	if Load(p, &sv) == nil {
		t.Fatal("unknown field ignored")
	}
	big := filepath.Join(dir, "big.json")
	os.WriteFile(big, []byte("{}"), 0600)
	os.Truncate(big, 17<<20)
	if Load(big, &v) == nil {
		t.Fatal("oversize accepted")
	}
	if _, err := Lock(filepath.Join(dir, "a", "b")); err != nil {
		t.Fatal(err)
	}
}

func TestConfigValidateTable(t *testing.T) {
	cases := []func(*Config){
		func(c *Config) { c.Mode = "demo" },
		func(c *Config) { c.Budget = d("-1") },
		func(c *Config) { c.Slots = 5 },
		func(c *Config) { c.Slots = 0 },
		func(c *Config) { c.MaxOrdersDay = 0 },
		func(c *Config) { c.MaxOrdersDay = 51 },
		func(c *Config) { c.MaxSpread = 0 },
		func(c *Config) { c.MaxSpread = .02 },
		func(c *Config) { c.MinVolume = 1 },
		func(c *Config) { c.FeeRate = d("0.0001") },
		func(c *Config) { c.FeeRate = d("0.05") },
	}
	for i, fn := range cases {
		c := DefaultConfig()
		fn(&c)
		if c.Validate() == nil {
			t.Fatalf("case %d accepted", i)
		}
	}
	if err := DefaultConfig().Validate(); err != nil {
		t.Fatal(err)
	}
}

func TestModelValidEdges(t *testing.T) {
	b := candles(2400)
	m, err := Train("ETH_USDT", b)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	if m.Valid(now.Add(8 * 24 * time.Hour)) {
		t.Fatal("expired accepted")
	}
	bad := m
	bad.Hash = "00"
	if bad.Valid(now) {
		t.Fatal("tampered accepted")
	}
	bad = m
	bad.Schema = "other"
	bad.Hash = bad.checksum()
	if bad.Valid(now) {
		t.Fatal("schema accepted")
	}
	bad = m
	bad.Ensemble.Bias = math.NaN()
	bad.Hash = bad.checksum()
	if bad.Valid(now) {
		t.Fatal("nan bias accepted")
	}
	if len(m.Ensemble.Trees) == 0 {
		t.Skip("no trees to corrupt")
	}
	bad = m
	bad.Ensemble.Trees[0].Feature = 9
	bad.Hash = bad.checksum()
	if bad.Valid(now) {
		t.Fatal("bad tree accepted")
	}
	if _, err := m.Forecast(b[:100], now); err == nil {
		t.Fatal("short history accepted")
	}
	stale := append(append([]Candle{}, b...), Candle{Start: b[len(b)-1].Start + 2*3600000, Open: 100, High: 101, Low: 99, Close: 100, Volume: 1})
	if _, err := m.Forecast(stale, now); err == nil {
		t.Fatal("gapped forecast accepted")
	}
	if len(samples(nil)) != 0 || fit(nil).Bias != 0 {
		t.Fatal("empty fit mishandled")
	}
}

func TestPredictBranches(t *testing.T) {
	e := Ensemble{Bias: 1.5}
	if e.Predict(Features{0, 0, 0, 0, 0, 0}) != 1.5 {
		t.Fatal("bias mispredicted")
	}
	e.Trees = []Stump{{Feature: 0, Cut: 0, Left: .1, Right: -.1}}
	if e.Predict(Features{-1, 0, 0, 0, 0, 0}) != 1.6 {
		t.Fatal("left mispredicted")
	}
	if e.Predict(Features{1, 0, 0, 0, 0, 0}) != 1.4 {
		t.Fatal("right mispredicted")
	}
}

func TestTargetsEdges(t *testing.T) {
	m := []Market{market(), {Symbol: "AAA_USDT", Base: "AAA", Quote: "USDT", State: "NORMAL", Limits: market().Limits}}
	got := Targets(map[string]float64{"ETH_USDT": 1, "AAA_USDT": 1}, m, 4)
	if len(got) != 2 || got[0] != "AAA_USDT" {
		t.Fatal(got)
	}
	got = Targets(map[string]float64{"ETH_USDT": 2, "AAA_USDT": 1}, m, 1)
	if len(got) != 1 || got[0] != "ETH_USDT" {
		t.Fatal(got)
	}
	got = Targets(map[string]float64{"ETH_USDT": math.NaN()}, m, 4)
	if len(got) != 0 {
		t.Fatal(got)
	}
}

func TestCycleGuards(t *testing.T) {
	e := engine(t)
	e.Config.Mode = "demo"
	if err := e.Cycle(context.Background()); err == nil {
		t.Fatal("bad mode cycled")
	}
	e = engine(t)
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	s.Halted = "review"
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	if err := e.Cycle(context.Background()); err == nil || !strings.Contains(err.Error(), "halted") {
		t.Fatalf("%v", err)
	}
}

func TestAccountSummarySkipsZero(t *testing.T) {
	accts := []Account{{Type: "SPOT", Balances: []Balance{
		{Currency: "USDT", Available: "0", Hold: "0"},
		{Currency: "ETH", Available: "1.5", Hold: "0"},
		{Currency: "BAD", Available: "oops", Hold: "0"},
	}}}
	out := AccountSummary(accts)
	if len(out) != 1 || out[0]["currency"] != "ETH" {
		t.Fatal(out)
	}
}

func TestTrainFallbackUniverseError(t *testing.T) {
	e := engine(t)
	e.Client.BaseURL = "http://127.0.0.1:1"
	if err := e.TrainFallback(context.Background(), 1); err == nil {
		t.Fatal("universe error ignored")
	}
}

func TestTrainFallbackWritesReports(t *testing.T) {
	last := time.Now().Truncate(time.Hour).Add(-time.Hour).UnixMilli()
	rows := [][]any{}
	for i := 2999; i >= 0; i-- {
		s := last - int64(i)*3600000
		rows = append(rows, qrow(s))
	}
	mk := market()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		switch {
		case strings.HasSuffix(p, "ticker24h"):
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "200000", TS: time.Now().UnixMilli()}})
		case strings.HasSuffix(p, "candles"):
			cutoff, _ := strconv.ParseInt(r.URL.Query().Get("endTime"), 10, 64)
			out := [][]any{}
			for _, row := range rows {
				if row[12].(int64) <= cutoff {
					out = append(out, row)
				}
				if len(out) >= 3000 {
					break
				}
			}
			if len(out) > 500 {
				out = out[len(out)-500:]
			}
			json.NewEncoder(w).Encode(out)
		default:
			json.NewEncoder(w).Encode([]Market{mk})
		}
	}))
	defer srv.Close()
	e := engine(t)
	e.Client.BaseURL = srv.URL
	if err := e.TrainFallback(context.Background(), 1); err != nil {
		t.Fatal(err)
	}
	for _, f := range []string{"validation.json", "models.json"} {
		if _, err := os.Stat(filepath.Join(e.Config.StateDir, f)); err != nil {
			t.Fatal(f, err)
		}
	}
}

func TestArchiveRejectsInterval(t *testing.T) {
	c := NewClient("", "")
	if _, err := c.archiveSymbol(context.Background(), t.TempDir(), "ETH_USDT", "MIN_1"); err == nil {
		t.Fatal("bad interval accepted")
	}
}

func qfundingServer() *httptest.Server {
	mk := market()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		enc := json.NewEncoder(w)
		switch {
		case strings.HasSuffix(p, "balances"):
			enc.Encode([]Account{{Type: "SPOT", Balances: []Balance{{Currency: "USDT", Available: "100", Hold: "0"}, {Currency: "ETH", Available: "1", Hold: "0"}}}})
		case strings.HasSuffix(p, "accountMargin"):
			enc.Encode(Margin{Used: "0", Maintenance: "0", Free: "50", Value: "2100"})
		case strings.HasSuffix(p, "borrowStatus"):
			enc.Encode([]Borrow{})
		case strings.HasSuffix(p, "collateralInfo"):
			enc.Encode([]Collateral{{Currency: "USDT", Rate: "1", Initial: "1", Maintenance: "1"}, {Currency: "ETH", Rate: "0.8", Initial: "1", Maintenance: "1"}})
		case strings.HasSuffix(p, "borrowRatesInfo"):
			enc.Encode([]BorrowTier{{Tier: "1", Rates: []BorrowRate{{Currency: "USDT", Hourly: "0.0001", Daily: "0.0024", Limit: "1000"}}}})
		case strings.HasSuffix(p, "maxSize"):
			enc.Encode(MaxSize{AvailableBuy: "10", MaxBuy: "100", AvailableSell: "0", MaxSell: "0", MaxLeverage: 3})
		case strings.Contains(p, "orderBook"):
			now := time.Now().UnixMilli()
			enc.Encode(Book{Asks: []string{"2000.01", "10"}, Bids: []string{"2000", "10"}, TS: now})
		default:
			enc.Encode([]Market{mk})
		}
	}))
}

func TestFundingSnapshotAndPlan(t *testing.T) {
	srv := qfundingServer()
	defer srv.Close()
	c := NewClient("k", "s")
	c.BaseURL = srv.URL
	s, err := c.FundingSnapshot(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !s.FreeUSDT.Equal(d("100")) || len(s.Assets) != 2 {
		t.Fatalf("%v %v", s.FreeUSDT, s.Assets)
	}
	p, err := c.PlanFunding(context.Background(), "ETH_USDT", "convert", d("10"))
	if err != nil {
		t.Fatal(err)
	}
	if !p.AllowedQuote.Equal(d("10")) || p.LiveOrdersSubmitted {
		t.Fatal(p)
	}
	p, err = c.PlanFunding(context.Background(), "ETH_USDT", "margin", d("10"))
	if err != nil {
		t.Fatal(err)
	}
	if p.BorrowPossible || !p.AllowedQuote.Equal(d("10")) || len(p.Reasons) == 0 {
		t.Fatal(p)
	}
	if _, err = c.PlanFunding(context.Background(), "ETH_USDT", "margin", d("-1")); err == nil {
		t.Fatal("negative amount accepted")
	}
	if _, err = c.PlanFunding(context.Background(), "ETH_USDT", "bogus", d("10")); err == nil {
		t.Fatal("bad mode accepted")
	}
}

func TestFundingSnapshotBadHaircut(t *testing.T) {
	mk := market()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		enc := json.NewEncoder(w)
		switch {
		case strings.HasSuffix(p, "balances"):
			enc.Encode([]Account{{Type: "SPOT", Balances: []Balance{{Currency: "ETH", Available: "1", Hold: "0"}}}})
		case strings.HasSuffix(p, "accountMargin"):
			enc.Encode(Margin{Used: "0", Maintenance: "0", Free: "50", Value: "2100"})
		case strings.HasSuffix(p, "borrowStatus"):
			enc.Encode([]Borrow{})
		case strings.HasSuffix(p, "collateralInfo"):
			enc.Encode([]Collateral{{Currency: "ETH", Rate: "bogus"}})
		default:
			enc.Encode([]Market{mk})
		}
	}))
	defer srv.Close()
	c := NewClient("k", "s")
	c.BaseURL = srv.URL
	if _, err := c.FundingSnapshot(context.Background()); err == nil {
		t.Fatal("bad haircut accepted")
	}
}
