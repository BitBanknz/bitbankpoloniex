package bot

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestThresholdPolicyEntersAboveAndExitsBelow(t *testing.T) {
	for _, policy := range []bool{true, false} {
		e := engine(t)
		e.Config.SignalCadence, e.Config.MinHoldHours, e.Config.Slots = CadenceHourly, 24, 3
		e.Config.ThresholdPolicy, e.Config.EntryMin, e.Config.ExitBelow = policy, .005, -.005
		if err := e.Config.Validate(); err != nil {
			t.Fatal(err)
		}
		now := time.Now()
		s, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		s.Cash, s.HighWater, s.DayStart, s.Day = d("960"), d("1000"), d("1000"), now.UTC().Format("2006-01-02")
		s.Holdings["BBB_USDT"] = Position{Quantity: d("0.005"), Peak: d("2000"), Entered: now.Add(-30 * time.Hour)}
		s.Holdings["ETH_USDT"] = Position{Quantity: d("0.005"), Peak: d("2000"), Entered: now.Add(-30 * time.Hour)}
		if err := Save(e.path(), s); err != nil {
			t.Fatal(err)
		}
		ms := []Market{market(), market(), market(), market()}
		for i, b := range []string{"AAA", "BBB", "CCC"} {
			ms[i].Symbol, ms[i].Base = b+"_USDT", b
		}
		hour := now.UTC().Truncate(time.Hour)
		pred := Prediction{Available: true, Venue: "POLONIEX", Mode: "research_rank_forecast", Cadence: CadenceHourly, Issued: hour.Add(-time.Hour), Execution: hour,
			Ranks: map[string]float64{"AAAUSDT": .01, "BBBUSDT": .002, "CCCUSDT": .001, "ETHUSDT": -.01}}
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch {
			case r.URL.Path == "/markets":
				json.NewEncoder(w).Encode(ms)
			case r.URL.Path == "/markets/ticker24h":
				var ts []Ticker
				for _, m := range ms {
					ts = append(ts, Ticker{Symbol: m.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()})
				}
				json.NewEncoder(w).Encode(ts)
			case strings.HasSuffix(r.URL.Path, "/orderBook"):
				json.NewEncoder(w).Encode(book())
			case r.URL.Path == "/prediction":
				json.NewEncoder(w).Encode(pred)
			default:
				w.WriteHeader(503)
			}
		}))
		e.Client.BaseURL, e.Config.PredictionURL = srv.URL, "http://127.0.0.1:"+strings.Split(srv.URL, ":")[2]+"/prediction"
		if err := e.Cycle(context.Background()); err != nil {
			srv.Close()
			t.Fatal(err)
		}
		srv.Close()
		after, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		_, eth := after.Holdings["ETH_USDT"]
		_, bbb := after.Holdings["BBB_USDT"]
		_, aaa := after.Holdings["AAA_USDT"]
		_, ccc := after.Holdings["CCC_USDT"]
		if policy && (eth || !bbb || !aaa || ccc) {
			t.Fatalf("threshold policy: eth=%v bbb=%v aaa=%v ccc=%v fills=%+v", eth, bbb, aaa, ccc, after.Fills)
		}
		// legacy top-3 rotation: ETH (4th) exits, BBB stays, AAA and CCC (top 3) are bought
		if !policy && (eth || !bbb || !aaa || !ccc) {
			t.Fatalf("legacy policy: eth=%v bbb=%v aaa=%v ccc=%v fills=%+v", eth, bbb, aaa, ccc, after.Fills)
		}
	}
}

func TestThresholdPolicyValidation(t *testing.T) {
	for _, c := range [][2]float64{{.005, .005}, {-.01, 0}, {.6, 0}, {.01, -.6}} {
		cfg := DefaultConfig()
		cfg.ThresholdPolicy, cfg.EntryMin, cfg.ExitBelow = true, c[0], c[1]
		if cfg.Validate() == nil {
			t.Fatalf("accepted %v", c)
		}
	}
}
