package bot

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func fundingClient(t *testing.T) (*Client, func()) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("unexpected financial write %s", r.Method)
		}
		var v any
		switch r.URL.Path {
		case "/accounts/balances":
			v = []Account{{Type: "SPOT", Balances: []Balance{{Currency: "ETH", Available: "0.2", Hold: "0"}, {Currency: "USDT", Available: "0", Hold: "0"}}}}
		case "/margin/accountMargin":
			v = Margin{Used: "0", Maintenance: "0", Free: "380", Value: "400"}
		case "/margin/borrowStatus":
			v = []Borrow{{Currency: "ETH", Borrowed: "0"}}
		case "/markets/collateralInfo":
			v = []Collateral{{Currency: "ETH", Rate: "0.95", Initial: "0.5", Maintenance: "0.1"}}
		case "/markets":
			v = []Market{market()}
		case "/markets/ETH_USDT/orderBook":
			v = book()
		case "/orders":
			v = []OrderResult{}
		case "/margin/maxSize":
			v = MaxSize{AvailableBuy: "0", MaxBuy: "100", MaxLeverage: 3}
		case "/markets/borrowRatesInfo":
			v = []BorrowTier{{Tier: "TIER0", Rates: []BorrowRate{{Currency: "USDT", Hourly: "0.00001"}}}}
		default:
			t.Errorf("unexpected path %s", r.URL.Path)
			w.WriteHeader(404)
			return
		}
		json.NewEncoder(w).Encode(v)
	}))
	c := NewClient("test-key", "test-secret")
	c.BaseURL = srv.URL
	return c, srv.Close
}
func TestFundingSeparatesETHCashAndCollateral(t *testing.T) {
	c, close := fundingClient(t)
	defer close()
	s, err := c.FundingSnapshot(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !s.FreeUSDT.IsZero() || !s.PricedFreeEquity.Equal(d("400")) || !s.CollateralValue.Equal(d("380")) {
		t.Fatalf("bad account valuation: %+v", s)
	}
}
func TestMarginPlanUsesBorrowLimitAndInterest(t *testing.T) {
	c, close := fundingClient(t)
	defer close()
	p, err := c.PlanFunding(context.Background(), "ETH_USDT", "margin", d("1000"))
	if err != nil {
		t.Fatal(err)
	}
	if !p.AllowedQuote.Equal(d("95")) || !p.BorrowPossible || !p.HourlyInterestStress.Equal(d("0.0019")) || p.LiveOrdersSubmitted {
		t.Fatalf("bad plan %+v", p)
	}
}
func TestAccountMirrorDoesNotInventCash(t *testing.T) {
	c, close := fundingClient(t)
	defer close()
	cfg := DefaultConfig()
	cfg.StateDir = t.TempDir()
	e := Engine{Client: c, Config: cfg}
	if err := e.InitializeFromAccount(context.Background()); err != nil {
		t.Fatal(err)
	}
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if !s.AccountBacked || !s.Cash.IsZero() || !s.Budget.Equal(d("400")) || !s.Holdings["ETH_USDT"].Quantity.Equal(d(".2")) {
		t.Fatal("inventory converted into fictional cash")
	}
	if err = e.InitializeFromAccount(context.Background()); err == nil {
		t.Fatal("ledger overwritten")
	}
}
func TestArchiveDailyClockAndMalformedLow(t *testing.T) {
	stamp := time.Now().UTC().Truncate(24 * time.Hour).Add(-24 * time.Hour).UnixMilli()
	raw := []any{"99", "101", "100", "100", "10000", "1", "0", "0", 1, stamp, "100", "DAY_1", stamp, stamp + 86400000 - 1}
	b, _ := json.Marshal(raw)
	var row []json.RawMessage
	json.Unmarshal(b, &row)
	bars, err := parseArchive([][]json.RawMessage{row}, time.Now(), 86400000)
	if err != nil || len(bars) != 1 {
		t.Fatal(err)
	}
	row[0] = json.RawMessage(`"0"`)
	if _, err = parseArchive([][]json.RawMessage{row}, time.Now(), 86400000); err == nil {
		t.Fatal("invalid low accepted")
	}
}
func TestArchiveQuarantinesInvalidRowsAndResumes(t *testing.T) {
	stamp := time.Now().UTC().Truncate(24 * time.Hour).Add(-48 * time.Hour).UnixMilli()
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if strings.Contains(r.URL.RawQuery, "endTime="+jsonNumber(stamp-1)) {
			json.NewEncoder(w).Encode([]any{})
			return
		}
		json.NewEncoder(w).Encode([][]any{{"0", "101", "100", "100", "10", "1", "0", "0", 1, stamp, "100", "DAY_1", stamp, stamp + 86400000 - 1}, {"99", "101", "100", "100", "10", "1", "0", "0", 1, stamp + 86400000, "100", "DAY_1", stamp + 86400000, stamp + 172800000 - 1}})
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	root := t.TempDir()
	s, err := c.archiveSymbol(context.Background(), root, "ETH_USDT", "DAY_1")
	if err != nil || !s.Complete || s.Rows != 1 || s.Quarantined != 1 {
		t.Fatalf("%+v %v", s, err)
	}
	before := calls
	if _, err = c.archiveSymbol(context.Background(), root, "ETH_USDT", "DAY_1"); err != nil || calls != before {
		t.Fatal("completed archive refetched")
	}
}
func jsonNumber(v int64) string { b, _ := json.Marshal(v); return string(b) }
func TestMarginPaperAccruesAndRepaysWithoutSellingCollateral(t *testing.T) {
	c, close := fundingClient(t)
	defer close()
	dir := t.TempDir()
	s, err := c.MarginPaperStep(context.Background(), dir, "ETH_USDT", d("25"))
	if err != nil {
		t.Fatal(err)
	}
	if !s.Debt.IsPositive() || !s.Collateral["ETH_USDT"].Equal(d(".2")) || len(s.Fills) != 1 {
		t.Fatal("missing debt or collateral changed")
	}
	before := s.Debt
	if err = s.Accrue(s.LastAccrual.Add(time.Hour)); err != nil || !s.Debt.GreaterThan(before) {
		t.Fatal("interest not charged")
	}
	closed, err := c.MarginPaperClose(context.Background(), dir, "ETH_USDT")
	if err != nil {
		t.Fatal(err)
	}
	if !closed.Holdings["ETH_USDT"].Equal(d(".2")) || !closed.Debt.LessThan(before) {
		t.Fatal("repayment sold collateral or did not reduce debt")
	}
}
func TestDustTopLevelDoesNotHideExecutableDepth(t *testing.T) {
	b := book()
	b.Bids = []string{"2000", "0.000001", "1999.9", "2", "1900", "100"}
	o, err := BuildOrder(market(), b, "SELL", "depth-test", d("0"), d(".01"), .003)
	if err != nil {
		t.Fatal(err)
	}
	if !d(o.Quantity).Equal(d(".01")) || !d(o.Price).Equal(d("1999.9")) {
		t.Fatalf("unexpected depth order %+v", o)
	}
}
func TestResearchPolicyCannotEnableLive(t *testing.T) {
	cfg := DefaultConfig()
	cfg.Mode = "live"
	cfg.ExperimentalFallback = true
	if cfg.Validate() == nil {
		t.Fatal("experimental live policy allowed")
	}
}
func TestDailyMomentumAndBTCRegime(t *testing.T) {
	bars := make([]Candle, 220)
	for i := range bars {
		bars[i] = Candle{Close: 100 + float64(i), Volume: 200000}
	}
	score, ok := DailyTrend(bars)
	if !ok || score <= 0 || !BTCRegime(bars) {
		t.Fatal("uptrend rejected")
	}
	bars[len(bars)-1].Close = 1
	if BTCRegime(bars) {
		t.Fatal("bearish BTC regime accepted")
	}
}
func TestExperimentalCycleConvertsImportedETH(t *testing.T) {
	e := engine(t)
	e.Config.ExperimentalFallback = true
	s, _ := e.read()
	s.AccountBacked = true
	s.Cash = d("0")
	s.Budget = d("400")
	s.HighWater = d("400")
	s.DayStart = d("400")
	s.Holdings = map[string]Position{"ETH_USDT": {Imported: true, Quantity: d(".2"), Peak: d("2000"), Entered: time.Now().UTC()}}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	signal := ResearchSignal{Schema: "trend20-btc-paper-v1", Day: time.Now().UTC().Truncate(24 * time.Hour), Source: "experimental_test", Scores: map[string]float64{"BTC_USDT": 1}, Observed: map[string]bool{"BTC_USDT": true, "ETH_USDT": true}}
	if err := Save(filepath.Join(e.Config.StateDir, "experimental-signals.json"), signal); err != nil {
		t.Fatal(err)
	}
	btc := market()
	btc.Symbol = "BTC_USDT"
	btc.Base = "BTC"
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Error("paper sent exchange write")
		}
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{market(), btc})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}, {Symbol: "BTC_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
		case "/markets/ETH_USDT/orderBook", "/markets/BTC_USDT/orderBook":
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
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if len(s.Fills) != 1 || s.Fills[0].Order.Side != "SELL" || !s.Cash.IsPositive() || !s.Holdings["ETH_USDT"].Quantity.LessThan(d(".2")) || s.LastSource != "experimental_test" {
		t.Fatal("account funding failover not applied")
	}
}
