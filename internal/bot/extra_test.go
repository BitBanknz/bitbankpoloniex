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

func TestScoresMapping(t *testing.T) {
	p := Prediction{Ranks: map[string]float64{"ETHUSDT": 1.5, "BTCUSDT": -2}}
	s := p.Scores()
	if s["ETH_USDT"] != 1.5 || s["BTC_USDT"] != -2 || len(s) != 2 {
		t.Fatal(s)
	}
}

func drow(start int64, i int) []any {
	open := 100. + float64(i)
	return []any{open - 1, open + 2, open, open + 1, "200000", nil, nil, nil, nil, nil, nil, nil, start, start + 86399999}
}

func dbars(daysAgo, n int, skip map[int64]bool) [][]any {
	last := time.Now().UTC().Truncate(24 * time.Hour).Add(-24 * time.Hour).UnixMilli()
	base := last - int64(daysAgo)*86400000
	rows := [][]any{}
	for i := 0; i < n; i++ {
		s := base - int64(n-1-i)*86400000
		if skip[s] {
			continue
		}
		rows = append(rows, drow(s, i))
	}
	return rows
}

func TestDailyHistory(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dbars(0, 210, nil))
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	bars, err := c.DailyHistory(context.Background(), "ETH_USDT")
	if err != nil || len(bars) != 210 {
		t.Fatalf("%v %v", len(bars), err)
	}
	short := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dbars(0, 100, nil))
	}))
	defer short.Close()
	c.BaseURL = short.URL
	if _, err := c.DailyHistory(context.Background(), "ETH_USDT"); err == nil {
		t.Fatal("short daily accepted")
	}
	last := time.Now().UTC().Truncate(24 * time.Hour).Add(-24 * time.Hour).UnixMilli()
	gap := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dbars(0, 210, map[int64]bool{last - 50*86400000: true}))
	}))
	defer gap.Close()
	c.BaseURL = gap.URL
	if _, err := c.DailyHistory(context.Background(), "ETH_USDT"); err == nil {
		t.Fatal("gapped daily accepted")
	}
	stale := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dbars(5, 210, nil))
	}))
	defer stale.Close()
	c.BaseURL = stale.URL
	if _, err := c.DailyHistory(context.Background(), "ETH_USDT"); err == nil {
		t.Fatal("stale daily accepted")
	}
}

func TestBTCRegimeEdges(t *testing.T) {
	if BTCRegime(nil) {
		t.Fatal("empty regime on")
	}
	up := candles(200)
	for i := range up {
		up[i].Close = 100 + float64(i)
	}
	if !BTCRegime(up) {
		t.Fatal("rising regime off")
	}
	down := candles(200)
	for i := range down {
		down[i].Close = 300 - float64(i)
	}
	if BTCRegime(down) {
		t.Fatal("falling regime on")
	}
}

func TestDailyTrendEdges(t *testing.T) {
	if _, ok := DailyTrend(candles(100)); ok {
		t.Fatal("short trend ok")
	}
	up := candles(130)
	for i := range up {
		up[i].Close = 100 + float64(i)
		up[i].Volume = 200000
	}
	v, ok := DailyTrend(up)
	if !ok || v <= 0 {
		t.Fatalf("%v %v", v, ok)
	}
	thin := candles(130)
	for i := range thin {
		thin[i].Close = 100 + float64(i)
		thin[i].Volume = 10
	}
	if _, ok := DailyTrend(thin); ok {
		t.Fatal("thin trend ok")
	}
	down := candles(130)
	for i := range down {
		down[i].Close = 300 - float64(i)
		down[i].Volume = 200000
	}
	if _, ok := DailyTrend(down); ok {
		t.Fatal("falling trend ok")
	}
}

func TestResearchSignalsComputeAndCache(t *testing.T) {
	rows := dbars(0, 210, nil)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(rows)
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	dir := t.TempDir()
	mk := func(sym, base string) Market {
		return Market{Symbol: sym, Base: base, Quote: "USDT", State: "NORMAL", Limits: market().Limits}
	}
	markets := []Market{mk("ETH_USDT", "ETH"), mk("XRP_USDT", "XRP"), mk("SOL_USDT", "SOL")}
	s, err := c.ResearchSignals(context.Background(), dir, markets)
	if err != nil {
		t.Fatal(err)
	}
	if !s.RegimeOn || len(s.Scores) != 3 || len(s.Failures) != 0 || s.LiveApproved {
		t.Fatalf("%+v", s)
	}
	cached, err := c.ResearchSignals(context.Background(), dir, markets)
	if err != nil || len(cached.Scores) != 3 {
		t.Fatalf("%v %+v", err, cached)
	}
	if _, err := c.ResearchSignals(context.Background(), t.TempDir(), nil); err == nil {
		t.Fatal("empty coverage accepted")
	}
}

func qreadyServer(open bool) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		enc := json.NewEncoder(w)
		switch {
		case strings.HasSuffix(r.URL.Path, "accountMargin"):
			enc.Encode(Margin{Used: "0", Maintenance: "0", Free: "50", Value: "100"})
		case strings.HasSuffix(r.URL.Path, "borrowStatus"):
			enc.Encode([]Borrow{})
		case strings.HasSuffix(r.URL.Path, "orders"):
			if open {
				enc.Encode([]OrderResult{{Symbol: "ETH_USDT", Side: "BUY", State: "OPEN"}})
			} else {
				enc.Encode([]OrderResult{})
			}
		default:
			enc.Encode([]Account{{Type: "SPOT", Balances: []Balance{{Currency: "USDT", Available: "100", Hold: "0"}}}})
		}
	}))
}

func TestReadyAndStatus(t *testing.T) {
	srv := qreadyServer(false)
	defer srv.Close()
	e := engine(t)
	e.Client.BaseURL = srv.URL
	if err := e.Ready(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err := e.Client.OpenOrders(context.Background()); err != nil {
		t.Fatal(err)
	}
	s, err := e.Status()
	if err != nil || s.Mode != "paper" {
		t.Fatalf("%v %+v", err, s)
	}
	busy := qreadyServer(true)
	defer busy.Close()
	e.Client.BaseURL = busy.URL
	if err := e.Ready(context.Background()); err == nil {
		t.Fatal("open orders ready")
	}
}

func TestTradePaperPending(t *testing.T) {
	e := engine(t)
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	hour := time.Now().UTC().Truncate(time.Hour)
	if err := e.trade(context.Background(), &s, market(), book(), "BUY", hour, "test"); err != nil {
		t.Fatal(err)
	}
	if s.Pending != nil || s.OrdersToday != 1 || !s.Holdings["ETH_USDT"].Quantity.IsPositive() {
		t.Fatalf("%+v", s.Pending)
	}
}

func TestArchiveCompletesEmpty(t *testing.T) {
	mk := market()
	now := time.Now().UnixMilli()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		switch {
		case strings.HasSuffix(p, "ticker24h"):
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "200000", TS: now}})
		case strings.Contains(p, "candles"):
			json.NewEncoder(w).Encode([][]any{})
		default:
			json.NewEncoder(w).Encode([]Market{mk})
		}
	}))
	defer srv.Close()
	c := NewClient("", "")
	c.BaseURL = srv.URL
	root := t.TempDir()
	if err := c.Archive(context.Background(), root, "HOUR_1", 1); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(root, "manifest.json")); err != nil {
		t.Fatal(err)
	}
}
