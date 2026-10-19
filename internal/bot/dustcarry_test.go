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

	"github.com/shopspring/decimal"
)

func TestDustCarriedIntoNextBuy(t *testing.T) {
	e := engine(t)
	e.Config.Slots = 1
	now := time.Now()
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	s.Cash, s.HighWater, s.DayStart = d("990"), d("1000"), d("1000")
	s.Day = now.UTC().Format("2006-01-02")
	s.Holdings["ETH_USDT"] = Position{Quantity: d("0.00001"), Peak: d("2000"), Entered: now.Add(-100 * time.Hour)}
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
	defer srv.Close()
	e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
	if err := e.Cycle(context.Background()); err != nil {
		t.Fatal(err)
	}
	after, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if len(after.Fills) != 1 || after.Fills[0].Order.Side != "BUY" {
		t.Fatalf("no entry: %+v", after.Fills)
	}
	if want := after.Fills[0].Quantity.Add(d("0.00001")); !after.Holdings["ETH_USDT"].Quantity.Equal(want) {
		t.Fatalf("dust not folded: %s want %s", after.Holdings["ETH_USDT"].Quantity, want)
	}
	if len(after.Dust) != 0 {
		t.Fatalf("dust left after fold: %v", after.Dust)
	}
}

func TestDustStateRoundTrip(t *testing.T) {
	p := filepath.Join(t.TempDir(), "state.json")
	s := State{Schema: "x", Holdings: map[string]Position{}}
	if err := Save(p, s); err != nil {
		t.Fatal(err)
	}
	b, _ := os.ReadFile(p)
	if strings.Contains(string(b), "Dust") {
		t.Fatal("empty dust serialized")
	}
	s.Dust = map[string]decimal.Decimal{"ZEC_USDT": d("0.000786")}
	if err := Save(p, s); err != nil {
		t.Fatal(err)
	}
	var got State
	if err := Load(p, &got); err != nil || !got.Dust["ZEC_USDT"].Equal(d("0.000786")) {
		t.Fatalf("dust round trip: %v %v", err, got.Dust)
	}
}
