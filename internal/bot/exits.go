package bot

import (
	"errors"

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

const exitTakeProfit = "take_profit"

func (c Config) trackEntry() bool { return c.TakeProfit > 0 || c.TrailArm > 0 }

func (c Config) validateExits() error {
	if !finite(c.TakeProfit) || c.TakeProfit < 0 || c.TakeProfit > 10 {
		return errors.New("take-profit must be within 0-10 (fraction above entry)")
	}
	if !finite(c.TrailArm) || !finite(c.TrailArmStop) || c.TrailArm < 0 || c.TrailArm > 10 || c.TrailArmStop < 0 || c.TrailArmStop >= .5 || (c.TrailArm > 0) != (c.TrailArmStop > 0) {
		return errors.New("armed trail needs both arm (0-10) and stop (0-0.5) or neither")
	}
	return nil
}

// noteBuy folds a buy of qty for amount into the holding's average entry price.
// A holding that predates entry tracking keeps a nil entry (no profit exits).
func (c Config) noteBuy(p Position, qty, amount decimal.Decimal) Position {
	if !c.trackEntry() || !qty.IsPositive() {
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

// protectiveExit reports whether a holding must be protectively sold at bid
// given the base peak-stop fraction, and returns the holding with any
// take-profit latch set.
func (c Config) protectiveExit(p Position, bid decimal.Decimal, stopFraction float64) (bool, Position) {
	level := p.Peak.Mul(decimal.NewFromFloat(stopFraction))
	if c.TrailArm > 0 && p.Entry != nil && p.Peak.GreaterThanOrEqual(p.Entry.Mul(decimal.NewFromFloat(1+c.TrailArm))) {
		level = decimal.Max(level, p.Peak.Mul(decimal.NewFromFloat(1-c.TrailArmStop)))
	}
	stop := bid.LessThanOrEqual(level)
	if c.TakeProfit > 0 && p.Entry != nil && p.Exiting == "" && bid.GreaterThanOrEqual(p.Entry.Mul(decimal.NewFromFloat(1+c.TakeProfit))) {
		p.Exiting = exitTakeProfit
	}
	return stop || p.Exiting != "", p
}
