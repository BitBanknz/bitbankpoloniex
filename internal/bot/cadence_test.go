package bot

import (
	"testing"
	"time"
)

func TestValidateCadence(t *testing.T) {
	day := time.Date(2026, 10, 13, 0, 0, 0, 0, time.UTC)
	base := Prediction{Available: true, Venue: "POLONIEX", Mode: "research_rank_forecast", Ranks: map[string]float64{"ETHUSDT": 1}}
	daily := base
	daily.Issued, daily.Execution = day, day.Add(time.Hour)
	if err := daily.Validate(day.Add(90 * time.Minute)); err != nil {
		t.Fatalf("legacy daily rejected: %v", err)
	}
	if daily.ValidateCadence(day.Add(90*time.Minute), CadenceHourly) == nil {
		t.Fatal("hourly consumer accepted an untagged daily issue")
	}
	hourly := base
	hourly.Cadence, hourly.Issued, hourly.Execution = CadenceHourly, day.Add(13*time.Hour), day.Add(14*time.Hour)
	if err := hourly.ValidateCadence(day.Add(14*time.Hour+5*time.Minute), CadenceHourly); err != nil {
		t.Fatalf("hourly rejected: %v", err)
	}
	if hourly.Validate(day.Add(14*time.Hour+5*time.Minute)) == nil {
		t.Fatal("daily consumer accepted an hourly issue")
	}
	if hourly.ValidateCadence(day.Add(15*time.Hour), CadenceHourly) == nil {
		t.Fatal("stale hourly issue accepted")
	}
	same := hourly
	same.Execution = same.Issued
	if err := same.ValidateCadence(day.Add(13*time.Hour+2*time.Minute), CadenceHourly); err != nil {
		t.Fatalf("zero-delay hourly rejected: %v", err)
	}
	odd := hourly
	odd.Issued = odd.Issued.Add(time.Minute)
	if odd.ValidateCadence(day.Add(14*time.Hour+5*time.Minute), CadenceHourly) == nil {
		t.Fatal("off-hour issue accepted")
	}
	if (Config{SignalCadence: "weekly"}).Validate() == nil {
		t.Fatal("unknown cadence accepted")
	}
}
