package bot

import (
	"testing"
	"time"
)

func TestMinHoldDefaultsAndBounds(t *testing.T) {
	for hours, want := range map[int]time.Duration{0: 72 * time.Hour, 24: 24 * time.Hour, 120: 120 * time.Hour} {
		cfg := DefaultConfig()
		cfg.MinHoldHours = hours
		if err := cfg.Validate(); err != nil {
			t.Fatalf("hours=%d: %v", hours, err)
		}
		if got := cfg.minHold(); got != want {
			t.Fatalf("hours=%d minHold=%v want %v", hours, got, want)
		}
	}
	for _, hours := range []int{-1, 337} {
		cfg := DefaultConfig()
		cfg.MinHoldHours = hours
		if cfg.Validate() == nil {
			t.Fatalf("accepted minimum hold %d", hours)
		}
	}
}
