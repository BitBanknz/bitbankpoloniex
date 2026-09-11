package bot

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func TestResolveReleasesNeverAcceptedIntentAfterGrace(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/orders/cid:") {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()
	dir := t.TempDir()
	e := &Engine{Client: &Client{BaseURL: srv.URL, Key: "k", Secret: "s", HTTP: srv.Client()}, Config: DefaultConfig()}
	e.Config.Mode, e.Config.StateDir = "live", dir
	order := Order{Symbol: "ETH_USDT", Side: "BUY", ClientID: "bbp-test", Quantity: "1", Price: "1"}
	s := State{Processed: map[string]bool{"d": true}, OrdersToday: 1, Budget: decimal.NewFromInt(100), Holdings: map[string]Position{}, Cooldown: map[string]time.Time{}}
	s.Pending = &Pending{Order: order, Decision: "d", Created: time.Now().UTC()}
	if err := e.resolve(context.Background(), &s); err == nil || s.Pending == nil {
		t.Fatalf("fresh unknown intent must stay pending: err=%v pending=%v", err, s.Pending)
	}
	s.Pending.Created = time.Now().UTC().Add(-intentGrace - time.Second)
	if err := e.resolve(context.Background(), &s); err != nil {
		t.Fatalf("stale unknown intent should be released: %v", err)
	}
	if s.Pending != nil || s.Processed["d"] || s.OrdersToday != 0 {
		t.Fatalf("intent not released: %+v", s)
	}
	if _, err := os.Stat(e.path()); err != nil {
		t.Fatalf("state not saved: %v", err)
	}
}
