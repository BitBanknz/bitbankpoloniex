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

	"github.com/shopspring/decimal"
)

// A held rotation target below its slot share receives further capped orders
// until the share is reached; the legacy engine never grows a held position.
func TestSlotTopUpFillsHeldTargetWithCappedOrders(t *testing.T) {
	for _, topUp := range []bool{false, true} {
		e := engine(t)
		e.Config.SlotTopUp = topUp
		now := time.Now()
		s, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		s.Cash, s.HighWater, s.DayStart = d("990"), d("1000"), d("1000")
		s.Day = now.UTC().Format("2006-01-02")
		s.Holdings["ETH_USDT"] = Position{Quantity: d("0.005"), Peak: d("2000"), Entered: now.Add(-time.Hour)}
		if err := Save(e.path(), s); err != nil {
			t.Fatal(err)
		}
		if err := Save(filepath.Join(e.Config.StateDir, "models.json"), map[string]Model{"ETH_USDT": acceptedFixture(now)}); err != nil {
			t.Fatal(err)
		}
		var raw [][]any
		for _, b := range candles(500) {
			raw = append(raw, []any{b.Low, b.High, b.Open, b.Close, b.Volume, 0, 0, 0, 0, 0, 0, 0, b.Start, b.Start + 3600000 - 1})
		}
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch {
			case r.URL.Path == "/markets":
				json.NewEncoder(w).Encode([]Market{market()})
			case r.URL.Path == "/markets/ticker24h":
				json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
			case strings.HasSuffix(r.URL.Path, "/orderBook"):
				json.NewEncoder(w).Encode(book())
			case strings.HasSuffix(r.URL.Path, "/candles"):
				json.NewEncoder(w).Encode(raw)
			default:
				w.WriteHeader(503)
			}
		}))
		e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
		for i := 0; i < e.Config.MaxOrdersDay+2; i++ {
			if err := e.Cycle(context.Background()); err != nil {
				t.Fatal(err)
			}
		}
		srv.Close()
		after, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		if !topUp {
			if len(after.Fills) != 0 {
				t.Fatalf("legacy engine grew a held position: %+v", after.Fills)
			}
			continue
		}
		target := e.Config.slotTarget(after.Budget) // 1000 * 0.6 / 3 = 200
		if !target.Equal(d("200")) {
			t.Fatalf("slot target %s", target)
		}
		mark := after.Holdings["ETH_USDT"].Quantity.Mul(d("2000"))
		if mark.LessThan(d("193")) || mark.GreaterThan(d("200")) {
			t.Fatalf("held mark %s not filled toward target", mark)
		}
		if len(after.Fills) != 8 || after.OrdersToday != 8 {
			t.Fatalf("expected eight capped top-ups, got %d fills / %d orders", len(after.Fills), after.OrdersToday)
		}
		for _, f := range after.Fills {
			if f.Order.Side != "BUY" || f.Amount.GreaterThan(e.Config.MaxOrder.Mul(decimal.NewFromFloat(1.0001))) {
				t.Fatalf("top-up exceeded the per-order cap: %+v", f)
			}
		}
		if !after.Holdings["ETH_USDT"].Entered.Equal(s.Holdings["ETH_USDT"].Entered) || !after.Holdings["ETH_USDT"].Peak.Equal(d("2000")) {
			t.Fatal("top-up reset entry time or peak")
		}
		if after.Cash.LessThan(e.Config.reserve(after.Budget)) {
			t.Fatalf("cash %s breached the reserve", after.Cash)
		}
	}
}

func TestCashReserveConfig(t *testing.T) {
	c := DefaultConfig()
	if c.CashReserve != .4 || !c.reserve(d("1000")).Equal(d("400")) {
		t.Fatal("legacy 40% reserve default changed")
	}
	c.CashReserve = .2
	if !c.slotTarget(d("495")).Equal(d("132")) {
		t.Fatalf("slot target %s", c.slotTarget(d("495")))
	}
	for _, bad := range []float64{-.1, .95} {
		c.CashReserve = bad
		if err := c.Validate(); err == nil {
			t.Fatalf("reserve %v accepted", bad)
		}
	}
}

func TestRiskHaltBandsConfigurable(t *testing.T) {
	c := DefaultConfig()
	if p, d := c.haltBands(); p != .1 || d != .03 {
		t.Fatal("legacy halt bands changed")
	}
	c.HaltPeakDD, c.HaltDailyLoss = .25, .08
	if err := c.Validate(); err != nil {
		t.Fatal(err)
	}
	if p, d := c.haltBands(); p != .25 || d != .08 {
		t.Fatal("configured halt bands ignored")
	}
	for _, bad := range [][2]float64{{.6, .03}, {.1, .3}, {-.1, .03}} {
		c.HaltPeakDD, c.HaltDailyLoss = bad[0], bad[1]
		if err := c.Validate(); err == nil {
			t.Fatalf("halt bands %v accepted", bad)
		}
	}
	e := engine(t)
	e.Config.HaltPeakDD = .25
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	s.HighWater, s.DayStart, s.Cash = d("1000"), d("850"), d("850")
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/markets":
			json.NewEncoder(w).Encode([]Market{market()})
		case r.URL.Path == "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
		case strings.HasSuffix(r.URL.Path, "/orderBook"):
			json.NewEncoder(w).Encode(book())
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
	_ = e.Cycle(context.Background())
	after, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if after.Halted != "" {
		t.Fatalf("15%% below peak halted under a 25%% band: %s", after.Halted)
	}
	e.Config.HaltPeakDD = .1
	_ = e.Cycle(context.Background())
	if after, err = e.read(); err != nil || after.Halted == "" {
		t.Fatalf("legacy 10%% band did not halt: %v %q", err, after.Halted)
	}
}
