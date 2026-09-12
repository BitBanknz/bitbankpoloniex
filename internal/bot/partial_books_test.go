package bot

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestUnavailableHoldingBookDoesNotDisableOtherProtectiveStop(t *testing.T) {
	e := engine(t)
	now := time.Now()
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	s.Cash, s.HighWater, s.DayStart = d("960"), d("1050"), d("1000")
	s.Day, s.OrdersToday = now.Add(-24*time.Hour).UTC().Format("2006-01-02"), 2
	s.markEquity(now.Add(-time.Hour), d("1000"))
	s.Holdings["AAA_USDT"] = Position{Quantity: d("0.01"), Peak: d("2000"), Entered: now.Add(-100 * time.Hour)}
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.01"), Peak: d("4000"), Entered: now.Add(-time.Hour)}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	aaa, eth := market(), market()
	aaa.Symbol, aaa.Base = "AAA_USDT", "AAA"
	signalRequests := 0
	var recovered atomic.Bool
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/markets":
			json.NewEncoder(w).Encode([]Market{aaa, eth})
		case "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: aaa.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}, {Symbol: eth.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}})
		case "/markets/ETH_USDT/orderBook":
			json.NewEncoder(w).Encode(book())
		case "/markets/AAA_USDT/orderBook":
			if recovered.Load() {
				json.NewEncoder(w).Encode(book())
			} else {
				w.WriteHeader(503)
			}
		case "/prediction":
			signalRequests++
			w.WriteHeader(503)
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
	err = e.Cycle(context.Background())
	if err == nil || !strings.Contains(err.Error(), "AAA_USDT") {
		t.Fatalf("missing explicit degraded-market result: %v", err)
	}
	after, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if len(after.Fills) != 1 || after.Fills[0].Order.Symbol != "ETH_USDT" || after.Fills[0].Order.Side != "SELL" {
		t.Fatalf("missing book blocked unrelated protective stop: %+v", after.Fills)
	}
	if !reflect.DeepEqual(after.Equity, s.Equity) || !after.HighWater.Equal(s.HighWater) || !after.DayStart.Equal(s.DayStart) || !after.DayStartPending {
		t.Fatal("partial valuation invented/reset account or daily risk baseline")
	}
	if !after.Holdings["AAA_USDT"].Quantity.Equal(s.Holdings["AAA_USDT"].Quantity) || signalRequests != 0 || after.Halted != s.Halted {
		t.Fatal("unavailable holding, halt or signal contract changed")
	}
	if after.OrdersToday != 1 || after.Day != now.UTC().Format("2006-01-02") {
		t.Fatal("protective sale bypassed existing daily quota")
	}
	if err := e.trade(context.Background(), &after, aaa, book(), "BUY", now, "test"); err == nil {
		t.Fatal("pending daily valuation admitted a direct entry")
	}
	recovered.Store(true)
	if err := e.Cycle(context.Background()); err != ErrEntriesPaused {
		t.Fatalf("unexpected recovered cycle: %v", err)
	}
	complete, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if complete.DayStartPending || complete.OrdersToday != 1 || len(complete.Fills) != 1 {
		t.Fatal("recovery reset an already used current-day order allowance")
	}
	want := complete.Cash.Add(complete.Holdings["AAA_USDT"].Quantity.Mul(d("2000")))
	if !complete.DayStart.Equal(want) || !complete.Equity[len(complete.Equity)-1].Value.Equal(want) {
		t.Fatal("recovery did not establish a fully priced account baseline")
	}
}
