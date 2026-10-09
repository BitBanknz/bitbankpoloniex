package bot

import (
	"context"
	"errors"
	"fmt"
	"math"
	"time"

	"github.com/shopspring/decimal"
)

// Volatility-scaled slot sizing, ported from bitbankkucoin -size-vol/-vol-target/-dd-throttle.
// Default off (VolTarget 0, DDThrottle 0): slot targets are unchanged.
// With VolTarget > 0 each rotation slot target (entry cap and top-up goal) is
// slotTarget * min(VolMaxWeight, VolTarget/vol), vol = annualized realized vol of hourly log
// closes (VolMode rms = sqrt((v24^2+v168^2)/2), or 24 / 168). With DDThrottle > 0 it is further
// scaled by max(DDFloor, 1 - dd/DDThrottle), dd = drawdown below the ledger high-water mark.
// Holdings are never trimmed when their target falls; only new buys are sized.

var volWindows = map[string]int{"rms": 168, "24": 24, "168": 168}

type volEntry struct {
	hour int64
	vol  float64
}

func (c Config) volMode() string {
	if c.VolMode == "" {
		return "rms"
	}
	return c.VolMode
}

func (c Config) volMaxWeight() float64 {
	if c.VolMaxWeight == 0 {
		return 1
	}
	return c.VolMaxWeight
}

func (c Config) sizeScaled() bool { return c.VolTarget > 0 || c.DDThrottle > 0 }

func (c Config) validateSizing() error {
	if !finite(c.VolTarget) || c.VolTarget < 0 || c.VolTarget > 5 {
		return errors.New("vol target must be within 0-5 (annualized)")
	}
	if !finite(c.VolMaxWeight) || (c.VolMaxWeight != 0 && (c.VolMaxWeight < .1 || c.VolMaxWeight > 2)) {
		return errors.New("vol max weight must be 0 (=1) or within 0.1-2")
	}
	if _, ok := volWindows[c.volMode()]; !ok {
		return fmt.Errorf("unknown vol mode %q", c.VolMode)
	}
	if !finite(c.DDThrottle) || c.DDThrottle < 0 || c.DDThrottle > .5 || !finite(c.DDFloor) || c.DDFloor < 0 || c.DDFloor > 1 {
		return errors.New("dd throttle must be within 0-0.5 and floor within 0-1")
	}
	if c.sizeScaled() && c.mirror() {
		return errors.New("vol/dd sizing and mirror mode are exclusive")
	}
	return nil
}

// realizedVol is the annualized population std of the last n hourly log returns of closes.
func realizedVol(closes []float64, n int) (float64, bool) {
	if len(closes) < n+1 {
		return 0, false
	}
	c := closes[len(closes)-n-1:]
	s, ss := 0., 0.
	for i := 1; i < len(c); i++ {
		if c[i] <= 0 || c[i-1] <= 0 {
			return 0, false
		}
		r := math.Log(c[i] / c[i-1])
		s += r
		ss += r * r
	}
	m := s / float64(n)
	v := ss/float64(n) - m*m
	if v < 0 {
		v = 0
	}
	return math.Sqrt(v * 8760), true
}

func sizingVol(closes []float64, mode string) (float64, bool) {
	if mode != "rms" {
		return realizedVol(closes, volWindows[mode])
	}
	a, ok := realizedVol(closes, 24)
	b, ok2 := realizedVol(closes, 168)
	return math.Sqrt((a*a + b*b) / 2), ok && ok2
}

// symbolVol fetches and caches (per symbol and UTC hour) the sizing vol from completed hourly candles.
func (e *Engine) symbolVol(ctx context.Context, symbol string, now time.Time) (float64, error) {
	hour := now.UTC().Truncate(time.Hour).Unix()
	if v, ok := e.vol[symbol]; ok && v.hour == hour {
		return v.vol, nil
	}
	n := volWindows[e.Config.volMode()] + 1
	bars, err := e.Client.History(ctx, symbol, n)
	if err != nil {
		return 0, err
	}
	if len(bars) < n || bars[len(bars)-1].Start != (hour-3600)*1000 {
		return 0, fmt.Errorf("%s: stale or short candle history (%d bars)", symbol, len(bars))
	}
	closes := make([]float64, len(bars))
	for i, b := range bars {
		closes[i] = b.Close
	}
	vol, ok := sizingVol(closes, e.Config.volMode())
	if !ok || !finite(vol) || vol <= 0 {
		return 0, fmt.Errorf("%s: invalid sizing vol", symbol)
	}
	if e.vol == nil {
		e.vol = map[string]volEntry{}
	}
	e.vol[symbol] = volEntry{hour, vol}
	return vol, nil
}

// sizeScale is the slot-target multiplier for symbol (1 when sizing is off).
func (e *Engine) sizeScale(ctx context.Context, s State, equity decimal.Decimal, symbol string, now time.Time) (float64, error) {
	scale := 1.
	if e.Config.VolTarget > 0 {
		vol, err := e.symbolVol(ctx, symbol, now)
		if err != nil {
			return 0, err
		}
		scale = math.Min(e.Config.volMaxWeight(), e.Config.VolTarget/vol)
	}
	if e.Config.DDThrottle > 0 && s.HighWater.IsPositive() {
		dd, _ := decimal.NewFromInt(1).Sub(equity.Div(s.HighWater)).Float64()
		scale *= math.Max(e.Config.DDFloor, 1-math.Max(dd, 0)/e.Config.DDThrottle)
	}
	return scale, nil
}
