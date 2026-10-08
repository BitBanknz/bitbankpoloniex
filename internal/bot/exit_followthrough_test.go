package bot

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func thinBook(bidLevels ...string) Book {
	return Book{Asks: []string{"2000.5", "1", "2001", "1"}, Bids: bidLevels, TS: time.Now().UnixMilli()}
}

func TestBuildOrderOptsZeroIsLegacy(t *testing.T) {
	for _, side := range []string{"BUY", "SELL"} {
		a, errA := BuildOrder(market(), book(), side, "id", d("25"), d("0.01"), .003)
		b, errB := BuildOrderOpts(market(), book(), side, "id", d("25"), d("0.01"), OrderOpts{MaxSpread: .003})
		if errA != nil || errB != nil || a.Price != b.Price || a.Quantity != b.Quantity {
			t.Fatalf("%s: %+v %v / %+v %v", side, a, errA, b, errB)
		}
	}
}

func TestMinExitRaisesThinBookSellAndPaperFillIsCappedAtBook(t *testing.T) {
	b := thinBook("2000", "0.001", "1990", "0.01")
	if _, err := BuildOrder(market(), b, "SELL", "id", decimal.Zero, d("0.02"), .003); err == nil {
		t.Fatal("legacy 10% clip of 2 USDT depth should fall below the 1 USDT minimum")
	}
	o, err := BuildOrderOpts(market(), b, "SELL", "id", decimal.Zero, d("0.02"), OrderOpts{MaxSpread: .003, MinQuote: d("24.5")})
	if err != nil || o.Quantity != "0.01225" || o.Price != "2000" || !o.fillable.Equal(d("0.001")) {
		t.Fatalf("%+v %v", o, err)
	}
	small, err := BuildOrderOpts(market(), b, "SELL", "id", decimal.Zero, d("0.005"), OrderOpts{MaxSpread: .003, MinQuote: d("24.5")})
	if err != nil || small.Quantity != "0.005" {
		t.Fatalf("floor must not exceed the holding: %+v %v", small, err)
	}
	buy, err := BuildOrderOpts(market(), book(), "BUY", "id", d("25"), decimal.Zero, OrderOpts{MaxSpread: .003, MinQuote: d("49")})
	if err != nil || buy.Quantity != "0.012499" {
		t.Fatalf("buys ignore the exit floor: %+v %v", buy, err)
	}
	e := engine(t)
	s, _ := e.read()
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.02"), Peak: d("2000"), Entered: time.Now().Add(-time.Hour)}
	if err := e.submit(context.Background(), &s, o, "k", "test"); err != nil {
		t.Fatal(err)
	}
	if f := s.Fills[len(s.Fills)-1]; !f.Quantity.Equal(d("0.001")) || !s.Holdings["ETH_USDT"].Quantity.Equal(d("0.019")) {
		t.Fatalf("paper IOC filled beyond visible depth: %+v", f)
	}
}

func TestStopLatchPersistsAndClearsWhenOff(t *testing.T) {
	cfg := Config{ExitRampMinutes: 20}
	now := time.Date(2026, 10, 9, 10, 0, 0, 0, time.UTC)
	p := Position{Quantity: d("1"), Peak: d("100"), Entered: now.Add(-time.Hour)}
	stop, _, q := cfg.protectiveExit(p, d("89"), .9, now)
	if !stop || q.Exiting != exitStop || q.ExitSince == nil || !q.ExitSince.Equal(now) {
		t.Fatalf("stop did not latch: %+v", q)
	}
	stop, _, r := cfg.protectiveExit(q, d("99"), .9, now.Add(5*time.Minute))
	if !stop || !r.ExitSince.Equal(now) {
		t.Fatal("latched stop must keep selling after the bid recovers, from its original time")
	}
	stop, _, r = (Config{}).protectiveExit(q, d("99"), .9, now)
	if stop || r.Exiting != "" || r.ExitSince != nil {
		t.Fatal("latch must clear once the ramp is switched off")
	}
	if stop, _, r = (Config{}).protectiveExit(p, d("89"), .9, now); !stop || r.Exiting != "" {
		t.Fatal("legacy stop must not latch")
	}
}

func TestExitOptsRamp(t *testing.T) {
	cfg := Config{MaxSpread: .003, ExitRampMinutes: 20, MinExitUSDT: d("24.5")}
	t0 := time.Date(2026, 10, 9, 10, 0, 0, 0, time.UTC)
	p := Position{Exiting: exitStop, ExitSince: &t0}
	o, follow := cfg.exitOpts(p, t0)
	if !follow || o.Band != .001 || o.Participation != .1 || o.MaxSpread != .003 || !o.MinQuote.Equal(d("24.5")) {
		t.Fatalf("%+v", o)
	}
	o, _ = cfg.exitOpts(p, t0.Add(10*time.Minute))
	if o.Band < .0054 || o.Band > .0056 || o.Participation != .55 || o.MaxSpread != o.Band {
		t.Fatalf("%+v", o)
	}
	o, _ = cfg.exitOpts(p, t0.Add(3*time.Hour))
	if o.Band != exitRampMaxBand || o.Participation != 1 {
		t.Fatalf("%+v", o)
	}
	if o, follow = cfg.exitOpts(Position{}, t0); follow || o.Band != 0 || !o.MinQuote.Equal(d("24.5")) {
		t.Fatal("unlatched exits get only the floor")
	}
	if o, follow = (Config{MaxSpread: .003}).exitOpts(p, t0); follow || o.Band != 0 || o.MinQuote.IsPositive() {
		t.Fatal("ramp off must be the legacy order")
	}
	for _, bad := range []Config{{ExitRampMinutes: -1}, {ExitRampMinutes: 61}, {MinExitUSDT: d("-1"), MaxOrder: d("49")}, {MinExitUSDT: d("50"), MaxOrder: d("49")}} {
		if bad.validateExits() == nil {
			t.Fatalf("accepted %+v", bad)
		}
	}
}

// A thin-book stop sells the floor clip, latches, and keeps working the
// remainder every cycle (wider band later in the ramp, past the daily cap)
// until flat, even after the bid recovers above the stop.
func TestThinBookStopFollowsThroughUntilFlat(t *testing.T) {
	e := engine(t)
	e.Config.MinExitUSDT, e.Config.ExitRampMinutes = d("24.5"), 20
	now := time.Now()
	s, _ := e.read()
	s.Cash, s.HighWater, s.DayStart = d("960"), d("1000"), d("1000")
	s.Day, s.OrdersToday = now.UTC().Format("2006-01-02"), e.Config.MaxOrdersDay
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.02"), Peak: d("2300"), Entered: now.Add(-time.Hour)}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	var bid atomic.Value
	bid.Store("2000")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/markets":
			json.NewEncoder(w).Encode([]Market{market()})
		case r.URL.Path == "/markets/ticker24h":
			json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
		case strings.HasSuffix(r.URL.Path, "/orderBook"):
			b := bid.Load().(string)
			second := d(b).Sub(d("10")).String()
			json.NewEncoder(w).Encode(Book{Asks: []string{d(b).Add(d("0.5")).String(), "1"}, Bids: []string{b, "0.001", second, "0.01"}, TS: time.Now().UnixMilli()})
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
	cycle := func() State {
		t.Helper()
		if err := e.Cycle(context.Background()); err != nil && err != ErrEntriesPaused {
			t.Fatal(err)
		}
		st, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		return st
	}
	nextMinute := func(back time.Duration) {
		st, _ := e.read()
		for k := range st.Processed {
			if strings.Contains(k, "|protect-") {
				delete(st.Processed, k)
			}
		}
		p := st.Holdings["ETH_USDT"]
		since := p.ExitSince.Add(-back)
		p.ExitSince = &since
		st.Holdings["ETH_USDT"] = p
		if err := Save(e.path(), st); err != nil {
			t.Fatal(err)
		}
	}
	st := cycle()
	p := st.Holdings["ETH_USDT"]
	if len(st.Fills) != 1 || !st.Fills[0].Quantity.Equal(d("0.001")) || p.Exiting != exitStop || !p.Quantity.Equal(d("0.019")) {
		t.Fatalf("first clip: fills=%+v pos=%+v", st.Fills, p)
	}
	if st = cycle(); len(st.Fills) != 1 {
		t.Fatal("a follow-up must not repeat within the same minute")
	}
	bid.Store("2290") // recovered above the 2070 stop; the latch keeps selling
	nextMinute(30 * time.Minute)
	st = cycle()
	if len(st.Fills) != 2 || st.Fills[1].Order.Price != "2280" || !st.Fills[1].Quantity.Equal(d("0.010964")) { // 25 USDT order cap
		t.Fatalf("ramped follow-up: %+v", st.Fills)
	}
	nextMinute(0)
	st = cycle()
	if _, held := st.Holdings["ETH_USDT"]; held || len(st.Fills) != 3 || st.OrdersToday != e.Config.MaxOrdersDay+3 {
		t.Fatalf("not flat: holdings=%+v fills=%d orders=%d", st.Holdings, len(st.Fills), st.OrdersToday)
	}
}

func TestLegacyThinBookStopStalls(t *testing.T) {
	e := engine(t)
	now := time.Now()
	s, _ := e.read()
	s.Cash, s.HighWater, s.DayStart = d("960"), d("1000"), d("1000")
	s.Day = now.UTC().Format("2006-01-02")
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.02"), Peak: d("2300"), Entered: now.Add(-time.Hour)}
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
			json.NewEncoder(w).Encode(thinBook("2000", "0.001", "1990", "0.01"))
		default:
			w.WriteHeader(503)
		}
	}))
	defer srv.Close()
	e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
	if err := e.Cycle(context.Background()); err != nil && err != ErrEntriesPaused {
		t.Fatal(err)
	}
	st, _ := e.read()
	if len(st.Fills) != 0 || st.Holdings["ETH_USDT"].Exiting != "" {
		t.Fatalf("defaults changed legacy stop behaviour: %+v", st.Fills)
	}
}

func TestPaperPendingRecoveryKeepsIOCCap(t *testing.T) {
	e := engine(t)
	o, err := BuildOrderOpts(market(), thinBook("2000", "0.001", "1990", "0.01"), "SELL", "id", decimal.Zero, d("0.02"), OrderOpts{MaxSpread: .003, MinQuote: d("24.5")})
	if err != nil {
		t.Fatal(err)
	}
	s, _ := e.read()
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.02"), Peak: d("2000"), Entered: time.Now().Add(-time.Hour)}
	f := o.fillable
	s.Pending = &Pending{Order: o, Decision: "k", Created: time.Now(), Source: "test", Fillable: &f}
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	e.Client.BaseURL = "http://127.0.0.1:1" // recovery happens before any request; the cycle then fails offline
	_ = e.Cycle(context.Background())
	st, _ := e.read()
	if st.Pending != nil || len(st.Fills) != 1 || !st.Fills[0].Quantity.Equal(d("0.001")) {
		t.Fatalf("recovered paper intent ignored its IOC cap: %+v", st.Fills)
	}
}

func TestSubIncrementDepthIsNotExecutable(t *testing.T) {
	if _, err := BuildOrderOpts(market(), thinBook("2000", "0.0000004", "1990", "0.01"), "SELL", "id", decimal.Zero, d("0.02"), OrderOpts{MaxSpread: .003, MinQuote: d("24.5")}); err == nil {
		t.Fatal("depth below one quantity increment must not produce an unbounded floor order")
	}
}

func TestTakeProfitLatchFromRampOffRunGetsRampClock(t *testing.T) {
	now := time.Date(2026, 10, 9, 10, 0, 0, 0, time.UTC)
	entry := d("100")
	p := Position{Quantity: d("1"), Peak: d("150"), Entry: &entry, Exiting: exitTakeProfit}
	_, profit, q := (Config{TakeProfit: .3, ExitRampMinutes: 20}).protectiveExit(p, d("140"), .9, now)
	if !profit || q.ExitSince == nil || !q.ExitSince.Equal(now) {
		t.Fatalf("%+v", q)
	}
	if _, follow := (Config{ExitRampMinutes: 20}).exitOpts(q, now); !follow {
		t.Fatal("migrated latch must follow through")
	}
}
