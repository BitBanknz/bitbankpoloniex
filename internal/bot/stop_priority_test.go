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

func TestProtectiveStopGetsLastDailyAllowanceBeforeRotation(t *testing.T) {
	e := engine(t)
	now := time.Now()
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	s.Cash, s.HighWater, s.DayStart = d("960"), d("1000"), d("1000")
	s.Day, s.OrdersToday = now.UTC().Format("2006-01-02"), e.Config.MaxOrdersDay-1
	s.Holdings["AAA_USDT"] = Position{Quantity: d("0.01"), Peak: d("2000"), Entered: now.Add(-100 * time.Hour)}
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.01"), Peak: d("4000"), Entered: now.Add(-time.Hour)}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	ordinary, held := acceptedFixture(now), acceptedFixture(now)
	ordinary.Symbol, ordinary.Ensemble.Bias = "AAA_USDT", -.02
	ordinary.Hash = ordinary.checksum()
	if err := Save(filepath.Join(e.Config.StateDir, "models.json"), map[string]Model{"AAA_USDT": ordinary, "ETH_USDT": held}); err != nil {
		t.Fatal(err)
	}
	var raw [][]any
	for _, b := range candles(500) {
		raw = append(raw, []any{b.Low, b.High, b.Open, b.Close, b.Volume, 0, 0, 0, 0, 0, 0, 0, b.Start, b.Start + 3600000 - 1})
	}
	aaa, eth := market(), market()
	aaa.Symbol, aaa.Base = "AAA_USDT", "AAA"
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/markets":
			json.NewEncoder(w).Encode([]Market{aaa, eth})
		case r.URL.Path == "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: aaa.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}, {Symbol: eth.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}})
		case strings.HasSuffix(r.URL.Path, "/orderBook"):
			json.NewEncoder(w).Encode(book())
		case strings.HasSuffix(r.URL.Path, "/candles"):
			json.NewEncoder(w).Encode(raw)
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
	if err := e.Cycle(context.Background()); err != nil {
		t.Fatal(err)
	}
	after, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if len(after.Fills) != 1 || after.Fills[0].Order.Symbol != "ETH_USDT" || after.Fills[0].Order.Side != "SELL" {
		t.Fatalf("ordinary rotation consumed protective allowance: %+v", after.Fills)
	}
	if after.OrdersToday != e.Config.MaxOrdersDay || !after.Holdings["AAA_USDT"].Quantity.Equal(s.Holdings["AAA_USDT"].Quantity) {
		t.Fatal("daily cap or deferred ordinary holding changed")
	}
	if _, held := after.Holdings["ETH_USDT"]; held {
		t.Fatal("protective position remains")
	}
}
