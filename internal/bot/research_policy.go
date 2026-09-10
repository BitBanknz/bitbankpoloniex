package bot

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"net/url"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

type ResearchSignal struct {
	Schema       string
	Day          time.Time
	Source       string
	Scores       map[string]float64
	Observed     map[string]bool
	RegimeOn     bool
	Evaluated    int
	Failures     []string
	LiveApproved bool
}

func (c *Client) DailyHistory(ctx context.Context, symbol string) ([]Candle, error) {
	var raw [][]json.RawMessage
	if err := c.request(ctx, "GET", "/markets/"+symbol+"/candles", url.Values{"interval": {"DAY_1"}, "limit": {"250"}}, nil, false, &raw); err != nil {
		return nil, err
	}
	bars, err := parseArchive(raw, time.Now(), 86400000)
	if err != nil {
		return nil, err
	}
	if len(bars) < 201 {
		return nil, errors.New("insufficient daily history")
	}
	for i := 1; i < len(bars); i++ {
		if bars[i].Start-bars[i-1].Start != 86400000 {
			return nil, errors.New("daily history gap")
		}
	}
	if bars[len(bars)-1].Start != time.Now().UTC().Truncate(24*time.Hour).Add(-24*time.Hour).UnixMilli() {
		return nil, errors.New("stale daily history")
	}
	return bars, nil
}
func BTCRegime(b []Candle) bool {
	if len(b) < 200 {
		return false
	}
	last := b[len(b)-1].Close
	avg := func(n int) float64 {
		sum := 0.
		for _, c := range b[len(b)-n:] {
			sum += c.Close
		}
		return sum / float64(n)
	}
	return last > avg(200) && last > avg(50)
}
func DailyTrend(b []Candle) (float64, bool) {
	if len(b) < 121 {
		return 0, false
	}
	last := len(b) - 1
	vol := make([]float64, 20)
	for i := range vol {
		vol[i] = b[last-i].Volume
	}
	sort.Float64s(vol)
	median := (vol[9] + vol[10]) / 2
	r20 := b[last].Close/b[last-20].Close - 1
	r120 := b[last].Close/b[last-120].Close - 1
	return r20, finite(r20) && finite(r120) && r20 > 0 && r120 > 0 && median >= 100000
}

// This policy was selected after comparing historical candidates. Its paper-only
// gate is separate from validated native-model promotion and cannot enable live.
func (c *Client) ResearchSignals(ctx context.Context, dir string, markets []Market) (ResearchSignal, error) {
	day := time.Now().UTC().Truncate(24 * time.Hour)
	path := filepath.Join(dir, "experimental-signals.json")
	var s ResearchSignal
	if Load(path, &s) == nil && s.Schema == "trend20-btc-paper-v1" && s.Day.Equal(day) && !s.LiveApproved && s.Observed != nil && s.Scores != nil {
		valid := true
		for _, v := range s.Scores {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				valid = false
			}
		}
		if valid {
			return s, nil
		}
	}
	btc, err := c.DailyHistory(ctx, "BTC_USDT")
	if err != nil {
		return s, err
	}
	s = ResearchSignal{Schema: "trend20-btc-paper-v1", Day: day, Source: "experimental_trend20_btc_not_live_validated", Scores: map[string]float64{}, Observed: map[string]bool{}, RegimeOn: BTCRegime(btc)}
	jobs := make(chan Market)
	var mu sync.Mutex
	var wg sync.WaitGroup
	for worker := 0; worker < 4; worker++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for m := range jobs {
				bars, e := c.DailyHistory(ctx, m.Symbol)
				mu.Lock()
				if e != nil {
					s.Failures = append(s.Failures, m.Symbol)
					mu.Unlock()
					continue
				}
				s.Evaluated++
				s.Observed[m.Symbol] = true
				score, eligible := DailyTrend(bars)
				if s.RegimeOn && eligible {
					s.Scores[m.Symbol] = score
				}
				mu.Unlock()
			}
		}()
	}
	for _, m := range markets {
		jobs <- m
	}
	close(jobs)
	wg.Wait()
	if s.Evaluated < 3 {
		return s, errors.New("insufficient fresh research market coverage")
	}
	chosen := Targets(s.Scores, markets, 3)
	filtered := map[string]float64{}
	for _, pair := range chosen {
		filtered[pair] = s.Scores[pair]
	}
	s.Scores = filtered
	sort.Strings(s.Failures)
	return s, Save(path, s)
}
