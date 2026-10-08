package bot

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func dp(s string) *decimal.Decimal { v := d(s); return &v }

func TestExitConfigValidation(t *testing.T) {
	for _, c := range []struct {
		tp, arm, stop float64
		ok            bool
	}{{0, 0, 0, true}, {.35, 0, 0, true}, {0, .2, .05, true}, {-.1, 0, 0, false}, {11, 0, 0, false}, {0, .2, 0, false}, {0, 0, .05, false}, {0, .2, .5, false}} {
		cfg := Config{TakeProfit: c.tp, TrailArm: c.arm, TrailArmStop: c.stop}
		if err := cfg.validateExits(); (err == nil) != c.ok {
			t.Fatalf("%+v: err=%v", c, err)
		}
	}
}

func TestNoteBuyAveragesEntryOnlyWhenTracking(t *testing.T) {
	off := Config{}
	if p := off.noteBuy(Position{}, d("1"), d("100")); p.Entry != nil {
		t.Fatal("entry tracked with profit exits off")
	}
	on := Config{TakeProfit: .35}
	p := on.noteBuy(Position{}, d("1"), d("100"))
	p.Quantity = d("1")
	p = on.noteBuy(p, d("1"), d("200"))
	if p.Entry == nil || !p.Entry.Equal(d("150")) {
		t.Fatalf("average entry = %v, want 150", p.Entry)
	}
	legacy := on.noteBuy(Position{Quantity: d("1")}, d("1"), d("200"))
	if legacy.Entry != nil {
		t.Fatal("pre-tracking holding gained an entry from a top-up")
	}
	// a top-up while tracking is off drops the entry instead of leaving a stale average
	q := on.noteBuy(Position{}, d("1"), d("100"))
	q.Quantity = d("1")
	q = off.noteBuy(q, d("1"), d("200"))
	q.Quantity = d("2")
	if q = on.noteBuy(q, d("1"), d("300")); q.Entry != nil {
		t.Fatalf("stale entry after an untracked top-up: %v", q.Entry)
	}
}

func TestProtectiveExitTakeProfitLatchAndArmedTrail(t *testing.T) {
	p := Position{Quantity: d("1"), Peak: d("140"), Entry: dp("100")}
	if stop, profit, q := (Config{}).protectiveExit(p, d("140"), .9); stop || profit || q.Exiting != "" {
		t.Fatal("exit fired with profit exits off")
	}
	latched := p
	latched.Exiting = exitTakeProfit
	if stop, profit, q := (Config{}).protectiveExit(latched, d("140"), .9); stop || profit || q.Exiting != "" {
		t.Fatal("stale take-profit latch survived switching the take-profit off")
	}
	cfg := Config{TakeProfit: .35}
	if _, profit, _ := cfg.protectiveExit(p, d("134.99"), .9); profit {
		t.Fatal("take-profit fired below threshold")
	}
	stop, profit, q := cfg.protectiveExit(p, d("135"), .9)
	if stop || !profit || q.Exiting != exitTakeProfit {
		t.Fatal("take-profit did not fire at threshold")
	}
	if _, profit, _ := cfg.protectiveExit(q, d("130"), .9); !profit {
		t.Fatal("latched take-profit stopped selling after the bid fell back")
	}
	if stop, profit, _ := cfg.protectiveExit(q, d("120"), .9); !stop || profit {
		t.Fatal("a latched take-profit that falls through the peak stop must rank as a stop")
	}
	if _, profit, _ := cfg.protectiveExit(Position{Quantity: d("1"), Peak: d("200")}, d("199"), .9); profit {
		t.Fatal("take-profit fired without an entry price")
	}
	trail := Config{TrailArm: .2, TrailArmStop: .05}
	if stop, _, _ := trail.protectiveExit(Position{Quantity: d("1"), Peak: d("115"), Entry: dp("100")}, d("109"), .9); stop {
		t.Fatal("trail tightened before the arm")
	}
	if stop, _, _ := trail.protectiveExit(Position{Quantity: d("1"), Peak: d("130"), Entry: dp("100")}, d("123.5"), .9); !stop {
		t.Fatal("armed trail did not stop at 5% below peak")
	}
	if stop, _, _ := trail.protectiveExit(Position{Quantity: d("1"), Peak: d("130"), Entry: dp("100")}, d("123.6"), .9); stop {
		t.Fatal("armed trail stopped above its level")
	}
	if stop, _, _ := trail.protectiveExit(Position{Quantity: d("1"), Peak: d("130"), Entry: dp("100")}, d("117"), .9); !stop {
		t.Fatal("base 10% stop lost under the armed trail")
	}
}

// A take-profit sells inside the minimum hold and blocks a same-cycle top-up; with it off the
// cycle leaves the holding alone and the state file carries no entry field.
func TestTakeProfitSellsInsideMinHold(t *testing.T) {
	for _, tp := range []float64{0, .6, .35} {
		e := engine(t)
		e.Config.TakeProfit = tp
		now := time.Now()
		s, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		s.Cash, s.HighWater, s.DayStart, s.Day = d("960"), d("1000"), d("1000"), now.UTC().Format("2006-01-02")
		p := Position{Quantity: d("0.01"), Peak: d("2000"), Entered: now.Add(-time.Hour)}
		if tp > 0 {
			p.Entry = dp("1450") // bid 2000 = +37.9%
		}
		s.Holdings["ETH_USDT"] = p
		if err := Save(e.path(), s); err != nil {
			t.Fatal(err)
		}
		eth := market()
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch {
			case r.URL.Path == "/markets":
				json.NewEncoder(w).Encode([]Market{eth})
			case r.URL.Path == "/markets/ticker24h":
				json.NewEncoder(w).Encode([]Ticker{{Symbol: eth.Symbol, Amount: "1000000", TS: time.Now().UnixMilli()}})
			case strings.HasSuffix(r.URL.Path, "/orderBook"):
				json.NewEncoder(w).Encode(book())
			default:
				w.WriteHeader(503)
			}
		}))
		e.Client.BaseURL, e.Config.PredictionURL = srv.URL, srv.URL+"/prediction"
		_ = e.Cycle(context.Background())
		srv.Close()
		after, err := e.read()
		if err != nil {
			t.Fatal(err)
		}
		sold := len(after.Fills) == 1 && after.Fills[0].Order.Side == "SELL"
		if sold != (tp == .35) {
			t.Fatalf("tp=%v sold=%v fills=%+v", tp, sold, after.Fills)
		}
		raw, _ := json.Marshal(after)
		if tp == 0 && (strings.Contains(string(raw), `"Entry"`) || strings.Contains(string(raw), `"Exiting"`)) {
			t.Fatal("profit-exit fields serialized with the feature off")
		}
	}
}
