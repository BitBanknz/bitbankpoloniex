package main

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/lee101/bitbankpoloniex/internal/bot"
)

func drive(errs []error) error {
	tick := make(chan time.Time, len(errs))
	i := 0
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	return runLoop(ctx, func(context.Context) error {
		if i >= len(errs) {
			cancel()
			return nil
		}
		e := errs[i]
		i++
		tick <- time.Time{}
		return e
	}, tick)
}

func TestRunLoopPausedNeverOpensCircuit(t *testing.T) {
	errs := make([]error, 100)
	for i := range errs {
		errs[i] = bot.ErrEntriesPaused
	}
	if err := drive(errs); err != nil {
		t.Fatalf("paused cycles opened the circuit: %v", err)
	}
}

func TestRunLoopRealFailuresOpenCircuit(t *testing.T) {
	boom := errors.New("boom")
	if err := drive([]error{boom, boom, boom, boom, boom}); err == nil {
		t.Fatal("expected circuit open")
	}
	if err := drive([]error{boom, boom, boom, boom, bot.ErrEntriesPaused, boom, boom}); err != nil {
		t.Fatalf("paused cycle should reset failures: %v", err)
	}
	if err := drive([]error{boom, boom, nil, boom, boom, boom, boom}); err != nil {
		t.Fatalf("success should reset failures: %v", err)
	}
}
