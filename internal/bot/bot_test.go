package bot

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/shopspring/decimal"
	"math"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func d(s string) decimal.Decimal { return decimal.RequireFromString(s) }
func market() Market {
	return Market{Symbol: "ETH_USDT", Base: "ETH", Quote: "USDT", State: "NORMAL", Limits: Limits{PriceScale: 2, QuantityScale: 6, MinQuantity: "0.000001", MinAmount: "1", MaxQuantity: "10000", MaxAmount: "1000000"}}
}
func book() Book {
	return Book{Asks: []string{"2000.01", "10"}, Bids: []string{"2000", "10"}, TS: time.Now().UnixMilli()}
}
func TestCanonicalSigning(t *testing.T) {
	q := url.Values{"symbol": {"ETH_USDT"}, "limit": {"5"}, "note": {"a b"}}
	want := "GET\n/orders\nlimit=5&note=a%20b&signTimestamp=123&symbol=ETH_USDT"
	if got := canonical("GET", "/orders", q, nil, "123"); got != want {
		t.Fatalf("%q", got)
	}
	if q.Get("signTimestamp") != "" {
		t.Fatal("mutated caller query")
	}
	got := canonical("POST", "/orders", nil, []byte(`{"symbol":"ETH_USDT"}`), "123")
	if got != "POST\n/orders\nrequestBody={\"symbol\":\"ETH_USDT\"}&signTimestamp=123" {
		t.Fatal(got)
	}
	if signature("key", "The quick brown fox jumps over the lazy dog") != "97yD9DBThCSxMpjmqm+xQ+9NWaFJRhdZl0edvC0aPNg=" {
		t.Fatal("HMAC test vector mismatch")
	}
}
func TestClientNoWriteRetryOrSecretError(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Header.Get("key") != "secret-key" {
			t.Error("missing key")
		}
		w.WriteHeader(503)
		fmt.Fprint(w, "secret-key secret-value")
	}))
	defer srv.Close()
	c := NewClient("secret-key", "secret-value")
	c.BaseURL = srv.URL
	_, err := c.Place(context.Background(), Order{Symbol: "ETH_USDT", Side: "BUY", Type: "LIMIT", TimeInForce: "IOC", AccountType: "SPOT", ClientID: "test"})
	if err == nil || calls != 1 || strings.Contains(err.Error(), "secret-") {
		t.Fatalf("calls=%d err=%v", calls, err)
	}
}
func TestOrderPrecisionLimitsAndFreshness(t *testing.T) {
	m, b := market(), book()
	o, err := BuildOrder(m, b, "BUY", "id", d("25"), decimal.Zero, .003)
	if err != nil {
		t.Fatal(err)
	}
	q, p := d(o.Quantity), d(o.Price)
	if q.Mul(p).GreaterThan(d("25")) || o.AllowBorrow || o.TimeInForce != "IOC" {
		t.Fatal(o)
	}
	for _, mutate := range []func(*Market, *Book){func(m *Market, b *Book) { m.State = "PAUSE" }, func(m *Market, b *Book) { b.TS = time.Now().Add(-time.Minute).UnixMilli() }, func(m *Market, b *Book) { b.Asks[0] = "2200" }, func(m *Market, b *Book) { m.Limits.MinAmount = "100" }, func(m *Market, b *Book) { m.Limits.QuantityScale = -1 }, func(m *Market, b *Book) { b.Bids[0] = "NaN" }} {
		m, b := market(), book()
		mutate(&m, &b)
		if _, err = BuildOrder(m, b, "BUY", "id", d("25"), decimal.Zero, .003); err == nil {
			t.Fatal("invalid order accepted")
		}
	}
}
func TestPredictionContract(t *testing.T) {
	now := time.Now().UTC().Truncate(24 * time.Hour).Add(90 * time.Minute)
	p := Prediction{Available: true, Venue: "POLONIEX", Mode: "research_rank_forecast", Issued: now.Truncate(24 * time.Hour), Ranks: map[string]float64{"ETHUSDT": -1, "BTCUSDT": 2}}
	p.Execution = p.Issued.Add(time.Hour)
	if err := p.Validate(now); err != nil {
		t.Fatal(err)
	}
	if p.Validate(now.Add(time.Hour)) == nil {
		t.Fatal("stale accepted")
	}
	p.Ranks["ETHUSDT"] = math.NaN()
	if p.Validate(now) == nil {
		t.Fatal("NaN accepted")
	}
	p.Ranks["ETHUSDT"] = 1
	p.Mode = "expected_return"
	if p.Validate(now) == nil {
		t.Fatal("wrong schema accepted")
	}
}
func TestTargetsStableAndNoInventedMarkets(t *testing.T) {
	m := []Market{market()}
	for i := 0; i < 10; i++ {
		x := Targets(map[string]float64{"ETH_USDT": 1, "FAKE_USDT": 99}, m, 4)
		if len(x) != 1 || x[0] != "ETH_USDT" {
			t.Fatal(x)
		}
	}
}
func TestStateLockAtomicAndCorruption(t *testing.T) {
	dir := t.TempDir()
	unlock, err := Lock(dir)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = Lock(dir); err == nil {
		t.Fatal("second writer allowed")
	}
	unlock()
	path := filepath.Join(dir, "state.json")
	if err = Save(path, map[string]int{"a": 1}); err != nil {
		t.Fatal(err)
	}
	st, _ := os.Stat(path)
	if st.Mode().Perm() != 0600 {
		t.Fatal("insecure state")
	}
	var v map[string]int
	if err = Load(path, &v); err != nil || v["a"] != 1 {
		t.Fatal(err)
	}
	os.WriteFile(path, []byte("{"), 0600)
	if Load(path, &v) == nil {
		t.Fatal("corruption ignored")
	}
}
func engine(t *testing.T) *Engine {
	t.Helper()
	cfg := DefaultConfig()
	cfg.StateDir = t.TempDir()
	e := &Engine{Config: cfg, Client: NewClient("key", "secret")}
	if err := e.Initialize(); err != nil {
		t.Fatal(err)
	}
	return e
}
func TestPaperDurabilityAndAccounting(t *testing.T) {
	e := engine(t)
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	o, _ := BuildOrder(market(), book(), "BUY", "id", d("25"), decimal.Zero, .003)
	if err = e.submit(context.Background(), &s, o, "decision", "test"); err != nil {
		t.Fatal(err)
	}
	reloaded, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if len(reloaded.Fills) != 1 || reloaded.Pending != nil || !reloaded.Processed["decision"] || !reloaded.Cash.LessThan(d("1000")) {
		t.Fatal("missing durable fill")
	}
	if err = e.Initialize(); err == nil {
		t.Fatal("reset allowed")
	}
	e.Config.Mode = "live"
	if _, err = e.read(); err == nil {
		t.Fatal("paper ledger accepted for live")
	}
}
func TestPendingUnknownDoesNotResubmit(t *testing.T) {
	e := engine(t)
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Method != "GET" {
			t.Fatal("resubmitted")
		}
		w.WriteHeader(404)
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	s, _ := e.read()
	s.Pending = &Pending{Order: Order{ClientID: "bbp-unknown"}}
	if err := e.resolve(context.Background(), &s); err == nil || s.Pending == nil || calls != 1 {
		t.Fatalf("%v %d", err, calls)
	}
}
func TestLivePartialFillReconcilesBaseFee(t *testing.T) {
	e := engine(t)
	e.Config.Mode = "live"
	s, _ := e.read()
	s = State{Mode: "live", Cash: d("1000"), Holdings: map[string]Position{}, Cooldown: map[string]time.Time{}}
	o := Order{Symbol: "ETH_USDT", Side: "BUY", Price: "2000", Quantity: "0.01", ClientID: "bbp-test"}
	s.Pending = &Pending{Order: o}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/trades") {
			json.NewEncoder(w).Encode([]Trade{{ID: "trade", OrderID: "order", Symbol: o.Symbol, Side: o.Side, Quantity: "0.005", Amount: "10", FeeCurrency: "ETH", FeeAmount: "0.00001"}})
		} else {
			json.NewEncoder(w).Encode(OrderResult{ID: "order", ClientID: o.ClientID, Symbol: o.Symbol, Side: o.Side, State: "CANCELED", FilledQuantity: "0.005", FilledAmount: "10"})
		}
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	if err := e.resolve(context.Background(), &s); err != nil {
		t.Fatal(err)
	}
	if !s.Holdings[o.Symbol].Quantity.Equal(d("0.00499")) || !s.Cash.Equal(d("990")) || s.Pending != nil {
		t.Fatal("partial fill accounting wrong")
	}
	if err := e.resolve(context.Background(), &s); err != nil || len(s.Fills) != 1 {
		t.Fatal("applied twice")
	}
}
func TestStopBlocksBeforeNetwork(t *testing.T) {
	e := engine(t)
	os.WriteFile(filepath.Join(e.Config.StateDir, "STOP"), []byte("stop"), 0600)
	e.Client.BaseURL = "http://127.0.0.1:1"
	if err := e.Cycle(context.Background()); err == nil || !strings.Contains(err.Error(), "STOP") {
		t.Fatal(err)
	}
}
func candles(n int) []Candle {
	b := make([]Candle, n)
	p := 100.
	start := time.Now().UTC().Truncate(time.Hour).Add(-time.Duration(n) * time.Hour).UnixMilli()
	for i := range b {
		close := p * (1 + .001*math.Sin(float64(i)/30))
		b[i] = Candle{Start: start + int64(i)*3600000, Open: p, Close: close, Low: math.Min(p, close) * .999, High: math.Max(p, close) * 1.001, Volume: 10000}
		p = close
	}
	return b
}
func TestFeaturesCausal(t *testing.T) {
	b := candles(1000)
	x := features(b, 500)
	for i := 501; i < len(b); i++ {
		b[i].Close *= 10
	}
	if features(b, 500) != x {
		t.Fatal("future leak")
	}
	s := samples(b[:600])
	for _, r := range s {
		if r.Index+Horizon+1 >= 600 {
			t.Fatal("label beyond data")
		}
	}
}
func TestChronologicalValidationAndFailClosed(t *testing.T) {
	b := candles(2400)
	for i := range b {
		b[i].Open = 100
		b[i].Close = 100
		b[i].High = 101
		b[i].Low = 99
	}
	m, err := Train("ETH_USDT", b)
	if err != nil {
		t.Fatal(err)
	}
	if m.Accepted || m.Valid(time.Now()) {
		t.Fatal("flat model accepted")
	}
	for i, f := range m.Folds {
		if f.TrainLast >= f.TestFirst {
			t.Fatal("train leakage")
		}
		if i > 0 && f.TestFirst <= m.Folds[i-1].TestLast {
			t.Fatal("fold overlap")
		}
	}
	m.Accepted = true
	m.Hash = m.checksum()
	if m.Valid(time.Now()) {
		t.Fatal("flag alone bypassed validation")
	}
	b[500].Start++
	if _, err = Train("ETH_USDT", b); err == nil {
		t.Fatal("gap accepted")
	}
}
func TestConfigRejectsRiskBypass(t *testing.T) {
	c := DefaultConfig()
	c.MaxOrder = d("101")
	if c.Validate() == nil {
		t.Fatal("oversize accepted")
	}
	c = DefaultConfig()
	c.MaxSpread = math.NaN()
	if c.Validate() == nil {
		t.Fatal("nonfinite risk limit")
	}
	_ = errors.New("")
}

func TestPaperCycleWaitsForExecutionAndUsesBitBank(t *testing.T) {
	e := engine(t)
	now := time.Now().UTC()
	issued := now.Truncate(24 * time.Hour)
	prediction := Prediction{Available: true, Venue: "POLONIEX", Mode: "research_rank_forecast", Issued: issued, Execution: issued.Add(time.Hour), Ranks: map[string]float64{"ETHUSDT": 1}}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Error("paper sent write")
		}
		switch r.URL.Path {
		case "/prediction":
			json.NewEncoder(w).Encode(prediction)
		case "/markets":
			json.NewEncoder(w).Encode([]Market{market()})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
		case "/markets/ETH_USDT/orderBook":
			json.NewEncoder(w).Encode(book())
		default:
			t.Errorf("unexpected request %s", r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	e.Config.PredictionURL = srv.URL + "/prediction"
	err := e.Cycle(context.Background())
	s, _ := e.read()
	if now.Before(prediction.Execution) {
		if err != nil || len(s.Fills) != 0 || s.LastCycle.IsZero() {
			t.Fatalf("premature trade or cycle failed: %v", err)
		}
	} else if now.Before(prediction.Execution.Add(time.Hour)) {
		if err != nil || len(s.Fills) != 1 {
			t.Fatalf("expected one paper fill: %v", err)
		}
		if err = e.Cycle(context.Background()); err != nil {
			t.Fatal(err)
		}
		s, _ = e.read()
		if len(s.Fills) != 1 {
			t.Fatal("duplicate paper fill")
		}
	} else {
		if err == nil || len(s.Fills) != 0 {
			t.Fatal("stale primary traded")
		}
	}
}
func TestUnavailablePrimaryAndNoFallbackPausesEntries(t *testing.T) {
	e := engine(t)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{market()})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	e.Config.PredictionURL = srv.URL + "/prediction"
	err := e.Cycle(context.Background())
	s, _ := e.read()
	if err == nil || len(s.Fills) > 0 || s.LastSource != "waiting_for_execution_or_validated_fallback" {
		t.Fatalf("fallback failed open: %v", err)
	}
}

// Synthetic acceptance metadata exercises the failover plumbing only; it is not
// evidence that any trained market model passed historical validation.
func acceptedFixture(now time.Time) Model {
	m := Model{Symbol: "ETH_USDT", Schema: FeatureSchema, TrainedThrough: now.Truncate(time.Hour).Add(-time.Hour), Expires: now.Add(time.Hour), Accepted: true, Ensemble: Ensemble{Bias: .02}}
	base := now.Add(-30 * 24 * time.Hour).UnixMilli()
	for i := 0; i < 4; i++ {
		first := base + int64(i)*48*3600000
		m.Folds = append(m.Folds, Fold{TrainLast: first - 3600000, TestFirst: first, TestLast: first + 24*3600000, Trades: 4, Net: .01, MaxDrawdown: .01, ModelMSE: .001, ZeroMSE: .002})
	}
	m.Hash = m.checksum()
	return m
}
func TestFallbackExpirationAndTampering(t *testing.T) {
	now := time.Now()
	m := acceptedFixture(now)
	if !m.Valid(now) {
		t.Fatal("valid synthetic fixture rejected")
	}
	if m.Valid(now.Add(2 * time.Hour)) {
		t.Fatal("expired accepted")
	}
	m.Ensemble.Bias = .5
	if m.Valid(now) {
		t.Fatal("modified weights accepted")
	}
}
func TestValidatedFallbackActivatesOnPrimaryOutage(t *testing.T) {
	e := engine(t)
	m := acceptedFixture(time.Now())
	if err := Save(filepath.Join(e.Config.StateDir, "models.json"), map[string]Model{"ETH_USDT": m}); err != nil {
		t.Fatal(err)
	}
	bars := candles(500)
	raw := [][]any{}
	for _, b := range bars {
		raw = append(raw, []any{fmt.Sprint(b.Low), fmt.Sprint(b.High), fmt.Sprint(b.Open), fmt.Sprint(b.Close), "100000", "100", "100", "100", 1, b.Start + 3600000 - 1, "100", "HOUR_1", b.Start, b.Start + 3600000 - 1})
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Error("paper fallback sent write")
		}
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{market()})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
		case "/markets/ETH_USDT/candles":
			json.NewEncoder(w).Encode(raw)
		case "/markets/ETH_USDT/orderBook":
			json.NewEncoder(w).Encode(book())
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
	s, _ := e.read()
	if len(s.Fills) != 1 || s.LastSource != "go_boosted_fallback" {
		t.Fatalf("failover not active: %s fills=%d", s.LastSource, len(s.Fills))
	}
}
