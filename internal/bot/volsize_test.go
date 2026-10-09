package bot

import (
	"context"
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func TestRealizedVol(t *testing.T) {
	// alternating +/-1% log returns: population std 0.01 -> annualized 0.01*sqrt(8760)
	c := []float64{100}
	for i := 0; i < 200; i++ {
		c = append(c, c[len(c)-1]*math.Exp(.01*float64(1-2*(i%2))))
	}
	want := .01 * math.Sqrt(8760)
	for _, mode := range []string{"24", "168", "rms"} {
		v, ok := sizingVol(c, mode)
		if !ok || math.Abs(v-want) > 1e-9 {
			t.Fatalf("%s: %v %v want %v", mode, v, ok, want)
		}
	}
	if _, ok := sizingVol(c[:100], "rms"); ok {
		t.Fatal("short history accepted for rms")
	}
	if _, ok := realizedVol([]float64{1, 0, 1}, 2); ok {
		t.Fatal("non-positive close accepted")
	}
}

func TestSizingValidate(t *testing.T) {
	c := DefaultConfig()
	if c.sizeScaled() {
		t.Fatal("sizing on by default")
	}
	c.VolTarget, c.VolMaxWeight, c.VolMode, c.DDThrottle, c.DDFloor = .8, 1.5, "168", .2, .25
	if err := c.Validate(); err != nil {
		t.Fatal(err)
	}
	for _, f := range []func(*Config){
		func(c *Config) { c.VolTarget = -1 }, func(c *Config) { c.VolMaxWeight = 3 }, func(c *Config) { c.VolMode = "720" },
		func(c *Config) { c.DDThrottle = .9 }, func(c *Config) { c.DDFloor = 2 }, func(c *Config) { c.VolTarget = math.NaN() },
		func(c *Config) { c.MirrorState = "x.json" },
	} {
		b := c
		f(&b)
		if b.Validate() == nil {
			t.Fatalf("invalid sizing accepted: %+v", b)
		}
	}
}

// volCandles has constant +/-r hourly log returns, so every sizing vol is r*sqrt(8760).
func volCandles(n int, r float64) [][]any {
	start := time.Now().UTC().Truncate(time.Hour).Add(-time.Duration(n) * time.Hour).UnixMilli()
	p := 2000.
	var raw [][]any
	for i := 0; i < n; i++ {
		c := p * math.Exp(r*float64(1-2*(i%2)))
		raw = append(raw, []any{math.Min(p, c), math.Max(p, c), p, c, 1e4, 0, 0, 0, 0, 0, 0, 0, start + int64(i)*3600000, start + int64(i)*3600000 + 3600000 - 1})
		p = c
	}
	return raw
}

// The top-up goal and new-entry cap scale with min(VolMaxWeight, VolTarget/vol) and the DD throttle;
// sizing off reproduces the legacy slot target; unavailable candles block buys (fail closed).
func TestVolSizedSlotTargets(t *testing.T) {
	vol := .01 * math.Sqrt(8760) // ~0.936
	cases := []struct {
		name            string
		vt, w, ddt, ddf float64
		highWater       string
		want            float64 // expected held mark after top-ups (0 = no buys)
	}{
		{"off", 0, 0, 0, 0, "1000", 200},
		{"half", vol / 2, 1, 0, 0, "1000", 100},
		{"capped", 2 * vol, 1.5, 0, 0, "1000", 300},
		{"dd", 0, 0, .2, .25, "1100", 200 * (1 - (1-1000./1100)/.2)},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			e := engine(t)
			e.Config.SlotTopUp, e.Config.CashReserve, e.Config.MaxOrdersDay = true, .4, 50
			e.Config.VolTarget, e.Config.VolMaxWeight, e.Config.DDThrottle, e.Config.DDFloor = tc.vt, tc.w, tc.ddt, tc.ddf
			now := time.Now()
			s, err := e.read()
			if err != nil {
				t.Fatal(err)
			}
			s.Cash, s.HighWater, s.DayStart = d("990"), d(tc.highWater), d("1000")
			s.Day = now.UTC().Format("2006-01-02")
			s.Holdings["ETH_USDT"] = Position{Quantity: d("0.005"), Peak: d("2000"), Entered: now.Add(-time.Hour)}
			if err := Save(e.path(), s); err != nil {
				t.Fatal(err)
			}
			if err := Save(filepath.Join(e.Config.StateDir, "models.json"), map[string]Model{"ETH_USDT": acceptedFixture(now)}); err != nil {
				t.Fatal(err)
			}
			raw := volCandles(500, .01)
			hits := 0
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				switch {
				case r.URL.Path == "/markets":
					json.NewEncoder(w).Encode([]Market{market()})
				case r.URL.Path == "/markets/ticker24h":
					json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
				case strings.HasSuffix(r.URL.Path, "/orderBook"):
					json.NewEncoder(w).Encode(Book{Asks: []string{"2000", "10"}, Bids: []string{"2000", "10"}, TS: time.Now().UnixMilli()})
				case strings.HasSuffix(r.URL.Path, "/candles"):
					hits++
					json.NewEncoder(w).Encode(raw)
				default:
					w.WriteHeader(503)
				}
			}))
			defer srv.Close()
			e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
			for i := 0; i < 12; i++ {
				if err := e.Cycle(context.Background()); err != nil {
					t.Fatal(err)
				}
			}
			after, err := e.read()
			if err != nil {
				t.Fatal(err)
			}
			mark, _ := after.Holdings["ETH_USDT"].Quantity.Mul(d("2000")).Float64()
			if mark > tc.want+.01 || mark < tc.want-e.Config.MaxOrder.InexactFloat64()*.25-1 {
				t.Fatalf("held mark %.2f, want ~%.2f", mark, tc.want)
			}
			// the fallback model reads candles once per cycle; vol sizing adds one cached fetch per hour
			if want := 12 + map[bool]int{true: 1}[tc.vt > 0]; hits != want {
				t.Fatalf("candle fetches %d, want %d", hits, want)
			}
			if after.Cash.LessThan(e.Config.reserve(after.Budget)) {
				t.Fatal("reserve breached")
			}
		})
	}
}

// No sizing vol (candles unavailable) is an error, so Cycle skips the buy (fail closed).
func TestSizeScaleFailsClosed(t *testing.T) {
	e := engine(t)
	e.Config.VolTarget = .5
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(503) }))
	defer srv.Close()
	e.Client.BaseURL = srv.URL
	s, _ := e.read()
	if _, err := e.sizeScale(context.Background(), s, decimal.NewFromInt(1000), "ETH_USDT", time.Now()); err == nil {
		t.Fatal("sizing without candles succeeded")
	}
}
