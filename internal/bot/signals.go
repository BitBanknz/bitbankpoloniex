package bot

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

type Prediction struct {
	Available bool               `json:"available"`
	Venue     string             `json:"venue"`
	Mode      string             `json:"mode"`
	Issued    time.Time          `json:"issued_at"`
	Execution time.Time          `json:"execution_hour"`
	Ranks     map[string]float64 `json:"rank_scores"`
}

var predClient = &http.Client{Timeout: 15 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("prediction redirect refused") }}

func FetchPrediction(ctx context.Context, endpoint string) (Prediction, error) {
	var p Prediction
	u, e := url.Parse(endpoint)
	if e != nil || u.User != nil || (u.Scheme != "https" && !(u.Scheme == "http" && (u.Hostname() == "127.0.0.1" || u.Hostname() == "localhost"))) {
		return p, errors.New("prediction endpoint must use HTTPS or loopback")
	}
	req, e := http.NewRequestWithContext(ctx, "GET", endpoint, nil)
	if e != nil {
		return p, e
	}
	r, e := predClient.Do(req)
	if e != nil {
		return p, errors.New("BitBank unavailable")
	}
	defer r.Body.Close()
	if r.StatusCode != 200 {
		return p, errors.New("BitBank prediction unavailable")
	}
	raw, e := io.ReadAll(io.LimitReader(r.Body, 1<<20+1))
	if e != nil || len(raw) > 1<<20 {
		return p, errors.New("invalid prediction response")
	}
	if e = json.Unmarshal(raw, &p); e != nil {
		return p, errors.New("invalid prediction JSON")
	}
	return p, p.Validate(time.Now())
}
func (p Prediction) Validate(now time.Time) error {
	if !p.Available || p.Venue != "POLONIEX" || p.Mode != "research_rank_forecast" || len(p.Ranks) == 0 || p.Issued.Unix()%86400 != 0 || !p.Execution.Equal(p.Issued.Add(time.Hour)) || now.Before(p.Issued) || !now.Before(p.Execution.Add(time.Hour)) {
		return errors.New("stale or invalid BitBank ranks")
	}
	for symbol, score := range p.Ranks {
		if !strings.HasSuffix(symbol, "USDT") || strings.ContainsAny(symbol, "/ ._-?") || !finite(score) {
			return errors.New("invalid rank entry")
		}
	}
	return nil
}
func Targets(scores map[string]float64, markets []Market, slots int) []string {
	eligible := make(map[string]bool, len(markets))
	for _, m := range markets {
		eligible[m.Symbol] = true
	}
	symbols := make([]string, 0, len(scores))
	for s, v := range scores {
		if eligible[s] && finite(v) {
			symbols = append(symbols, s)
		}
	}
	sort.Slice(symbols, func(i, j int) bool {
		a, b := scores[symbols[i]], scores[symbols[j]]
		if a == b {
			return symbols[i] < symbols[j]
		}
		return a > b
	})
	if len(symbols) > slots {
		symbols = symbols[:slots]
	}
	return symbols
}
func (p Prediction) Scores() map[string]float64 {
	m := make(map[string]float64, len(p.Ranks))
	for s, v := range p.Ranks {
		m[strings.TrimSuffix(s, "USDT")+"_USDT"] = v
	}
	return m
}
