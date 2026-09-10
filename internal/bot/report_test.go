package bot

import (
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func TestSummarizeAndMarkEquity(t *testing.T) {
	s := State{Budget: decimal.NewFromInt(1000), Cash: decimal.NewFromInt(1000)}
	if r := Summarize(s); r.Points != 0 || !r.Equity.Equal(decimal.NewFromInt(1000)) {
		t.Fatalf("empty summary %+v", r)
	}
	t0 := time.Date(2026, 9, 10, 1, 10, 0, 0, time.UTC)
	s.markEquity(t0, decimal.NewFromInt(1000))
	s.markEquity(t0.Add(20*time.Minute), decimal.NewFromInt(1100))
	s.markEquity(t0.Add(time.Hour), decimal.NewFromInt(880))
	s.markEquity(t0.Add(2*time.Hour), decimal.NewFromInt(990))
	if len(s.Equity) != 3 {
		t.Fatalf("same-hour marks must overwrite, got %d points", len(s.Equity))
	}
	r := Summarize(s)
	if r.ReturnPct != -1 || r.MaxDrawdownPct != 20 || r.Points != 3 {
		t.Fatalf("bad report %+v", r)
	}
	for i := 0; i < maxEquityPoints+5; i++ {
		s.markEquity(t0.Add(time.Duration(3+i)*time.Hour), decimal.NewFromInt(990))
	}
	if len(s.Equity) != maxEquityPoints {
		t.Fatalf("history not capped: %d", len(s.Equity))
	}
}
