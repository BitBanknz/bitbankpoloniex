package bot

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

type mockEx struct {
	mu       sync.Mutex
	t        *testing.T
	markets  map[string]Market
	books    map[string]Book
	balances map[string]decimal.Decimal
	orders   map[string]OrderResult
	trades   map[string][]Trade
	placed   []Order
	trxFee   bool
	n        int
}

func newMockEx(t *testing.T) *mockEx {
	mk := func(sym, base string, ps, qs int, px, qty string) (Market, Book) {
		m := Market{Symbol: sym, Base: base, Quote: "USDT", State: "NORMAL", Limits: Limits{PriceScale: ps, QuantityScale: qs, MinQuantity: "0.000001", MinAmount: "1", MaxQuantity: "100000000", MaxAmount: "1000000"}}
		p := d(px)
		ask := p.Add(decimal.New(1, -int32(ps))).String()
		return m, Book{Asks: []string{ask, qty, ask, qty}, Bids: []string{px, qty, px, qty}}
	}
	x := &mockEx{t: t, markets: map[string]Market{}, books: map[string]Book{}, balances: map[string]decimal.Decimal{}, orders: map[string]OrderResult{}, trades: map[string][]Trade{}, trxFee: true}
	for _, a := range [][]string{{"ETH_USDT", "ETH", "2", "6", "2000", "10"}, {"TRX_USDT", "TRX", "5", "2", "0.30000", "100000"}, {"BNB_USDT", "BNB", "2", "6", "600", "100"}} {
		var ps, qs int
		fmt.Sscan(a[2], &ps)
		fmt.Sscan(a[3], &qs)
		x.markets[a[0]], x.books[a[0]] = mk(a[0], a[1], ps, qs, a[4], a[5])
	}
	return x
}

func (x *mockEx) fee(base string, side string, qty, amount decimal.Decimal) (string, decimal.Decimal) {
	rate := d("0.0014")
	if x.trxFee {
		trx := amount.Mul(rate).Div(d("0.3")).Round(18)
		need := trx
		if base == "TRX" && side == "SELL" {
			need = trx.Add(qty)
		}
		if x.balances["TRX"].GreaterThanOrEqual(need) {
			return "TRX", trx
		}
	}
	if side == "BUY" {
		return base, qty.Mul(rate)
	}
	return "USDT", amount.Mul(rate)
}

func (x *mockEx) fill(o Order) OrderResult {
	m := x.markets[o.Symbol]
	q, p := d(o.Quantity), d(o.Price)
	amount := q.Mul(p)
	x.n++
	id := fmt.Sprint(x.n)
	cur, f := x.fee(m.Base, o.Side, q, amount)
	if o.Side == "SELL" {
		if x.balances[m.Base].LessThan(q) {
			x.t.Errorf("exchange rejects %s: balance %s < %s", o.Symbol, x.balances[m.Base], q)
			return OrderResult{}
		}
		x.balances[m.Base] = x.balances[m.Base].Sub(q)
		x.balances["USDT"] = x.balances["USDT"].Add(amount)
	} else {
		x.balances["USDT"] = x.balances["USDT"].Sub(amount)
		x.balances[m.Base] = x.balances[m.Base].Add(q)
	}
	x.balances[cur] = x.balances[cur].Sub(f)
	r := OrderResult{ID: id, ClientID: o.ClientID, Symbol: o.Symbol, Side: o.Side, State: "FILLED", FilledQuantity: q.String(), FilledAmount: amount.String()}
	x.orders[o.ClientID] = r
	x.trades[id] = []Trade{{ID: "t" + id, OrderID: id, Symbol: o.Symbol, Side: o.Side, Quantity: q.String(), Amount: amount.String(), FeeCurrency: cur, FeeAmount: f.String()}}
	return r
}

func (x *mockEx) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	x.mu.Lock()
	defer x.mu.Unlock()
	p := r.URL.Path
	var v any
	switch {
	case p == "/markets":
		ms := []Market{}
		for _, m := range x.markets {
			ms = append(ms, m)
		}
		v = ms
	case p == "/markets/ticker24h":
		ts := []Ticker{}
		for s := range x.markets {
			ts = append(ts, Ticker{Symbol: s, Amount: "10000000", TS: time.Now().UnixMilli()})
		}
		v = ts
	case strings.HasSuffix(p, "/orderBook"):
		b := x.books[strings.TrimSuffix(strings.TrimPrefix(p, "/markets/"), "/orderBook")]
		b.TS = time.Now().UnixMilli()
		v = b
	case p == "/margin/accountMargin":
		v = Margin{Used: "0", Maintenance: "0"}
	case p == "/margin/borrowStatus":
		v = []Borrow{}
	case p == "/accounts/balances":
		bs := []Balance{}
		for c, a := range x.balances {
			bs = append(bs, Balance{Currency: c, Available: a.String(), Hold: "0"})
		}
		v = []Account{{Type: "SPOT", Balances: bs}}
	case p == "/orders" && r.Method == "GET":
		v = []OrderResult{}
	case p == "/orders" && r.Method == "POST":
		var o Order
		json.NewDecoder(r.Body).Decode(&o)
		x.placed = append(x.placed, o)
		v = x.fill(o)
	case strings.HasPrefix(p, "/orders/cid:"):
		o, ok := x.orders[strings.TrimPrefix(p, "/orders/cid:")]
		if !ok {
			w.WriteHeader(404)
			return
		}
		v = o
	case strings.HasPrefix(p, "/orders/") && strings.HasSuffix(p, "/trades"):
		v = x.trades[strings.TrimSuffix(strings.TrimPrefix(p, "/orders/"), "/trades")]
	default:
		w.WriteHeader(503)
		return
	}
	json.NewEncoder(w).Encode(v)
}

func liveEngine(t *testing.T, x *mockEx) (*Engine, func()) {
	srv := httptest.NewServer(x)
	cfg := DefaultConfig()
	cfg.Mode, cfg.StateDir, cfg.Budget, cfg.MaxOrder = "live", t.TempDir(), d("500"), d("49")
	cfg.PredictionURL = srv.URL + "/prediction"
	c := NewClient("k", "s")
	c.BaseURL = srv.URL
	return &Engine{Client: c, Config: cfg}, srv.Close
}

func liveState(cash string, h map[string]Position, p *Pending) State {
	return State{Schema: "poloniex-bot-v1", Mode: "live", AccountBacked: true, Budget: d("500"), Cash: d(cash), HighWater: d("420"), DayStart: d("420"),
		Day: time.Now().UTC().Format("2006-01-02"), Holdings: h, Processed: map[string]bool{}, Cooldown: map[string]time.Time{}, Pending: p}
}

func old() time.Time { return time.Now().Add(-200 * time.Hour) }

// A filled pending sell whose fee Poloniex took from TRX the ledger does not track
// (dust left after a TRX exit) must not latch the pending intent and block the stop.
func TestUntrackedTRXFeeDoesNotBlockStops(t *testing.T) {
	x := newMockEx(t)
	x.balances["USDT"], x.balances["ETH"], x.balances["BNB"], x.balances["TRX"] = d("400"), d("0.01"), d("0.05"), d("5")
	pend := Order{Symbol: "BNB_USDT", Side: "SELL", Type: "LIMIT", TimeInForce: "IOC", AccountType: "SPOT", Price: "600", Quantity: "0.05", ClientID: "bbp-pend"}
	x.fill(pend)
	e, done := liveEngine(t, x)
	defer done()
	h := map[string]Position{"BNB_USDT": {Quantity: d("0.05"), Peak: d("600"), Entered: old()}, "ETH_USDT": {Quantity: d("0.01"), Peak: d("4000"), Entered: old()}}
	if err := Save(e.path(), liveState("400", h, &Pending{Order: pend, Decision: "dp", Created: time.Now().UTC()})); err != nil {
		t.Fatal(err)
	}
	err := e.Cycle(context.Background())
	s, _ := e.read()
	if s.Pending != nil || len(x.placed) != 1 || x.placed[0].Symbol != "ETH_USDT" || len(s.Holdings) != 0 {
		t.Fatalf("stop blocked by untracked fee: err=%v placed=%+v pending=%v holdings=%+v", err, x.placed, s.Pending, s.Holdings)
	}
	if s.Halted != "" {
		t.Fatalf("fee-sized untracked charge must not halt: %s", s.Halted)
	}
	b, _ := os.ReadFile(filepath.Join(e.Config.StateDir, "reconcile.jsonl"))
	if !strings.Contains(string(b), `"untracked_fee"`) || !strings.Contains(string(b), `"TRX"`) {
		t.Fatalf("untracked fee not recorded: %s", b)
	}
}

// Selling the whole tracked TRX holding while Poloniex charges the TRX fee from an
// untracked TRX remainder: qty+fee exceeds the ledger by the fee only.
func TestTRXExitFeeFromUntrackedRemainder(t *testing.T) {
	x := newMockEx(t)
	x.balances["USDT"], x.balances["ETH"], x.balances["TRX"] = d("400"), d("0.01"), d("145")
	pend := Order{Symbol: "TRX_USDT", Side: "SELL", Type: "LIMIT", TimeInForce: "IOC", AccountType: "SPOT", Price: "0.30000", Quantity: "140", ClientID: "bbp-trx"}
	x.fill(pend)
	if x.trades["1"][0].FeeCurrency != "TRX" {
		t.Fatal("mock must charge TRX")
	}
	e, done := liveEngine(t, x)
	defer done()
	h := map[string]Position{"TRX_USDT": {Quantity: d("140"), Peak: d("0.3"), Entered: old()}, "ETH_USDT": {Quantity: d("0.01"), Peak: d("4000"), Entered: old()}}
	if err := Save(e.path(), liveState("400", h, &Pending{Order: pend, Decision: "dt", Created: time.Now().UTC()})); err != nil {
		t.Fatal(err)
	}
	err := e.Cycle(context.Background())
	s, _ := e.read()
	if s.Pending != nil || len(x.placed) != 1 || x.placed[0].Symbol != "ETH_USDT" || len(s.Holdings) != 0 || s.Halted != "" {
		t.Fatalf("TRX exit fee blocked stops: err=%v placed=%+v pending=%v holdings=%+v halted=%q", err, x.placed, s.Pending, s.Holdings, s.Halted)
	}
	if !s.Cash.Equal(d("400").Add(d("42")).Add(d("20"))) {
		t.Fatalf("cash %s", s.Cash)
	}
}

// A fee-sized shortfall between tracked and free balance must not abort the cycle
// before later stops; the sell is clamped to the free balance and the ledger reconciled.
func TestFreeBalanceShortfallClampsAndContinues(t *testing.T) {
	for _, tc := range []struct {
		eth   string
		halt  bool
		sells int
	}{{"0.00999", false, 2}, {"0.004", true, 2}, {"0", true, 1}} {
		x := newMockEx(t)
		x.trxFee = false
		x.balances["USDT"], x.balances["ETH"], x.balances["TRX"] = d("400"), d(tc.eth), d("100")
		e, done := liveEngine(t, x)
		h := map[string]Position{"ETH_USDT": {Quantity: d("0.01"), Peak: d("4000"), Entered: old()}, "TRX_USDT": {Quantity: d("100"), Peak: d("0.5"), Entered: old()}}
		if err := Save(e.path(), liveState("400", h, nil)); err != nil {
			t.Fatal(err)
		}
		err := e.Cycle(context.Background())
		done()
		s, _ := e.read()
		syms := []string{}
		for _, o := range x.placed {
			syms = append(syms, o.Symbol)
		}
		if len(x.placed) != tc.sells || x.placed[len(x.placed)-1].Symbol != "TRX_USDT" || len(s.Holdings) != 0 || s.Pending != nil {
			t.Fatalf("eth=%s: stops not all submitted: err=%v placed=%v holdings=%+v", tc.eth, err, syms, s.Holdings)
		}
		if (s.Halted != "") != tc.halt {
			t.Fatalf("eth=%s: halted=%q", tc.eth, s.Halted)
		}
		if tc.sells == 2 && x.placed[0].Quantity != tc.eth {
			t.Fatalf("eth=%s: sell not clamped: %s", tc.eth, x.placed[0].Quantity)
		}
	}
}

// After an accounting-review halt, protective exits keep running and entries stay off.
func TestAccountingHaltKeepsProtectiveExits(t *testing.T) {
	x := newMockEx(t)
	x.balances["USDT"], x.balances["ETH"] = d("400"), d("0.01")
	e, done := liveEngine(t, x)
	defer done()
	s0 := liveState("400", map[string]Position{"ETH_USDT": {Quantity: d("0.01"), Peak: d("4000"), Entered: old()}}, nil)
	s0.Halted = accountingHaltReason
	if err := Save(e.path(), s0); err != nil {
		t.Fatal(err)
	}
	e.Cycle(context.Background())
	s, _ := e.read()
	if len(x.placed) != 1 || x.placed[0].Side != "SELL" || len(s.Holdings) != 0 || s.Halted != accountingHaltReason {
		t.Fatalf("placed=%+v holdings=%+v halted=%q", x.placed, s.Holdings, s.Halted)
	}
}
