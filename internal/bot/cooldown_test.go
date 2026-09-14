package bot

import (
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func TestSaleCooldownUsesConfiguredDelay(t *testing.T) {
	for _, hours := range []int{0, 72, 120} {
		cfg := DefaultConfig()
		cfg.CooldownHours = hours
		e := Engine{Config: cfg}
		s := State{Cash: decimal.NewFromInt(100), Holdings: map[string]Position{
			"ETH_USDT": {Quantity: decimal.NewFromInt(1), Peak: decimal.NewFromInt(10), Entered: time.Now().Add(-100 * time.Hour)},
		}, Cooldown: map[string]time.Time{}, Processed: map[string]bool{}}
		want := time.Duration(hours) * time.Hour
		if hours == 0 {
			want = 72 * time.Hour
		}
		start := time.Now()
		e.apply(&s, Order{Symbol: "ETH_USDT", Side: "SELL"}, decimal.NewFromInt(1), decimal.NewFromInt(10), decimal.Zero)
		end := time.Now()
		until := s.Cooldown["ETH_USDT"]
		if until.Before(start.Add(want)) || until.After(end.Add(want)) {
			t.Fatalf("hours=%d cooldown=%v", hours, until)
		}
		if _, held := s.Holdings["ETH_USDT"]; held || !s.Cash.Equal(decimal.NewFromInt(110)) {
			t.Fatal("cooldown changed fill accounting")
		}
	}
}

func TestCooldownBoundsAndRetainedDeadlines(t *testing.T) {
	for _, hours := range []int{-1, 337} {
		cfg := DefaultConfig()
		cfg.CooldownHours = hours
		if cfg.Validate() == nil {
			t.Fatalf("accepted cooldown %d", hours)
		}
	}
	e := Engine{Config: DefaultConfig()}
	e.Config.StateDir = t.TempDir()
	if err := e.Initialize(); err != nil {
		t.Fatal(err)
	}
	s, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(71 * time.Hour).UTC()
	s.Cooldown["ETH_USDT"] = deadline
	if err := Save(e.path(), s); err != nil {
		t.Fatal(err)
	}
	e.Config.CooldownHours = 120
	after, err := e.read()
	if err != nil {
		t.Fatal(err)
	}
	if !after.Cooldown["ETH_USDT"].Equal(deadline) {
		t.Fatal("config change rewrote an existing deadline")
	}
}
