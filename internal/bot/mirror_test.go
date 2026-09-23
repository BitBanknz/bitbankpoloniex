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

func writeMirror(t *testing.T, path string, lastBar time.Time, positions map[string]MirrorPosition) {
	t.Helper()
	raw, err := json.Marshal(map[string]any{"equity": 500.0, "positions": positions, "last_bar_ts": lastBar.Unix()})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestLoadMirrorWeightsAndStaleness(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	now := time.Now()
	bar := now.Truncate(time.Hour).Add(-time.Hour)
	writeMirror(t, path, bar, map[string]MirrorPosition{
		"ETH-USDT": {Qty: 0.08, Entry: 2000}, // 160/500 = 0.32
		"WIF-USDT": {Qty: 1, Entry: 0.25},     // dust below the minimum weight
		"BAD":      {Qty: 1, Entry: 1},
	})
	w, err := LoadMirror(path, now, 3*time.Hour, .02)
	if err != nil {
		t.Fatal(err)
	}
	if len(w) != 1 || w["ETH_USDT"] < .319 || w["ETH_USDT"] > .321 {
		t.Fatalf("weights %+v", w)
	}
	writeMirror(t, path, now.Add(-5*time.Hour), map[string]MirrorPosition{"ETH-USDT": {Qty: 0.08, Entry: 2000}})
	if _, err := LoadMirror(path, now, 3*time.Hour, .02); err == nil || !strings.Contains(err.Error(), "stale") {
		t.Fatalf("stale ledger accepted: %v", err)
	}
}

// Mirror mode buys the mirrored target toward its weighted notional without the
// daily BitBank ranks, and sells a tracked holding as soon as the ledger drops it.
func TestMirrorEntersAndExitsWithLedger(t *testing.T) {
	e := engine(t)
	e.Config.MirrorState = filepath.Join(t.TempDir(), "state.json")
	e.Config.CashReserve = 0
	e.Config.MaxOrdersDay = 30
	now := time.Now()
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	s.Cash, s.HighWater, s.DayStart = d("1000"), d("1000"), d("1000")
	s.Day = now.UTC().Format("2006-01-02")
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
	bar := now.Truncate(time.Hour).Add(-time.Hour)
	writeMirror(t, e.Config.MirrorState, bar, map[string]MirrorPosition{"ETH-USDT": {Qty: 0.05, Entry: 2000}}) // weight 0.2
	for i := 0; i < 8; i++ {
		if err := e.Cycle(context.Background()); err != nil {
			t.Fatal(err)
		}
	}
	after, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	mark := after.Holdings["ETH_USDT"].Quantity.Mul(d("2000"))
	if mark.LessThan(d("190")) || mark.GreaterThan(d("201")) || after.LastSource != "kucoin_mirror" {
		t.Fatalf("mirror entry mark %s source %s fills %d", mark, after.LastSource, len(after.Fills))
	}
	writeMirror(t, e.Config.MirrorState, bar, map[string]MirrorPosition{})
	for i := 0; i < 8; i++ {
		if err := e.Cycle(context.Background()); err != nil {
			t.Fatal(err)
		}
	}
	after, err = e.read()
	if err != nil {
		t.Fatal(err)
	}
	if _, held := after.Holdings["ETH_USDT"]; held {
		t.Fatalf("mirror exit left holding %+v", after.Holdings["ETH_USDT"])
	}
}

func TestMirrorStaleLedgerPausesEntries(t *testing.T) {
	e := engine(t)
	e.Config.MirrorState = filepath.Join(t.TempDir(), "state.json")
	now := time.Now()
	s, _ := e.read()
	s.Cash, s.HighWater, s.DayStart = d("1000"), d("1000"), d("1000")
	s.Day = now.UTC().Format("2006-01-02")
	Save(e.path(), s)
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
	e.Client.BaseURL = srv.URL
	writeMirror(t, e.Config.MirrorState, now.Add(-6*time.Hour), map[string]MirrorPosition{"ETH-USDT": {Qty: 0.05, Entry: 2000}})
	if err := e.Cycle(context.Background()); err != ErrEntriesPaused {
		t.Fatalf("stale mirror err %v", err)
	}
	after, _ := e.read()
	if len(after.Fills) != 0 {
		t.Fatalf("stale mirror traded: %+v", after.Fills)
	}
}
