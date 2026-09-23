package bot

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"
)

// MirrorPosition is the subset of a bitbankkucoin paper-ledger position the mirror needs.
type MirrorPosition struct {
	Qty   float64 `json:"Qty"`
	Entry float64 `json:"Entry"`
}

type mirrorLedger struct {
	Equity    float64                   `json:"equity"`
	Positions map[string]MirrorPosition `json:"positions"`
	LastBarTS int64                     `json:"last_bar_ts"`
}

// LoadMirror reads a bitbankkucoin paper ledger and returns target weights keyed by
// Poloniex symbol (BTC-USDT -> BTC_USDT). A ledger whose last processed bar closed more
// than maxAge ago is rejected so a stalled signal runner cannot hold stale targets.
func LoadMirror(path string, now time.Time, maxAge time.Duration, minWeight float64) (map[string]float64, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var l mirrorLedger
	if err := json.Unmarshal(raw, &l); err != nil {
		return nil, fmt.Errorf("mirror ledger: %w", err)
	}
	if !finite(l.Equity) || l.Equity <= 0 || l.LastBarTS <= 0 {
		return nil, errors.New("mirror ledger has no equity or processed bar")
	}
	closed := time.Unix(l.LastBarTS, 0).Add(time.Hour)
	if now.Sub(closed) > maxAge || closed.After(now.Add(time.Hour)) {
		return nil, fmt.Errorf("mirror ledger stale: last bar closed %s", closed.UTC().Format(time.RFC3339))
	}
	out := map[string]float64{}
	for sym, p := range l.Positions {
		if !strings.HasSuffix(sym, "-USDT") || !finite(p.Qty) || !finite(p.Entry) || p.Qty <= 0 || p.Entry <= 0 {
			continue
		}
		w := p.Qty * p.Entry / l.Equity
		if w < minWeight {
			continue
		}
		out[strings.TrimSuffix(sym, "-USDT")+"_USDT"] = w
	}
	return out, nil
}
