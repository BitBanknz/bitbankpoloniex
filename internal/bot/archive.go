package bot

import (
	"context"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"sync"
	"time"
)

type ArchiveStatus struct {
	Quarantined       int
	Symbol, Interval  string
	Snapshot          time.Time
	NextEnd           int64
	Pages, Rows, Gaps int
	Complete          bool
	Earliest, Latest  int64
	CSVHash           string
	Error             string
}

func parseArchive(raw [][]json.RawMessage, now time.Time, step int64) ([]Candle, error) {
	if step == 3600000 {
		return parseCandles(raw, now)
	}
	adjusted := make([][]json.RawMessage, len(raw))
	for i, r := range raw {
		if len(r) < 14 {
			return nil, errors.New("short archive candle")
		}
		var start, end int64
		if json.Unmarshal(r[12], &start) != nil || json.Unmarshal(r[13], &end) != nil || start%step != 0 || end != start+step-1 {
			return nil, errors.New("invalid daily clock")
		}
		if end >= now.UnixMilli() {
			continue
		}
		a := append([]json.RawMessage(nil), r...)
		a[13] = json.RawMessage(fmt.Sprint(start + 3600000 - 1))
		adjusted[i] = a
	}
	out := [][]json.RawMessage{}
	for _, a := range adjusted {
		if a != nil {
			out = append(out, a)
		}
	}
	return parseCandles(out, now)
}
func (c *Client) archiveSymbol(ctx context.Context, root, symbol, interval string) (ArchiveStatus, error) {
	step := int64(3600000)
	if interval == "DAY_1" {
		step *= 24
	} else if interval != "HOUR_1" {
		return ArchiveStatus{}, errors.New("archive supports HOUR_1 and DAY_1")
	}
	dir := filepath.Join(root, symbol)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return ArchiveStatus{}, err
	}
	statusPath := filepath.Join(dir, "status.json")
	s := ArchiveStatus{Symbol: symbol, Interval: interval, Snapshot: time.Now().UTC(), NextEnd: time.Now().UnixMilli()/step*step - 1}
	if err := Load(statusPath, &s); err != nil && !os.IsNotExist(err) {
		return s, err
	}
	if s.Symbol != symbol || s.Interval != interval {
		return s, errors.New("archive schema mismatch")
	}
	s.Error = ""
	for !s.Complete {
		if err := ctx.Err(); err != nil {
			return s, err
		}
		var raw [][]json.RawMessage
		var err error
		for attempt := 0; attempt < 3; attempt++ {
			err = c.request(ctx, "GET", "/markets/"+symbol+"/candles", url.Values{"interval": {interval}, "limit": {"500"}, "endTime": {fmt.Sprint(s.NextEnd)}}, nil, false, &raw)
			if err == nil {
				break
			}
			timer := time.NewTimer(time.Duration(attempt+1) * time.Second)
			select {
			case <-ctx.Done():
				timer.Stop()
				return s, ctx.Err()
			case <-timer.C:
			}
		}
		if err != nil {
			return s, err
		}
		if len(raw) == 0 {
			s.Complete = true
			break
		}
		bars := []Candle{}
		bad := [][]json.RawMessage{}
		oldest := s.NextEnd
		for _, r := range raw {
			if len(r) < 14 {
				return s, errors.New("short archive row")
			}
			var stamp, closeStamp int64
			if json.Unmarshal(r[12], &stamp) != nil || json.Unmarshal(r[13], &closeStamp) != nil || stamp%step != 0 || closeStamp != stamp+step-1 || stamp > s.NextEnd {
				return s, errors.New("invalid archive boundary")
			}
			if stamp < oldest {
				oldest = stamp
			}
			parsed, parseErr := parseArchive([][]json.RawMessage{r}, s.Snapshot, step)
			if parseErr != nil {
				bad = append(bad, r)
			} else {
				bars = append(bars, parsed...)
			}
		}
		if len(bad) > 0 {
			if err = Save(filepath.Join(dir, fmt.Sprintf("quarantine-%d.json", s.NextEnd)), bad); err != nil {
				return s, err
			}
			s.Quarantined += len(bad)
		}
		next := oldest - 1
		if next >= s.NextEnd {
			return s, errors.New("archive cursor did not advance")
		}
		page := filepath.Join(dir, fmt.Sprintf("page-%d.json", s.NextEnd))
		if err = Save(page, bars); err != nil {
			return s, err
		}
		s.NextEnd = next
		s.Pages++
		if err = Save(statusPath, s); err != nil {
			return s, err
		}
	}
	files, err := filepath.Glob(filepath.Join(dir, "page-*.json"))
	if err != nil {
		return s, err
	}
	byTime := map[int64]Candle{}
	for _, f := range files {
		var rows []Candle
		if err = Load(f, &rows); err != nil {
			return s, err
		}
		for _, b := range rows {
			if old, ok := byTime[b.Start]; ok && old != b {
				return s, errors.New("conflicting archive candle")
			}
			byTime[b.Start] = b
		}
	}
	rows := make([]Candle, 0, len(byTime))
	for _, b := range byTime {
		rows = append(rows, b)
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].Start < rows[j].Start })
	s.Rows = len(rows)
	if len(rows) > 0 {
		s.Earliest = rows[0].Start
		s.Latest = rows[len(rows)-1].Start
	}
	s.Gaps = 0
	for i := 1; i < len(rows); i++ {
		if rows[i].Start-rows[i-1].Start != step {
			s.Gaps++
		}
	}
	tmp, err := os.CreateTemp(dir, ".csv-*")
	if err != nil {
		return s, err
	}
	defer os.Remove(tmp.Name())
	defer tmp.Close()
	w := csv.NewWriter(tmp)
	w.Write([]string{"timestamp", "open", "high", "low", "close", "quote_volume"})
	for _, b := range rows {
		r := []string{time.UnixMilli(b.Start).UTC().Format(time.RFC3339)}
		for _, v := range []float64{b.Open, b.High, b.Low, b.Close, b.Volume} {
			r = append(r, strconv.FormatFloat(v, 'g', 17, 64))
		}
		w.Write(r)
	}
	w.Flush()
	if err = w.Error(); err != nil {
		return s, err
	}
	if err = tmp.Sync(); err != nil {
		return s, err
	}
	if err = tmp.Close(); err != nil {
		return s, err
	}
	out := filepath.Join(dir, "candles.csv")
	if err = os.Rename(tmp.Name(), out); err != nil {
		return s, err
	}
	data, err := os.ReadFile(out)
	if err != nil {
		return s, err
	}
	hash := sha256.Sum256(data)
	s.CSVHash = hex.EncodeToString(hash[:])
	if err = Save(statusPath, s); err != nil {
		return s, err
	}
	log.Printf("archive %s %s: %d rows, %d gaps, complete=%v", symbol, interval, s.Rows, s.Gaps, s.Complete)
	return s, nil
}
func (c *Client) Archive(ctx context.Context, root, interval string, maxMarkets int) error {
	unlock, err := Lock(root)
	if err != nil {
		return err
	}
	defer unlock()
	markets, err := c.Universe(ctx, 100000)
	if err != nil {
		return err
	}
	if maxMarkets > 0 && len(markets) > maxMarkets {
		markets = markets[:maxMarkets]
	}
	universePath := filepath.Join(root, "universe.json")
	if _, err = os.Stat(universePath); os.IsNotExist(err) {
		if err = Save(universePath, markets); err != nil {
			return err
		}
	} else if err = Load(universePath, &markets); err != nil {
		return err
	}
	jobs := make(chan Market, len(markets))
	results := make(map[string]ArchiveStatus, len(markets))
	var mu sync.Mutex
	var wg sync.WaitGroup
	workers := 4
	if len(markets) < workers {
		workers = len(markets)
	}
	for worker := 0; worker < workers; worker++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for m := range jobs {
				s, e := c.archiveSymbol(ctx, root, m.Symbol, interval)
				if e != nil {
					s.Symbol = m.Symbol
					s.Error = e.Error()
					log.Printf("archive %s: %v", m.Symbol, e)
				}
				mu.Lock()
				results[m.Symbol] = s
				mu.Unlock()
			}
		}()
	}
	for _, m := range markets {
		jobs <- m
	}
	close(jobs)
	wg.Wait()
	if err = Save(filepath.Join(root, "manifest.json"), results); err != nil {
		return err
	}
	failed := 0
	for _, s := range results {
		if s.Error != "" {
			failed++
		}
	}
	if failed > 0 {
		return fmt.Errorf("%d archive failures; rerun to resume", failed)
	}
	return nil
}
