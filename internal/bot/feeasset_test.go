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

func feeAssetServer(t *testing.T, feeCurrency string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasPrefix(r.URL.Path, "/orders/cid:"):
			json.NewEncoder(w).Encode(map[string]string{"id": "1", "clientOrderId": "bbp-fee", "symbol": "ETH_USDT", "side": "SELL", "state": "FILLED", "filledQuantity": "0.02", "filledAmount": "48"})
		case strings.HasPrefix(r.URL.Path, "/trades"), strings.Contains(r.URL.Path, "/trades"):
			json.NewEncoder(w).Encode([]map[string]string{{"id": "t1", "orderId": "1", "symbol": "ETH_USDT", "side": "SELL", "quantity": "0.02", "amount": "48", "feeCurrency": feeCurrency, "feeAmount": "0.2"}})
		default:
			t.Fatalf("unexpected %s", r.URL.Path)
		}
	}))
}

func feeAssetState() State {
	return State{Mode: "live", Budget: decimal.NewFromInt(500), Cash: decimal.NewFromInt(100), HighWater: decimal.NewFromInt(500),
		Holdings:  map[string]Position{"ETH_USDT": {Quantity: decimal.NewFromFloat(0.1), Peak: decimal.NewFromInt(2400)}, "TRX_USDT": {Quantity: decimal.NewFromInt(140), Peak: decimal.NewFromFloat(0.34)}},
		Processed: map[string]bool{}, Cooldown: map[string]time.Time{},
		Pending: &Pending{Order: Order{Symbol: "ETH_USDT", Side: "SELL", ClientID: "bbp-fee", Quantity: "0.02", Price: "2400"}, Decision: "d", Created: time.Now().UTC()}}
}

func TestThirdCurrencyFeeComesFromTrackedHolding(t *testing.T) {
	srv := feeAssetServer(t, "TRX")
	defer srv.Close()
	e := &Engine{Client: &Client{BaseURL: srv.URL, Key: "k", Secret: "s", HTTP: srv.Client()}, Config: DefaultConfig()}
	e.Config.Mode, e.Config.StateDir = "live", t.TempDir()
	s := feeAssetState()
	if err := e.resolve(context.Background(), &s); err != nil {
		t.Fatal(err)
	}
	if s.Pending != nil || !s.Holdings["TRX_USDT"].Quantity.Equal(decimal.NewFromFloat(139.8)) || !s.Holdings["ETH_USDT"].Quantity.Equal(decimal.NewFromFloat(0.08)) || !s.Cash.Equal(decimal.NewFromInt(148)) {
		t.Fatalf("bad accounting: %+v cash=%s", s.Holdings, s.Cash)
	}
}

func TestThirdCurrencyFeeWithoutHoldingBlocks(t *testing.T) {
	srv := feeAssetServer(t, "BNB")
	defer srv.Close()
	e := &Engine{Client: &Client{BaseURL: srv.URL, Key: "k", Secret: "s", HTTP: srv.Client()}, Config: DefaultConfig()}
	e.Config.Mode, e.Config.StateDir = "live", t.TempDir()
	s := feeAssetState()
	if err := e.resolve(context.Background(), &s); err == nil || s.Pending == nil {
		t.Fatalf("untracked fee asset must block: %v", err)
	}
}
