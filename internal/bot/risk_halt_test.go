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

func TestDrawdownHaltStillRunsProtectiveStops(t *testing.T) {
	for _, persisted := range []bool{false, true} {
		e := engine(t)
		s, _ := e.read()
		s.Cash, s.HighWater = d("800"), d("1000")
		s.Holdings["ETH_USDT"] = Position{Quantity: d("0.01"), Peak: d("4000"), Entered: time.Now().Add(-100 * time.Hour)}
		if persisted {
			s.Halted = "drawdown or daily loss limit; operator review required"
		}
		if err := Save(e.path(), s); err != nil {
			t.Fatal(err)
		}
		signalRequests := 0
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch r.URL.Path {
			case "/markets":
				json.NewEncoder(w).Encode([]Market{market()})
			case "/markets/ticker24h":
				json.NewEncoder(w).Encode([]Ticker{{Symbol: "ETH_USDT", Amount: "1000000", TS: time.Now().UnixMilli()}})
			case "/markets/ETH_USDT/orderBook":
				json.NewEncoder(w).Encode(book())
			case "/prediction":
				signalRequests++
				w.WriteHeader(503)
			default:
				w.WriteHeader(503)
			}
		}))
		e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
		err := e.Cycle(context.Background())
		srv.Close()
		if err == nil || (!strings.Contains(err.Error(), "halt") && !strings.Contains(err.Error(), "drawdown")) {
			t.Fatalf("missing retained halt: %v", err)
		}
		after, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		if len(after.Fills) != 1 || after.Fills[0].Order.Side != "SELL" || len(after.Holdings) != 0 {
			t.Fatalf("persisted=%t: drawdown halt disabled protective sale: fills=%+v holdings=%+v", persisted, after.Fills, after.Holdings)
		}
		if after.Halted == "" || signalRequests != 0 {
			t.Fatal("halt must remain latched with no signal/entry work")
		}
	}
}

func TestHaltedLedgerCannotOpenThroughTrade(t *testing.T) {
	e := engine(t)
	s, _ := e.read()
	s.Halted = "drawdown or daily loss limit; operator review required"
	if err := e.trade(context.Background(), &s, market(), book(), "BUY", time.Now(), "test"); err == nil {
		t.Fatal("halted ledger admitted an entry")
	}
	if s.Pending != nil || len(s.Fills) != 0 || len(s.Holdings) != 0 {
		t.Fatal("entry guard changed account state")
	}
}
