package bot

import (
	"errors"
	"time"

	"github.com/shopspring/decimal"
)

// Optional profit exits. Both are off by default; when off, positions record no
// entry price and every decision is byte-identical to the legacy engine.
//
// TakeProfit sells a rotation holding once its bid reaches (1+TakeProfit) x its
// average entry price, inside the minimum hold, as a protective exit. The exit
// latches (Position.Exiting) so capped sells continue until flat even if the bid
// falls back below the threshold, like a resting take-profit that has filled.
//
// TrailArm/TrailArmStop tighten the peak stop to (1-TrailArmStop) x peak once
// the peak bid reaches (1+TrailArm) x entry; the 10% peak stop stays the floor.

const (
	exitTakeProfit = "take_profit"
	exitStop       = "stop"
)

func (c Config) trackEntry() bool { return c.TakeProfit > 0 || c.TrailArm > 0 }

func (c Config) validateExits() error {
	if !finite(c.TakeProfit) || c.TakeProfit < 0 || c.TakeProfit > 10 {
		return errors.New("take-profit must be within 0-10 (fraction above entry)")
	}
	if !finite(c.TrailArm) || !finite(c.TrailArmStop) || c.TrailArm < 0 || c.TrailArm > 10 || c.TrailArmStop < 0 || c.TrailArmStop >= .5 || (c.TrailArm > 0) != (c.TrailArmStop > 0) {
		return errors.New("armed trail needs both arm (0-10) and stop (0-0.5) or neither")
	}
	if c.ExitRampMinutes < 0 || c.ExitRampMinutes > maxExitRampMinutes {
		return errors.New("exit ramp must be within 0-60 minutes")
	}
	if c.MinExitUSDT.IsNegative() || c.MinExitUSDT.GreaterThan(c.MaxOrder) {
		return errors.New("minimum exit notional must be within 0 and the maximum order")
	}
	return nil
}

// noteBuy folds a buy of qty for amount into the holding's average entry price.
// A holding that predates entry tracking, or was topped up while tracking was
// off, has a nil entry (no profit exits) rather than a stale average.
func (c Config) noteBuy(p Position, qty, amount decimal.Decimal) Position {
	if !c.trackEntry() {
		p.Entry = nil
		return p
	}
	if !qty.IsPositive() {
		return p
	}
	if p.Quantity.IsPositive() && p.Entry == nil {
		return p
	}
	cost := amount
	if p.Entry != nil {
		cost = cost.Add(p.Quantity.Mul(*p.Entry))
	}
	avg := cost.Div(p.Quantity.Add(qty))
	p.Entry = &avg
	return p
}

// protectiveExit reports whether a holding must be sold at bid by its peak stop
// (stop) or by a take-profit (profit), and returns the holding with its exit
// latch updated. With ExitRampMinutes set, a triggered stop latches
// (Exiting=stop, ExitSince) and keeps selling every cycle until flat, like a
// resting stop that has triggered, even if the bid recovers. A latch left by an
// earlier run is cleared once its feature is switched off.
func (c Config) protectiveExit(p Position, bid decimal.Decimal, stopFraction float64, now time.Time) (stop, profit bool, _ Position) {
	level := p.Peak.Mul(decimal.NewFromFloat(stopFraction))
	if c.TrailArm > 0 && p.Entry != nil && p.Peak.GreaterThanOrEqual(p.Entry.Mul(decimal.NewFromFloat(1+c.TrailArm))) {
		level = decimal.Max(level, p.Peak.Mul(decimal.NewFromFloat(1-c.TrailArmStop)))
	}
	stop = bid.LessThanOrEqual(level)
	if (p.Exiting == exitStop && c.ExitRampMinutes <= 0) || (p.Exiting == exitTakeProfit && c.TakeProfit <= 0) {
		p.Exiting, p.ExitSince = "", nil
	}
	if c.ExitRampMinutes > 0 {
		if stop && p.Exiting != exitStop {
			t := now.UTC()
			p.Exiting, p.ExitSince = exitStop, &t
		}
		if p.Exiting == exitStop {
			return true, false, p
		}
		if p.Exiting != "" && p.ExitSince == nil { // latch from a ramp-disabled run
			t := now.UTC()
			p.ExitSince = &t
		}
	}
	if c.TakeProfit <= 0 {
		return stop, false, p
	}
	if p.Entry != nil && p.Exiting == "" && bid.GreaterThanOrEqual(p.Entry.Mul(decimal.NewFromFloat(1+c.TakeProfit))) {
		p.Exiting = exitTakeProfit
		if c.ExitRampMinutes > 0 {
			t := now.UTC()
			p.ExitSince = &t
		}
	}
	return stop, p.Exiting != "" && !stop, p
}

// Protective follow-through limits (active only with ExitRampMinutes > 0).
const (
	exitRampMaxBand    = .01 // the sell band widens from 0.1% to 1% below the bid over the ramp
	protectiveExtraDay = 12  // latched exits may use this many orders beyond MaxOrdersDay
	maxExitRampMinutes = 60
)

// exitOpts sizes a sell. Every sell gets the MinExitUSDT floor; a latched
// protective exit additionally moves from the legacy 0.1% band and 10%
// participation toward exitRampMaxBand and full in-band participation over
// ExitRampMinutes since it latched (backing out toward the market, IOC limit
// only). follow reports a latched follow-up: keyed per cycle, extra order room.
func (c Config) exitOpts(p Position, now time.Time) (opts OrderOpts, follow bool) {
	opts = OrderOpts{MaxSpread: c.MaxSpread, MinQuote: c.MinExitUSDT}
	if c.ExitRampMinutes <= 0 || p.Exiting == "" || p.ExitSince == nil {
		return opts, false
	}
	frac := now.Sub(*p.ExitSince).Minutes() / float64(c.ExitRampMinutes)
	if !finite(frac) || frac < 0 {
		frac = 0
	}
	opts.Band, opts.Participation = exitRampMaxBand, 1
	if frac < 1 {
		opts.Band = .001 + frac*(exitRampMaxBand-.001)
		opts.Participation = .1 + frac*.9
	}
	if opts.Band > opts.MaxSpread {
		opts.MaxSpread = opts.Band
	}
	return opts, true
}
