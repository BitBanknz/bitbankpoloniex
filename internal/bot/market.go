package bot

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/shopspring/decimal"
	"math"
	"net/url"
	"sort"
	"strconv"
	"time"
)

type Limits struct {
	PriceScale    int    `json:"priceScale"`
	QuantityScale int    `json:"quantityScale"`
	MinQuantity   string `json:"minQuantity"`
	MinAmount     string `json:"minAmount"`
	MaxQuantity   string `json:"maxQuantity"`
	MaxAmount     string `json:"maxAmount"`
}
type Market struct {
	Symbol string `json:"symbol"`
	Base   string `json:"baseCurrencyName"`
	Quote  string `json:"quoteCurrencyName"`
	State  string `json:"state"`
	Limits Limits `json:"symbolTradeLimit"`
}
type Ticker struct {
	Symbol string `json:"symbol"`
	Amount string `json:"amount"`
	TS     int64  `json:"ts"`
}

func (c *Client) Markets(ctx context.Context) ([]Market, error) {
	var v []Market
	e := c.request(ctx, "GET", "/markets", nil, nil, false, &v)
	return v, e
}
func (c *Client) Universe(ctx context.Context, minVolume float64) ([]Market, error) {
	m, e := c.Markets(ctx)
	if e != nil {
		return nil, e
	}
	var ts []Ticker
	if e = c.request(ctx, "GET", "/markets/ticker24h", nil, nil, false, &ts); e != nil {
		return nil, e
	}
	now := time.Now()
	volume := make(map[string]float64, len(ts))
	for _, t := range ts {
		v, e := number(t.Amount)
		if e == nil && freshMS(t.TS, now, 5*time.Minute) {
			volume[t.Symbol] = v
		}
	}
	out := make([]Market, 0, len(m))
	for _, s := range m {
		if s.Quote == "USDT" && s.State == "NORMAL" && volume[s.Symbol] >= minVolume {
			out = append(out, s)
		}
	}
	sort.Slice(out, func(i, j int) bool {
		a, b := volume[out[i].Symbol], volume[out[j].Symbol]
		if a == b {
			return out[i].Symbol < out[j].Symbol
		}
		return a > b
	})
	return out, nil
}
func number(s string) (float64, error) {
	v, e := strconv.ParseFloat(s, 64)
	if e != nil || math.IsNaN(v) || math.IsInf(v, 0) {
		return 0, errors.New("invalid numeric value")
	}
	return v, nil
}
func freshMS(ms int64, now time.Time, age time.Duration) bool {
	return ms > 0 && ms <= now.Add(5*time.Second).UnixMilli() && ms >= now.Add(-age).UnixMilli()
}

type Book struct {
	Asks []string `json:"asks"`
	Bids []string `json:"bids"`
	Time int64    `json:"time"`
	TS   int64    `json:"ts"`
}

func (c *Client) Book(ctx context.Context, symbol string) (Book, error) {
	var b Book
	e := c.request(ctx, "GET", "/markets/"+symbol+"/orderBook", url.Values{"limit": {"5"}}, nil, false, &b)
	if e != nil {
		return b, e
	}
	if !freshMS(b.TS, time.Now(), 30*time.Second) || len(b.Asks) < 2 || len(b.Bids) < 2 {
		return b, errors.New("stale or empty book")
	}
	ask, e := number(b.Asks[0])
	if e != nil || ask <= 0 {
		return b, errors.New("bad ask")
	}
	bid, e := number(b.Bids[0])
	if e != nil || bid <= 0 || ask < bid {
		return b, errors.New("bad bid")
	}
	return b, nil
}
func BuildOrder(m Market, b Book, side, id string, quote, owned decimal.Decimal, maxSpread float64) (Order, error) {
	o := Order{Symbol: m.Symbol, Side: side, ClientID: id, Type: "LIMIT", TimeInForce: "IOC", AccountType: "SPOT"}
	now := time.Now()
	if m.State != "NORMAL" || m.Quote != "USDT" || m.Limits.PriceScale < 0 || m.Limits.PriceScale > 18 || m.Limits.QuantityScale < 0 || m.Limits.QuantityScale > 18 || len(b.Asks) < 2 || len(b.Bids) < 2 || !freshMS(b.TS, now, 30*time.Second) {
		return o, errors.New("invalid market/book")
	}
	ask, e := decimal.NewFromString(b.Asks[0])
	if e != nil || !ask.IsPositive() {
		return o, errors.New("invalid ask")
	}
	bid, e := decimal.NewFromString(b.Bids[0])
	if e != nil || !bid.IsPositive() || ask.LessThan(bid) {
		return o, errors.New("invalid bid")
	}
	spread := ask.Sub(bid).Div(bid).InexactFloat64()
	if spread > maxSpread {
		return o, errors.New("spread exceeds limit")
	}
	levels := b.Asks
	anchor := ask
	worst := ask
	if side == "SELL" {
		levels = b.Bids
		anchor = bid
		worst = bid
	} else if side != "BUY" {
		return o, errors.New("invalid side")
	}
	depth := decimal.Zero
	buyBound := anchor.Mul(decimal.NewFromFloat(1.001))
	sellBound := anchor.Mul(decimal.NewFromFloat(.999))
	for i := 0; i+1 < len(levels); i += 2 {
		levelPrice, e := decimal.NewFromString(levels[i])
		levelQty, qe := decimal.NewFromString(levels[i+1])
		if e != nil || qe != nil || !levelPrice.IsPositive() || levelQty.IsNegative() {
			return o, errors.New("invalid book level")
		}
		if side == "BUY" {
			if levelPrice.GreaterThan(buyBound) {
				break
			}
			worst = decimal.Max(worst, levelPrice)
		} else {
			if levelPrice.LessThan(sellBound) {
				break
			}
			worst = decimal.Min(worst, levelPrice)
		}
		depth = depth.Add(levelQty)
	}
	price := worst.RoundCeil(int32(m.Limits.PriceScale))
	if side == "SELL" {
		price = worst.RoundFloor(int32(m.Limits.PriceScale))
	}
	if !price.IsPositive() || !depth.IsPositive() {
		return o, errors.New("empty executable depth")
	}
	qty := quote.Div(price)
	if side == "SELL" {
		qty = owned
	}
	qty = decimal.Min(qty, depth.Mul(decimal.NewFromFloat(.1))).RoundFloor(int32(m.Limits.QuantityScale))
	if !qty.IsPositive() {
		return o, errors.New("zero size")
	}
	amount := qty.Mul(price)
	for _, lim := range []struct {
		v       string
		actual  decimal.Decimal
		maximum bool
	}{{m.Limits.MinQuantity, qty, false}, {m.Limits.MinAmount, amount, false}, {m.Limits.MaxQuantity, qty, true}, {m.Limits.MaxAmount, amount, true}} {
		v, e := decimal.NewFromString(lim.v)
		if e != nil || v.IsNegative() {
			return o, errors.New("invalid exchange limits")
		}
		if (!lim.maximum && lim.actual.LessThan(v)) || (lim.maximum && v.IsPositive() && lim.actual.GreaterThan(v)) {
			return o, errors.New("exchange size limit")
		}
	}
	o.Price = price.String()
	o.Quantity = qty.String()
	return o, nil
}

type Candle struct {
	Start                          int64
	Open, High, Low, Close, Volume float64
}

func parseCandles(raw [][]json.RawMessage, now time.Time) ([]Candle, error) {
	out := make([]Candle, 0, len(raw))
	for _, r := range raw {
		if len(r) < 14 {
			return nil, errors.New("short candle")
		}
		val := func(i int) (float64, error) {
			var s string
			if json.Unmarshal(r[i], &s) == nil {
				return number(s)
			}
			return number(string(r[i]))
		}
		start, e := val(12)
		if e != nil {
			return nil, e
		}
		closeTime, e := val(13)
		if e != nil || int64(closeTime) != int64(start)+3600000-1 || int64(start)%3600000 != 0 {
			return nil, errors.New("invalid candle clock")
		}
		if int64(closeTime) >= now.UnixMilli() {
			continue
		}
		c := Candle{Start: int64(start)}
		fields := [...]*float64{&c.Low, &c.High, &c.Open, &c.Close, &c.Volume}
		for i := range fields {
			v, e := val(i)
			if e != nil {
				return nil, e
			}
			*fields[i] = v
		}
		if c.Low <= 0 || c.High < c.Low || c.Open < c.Low || c.Open > c.High || c.Close < c.Low || c.Close > c.High || c.Volume < 0 {
			return nil, errors.New("invalid OHLC")
		}
		out = append(out, c)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Start < out[j].Start })
	return out, nil
}
func (c *Client) History(ctx context.Context, symbol string, n int) ([]Candle, error) {
	now := time.Now()
	end := now.Truncate(time.Hour).UnixMilli() - 1
	byTime := make(map[int64]Candle, n)
	for page := 0; page < (n+499)/500+1 && len(byTime) < n; page++ {
		var raw [][]json.RawMessage
		e := c.request(ctx, "GET", "/markets/"+symbol+"/candles", url.Values{"interval": {"HOUR_1"}, "limit": {"500"}, "endTime": {fmt.Sprint(end)}}, nil, false, &raw)
		if e != nil {
			return nil, e
		}
		bars, e := parseCandles(raw, now)
		if e != nil {
			return nil, e
		}
		if len(bars) == 0 {
			break
		}
		for _, b := range bars {
			byTime[b.Start] = b
		}
		next := bars[0].Start - 1
		if next >= end {
			return nil, errors.New("candle pagination did not advance")
		}
		end = next
	}
	bars := make([]Candle, 0, len(byTime))
	for _, b := range byTime {
		bars = append(bars, b)
	}
	sort.Slice(bars, func(i, j int) bool { return bars[i].Start < bars[j].Start })
	if len(bars) < n {
		return nil, errors.New("insufficient history")
	}
	bars = bars[len(bars)-n:]
	for i := 1; i < len(bars); i++ {
		if bars[i].Start-bars[i-1].Start != 3600000 {
			return nil, errors.New("candle gap")
		}
	}
	if bars[len(bars)-1].Start != now.Truncate(time.Hour).Add(-time.Hour).UnixMilli() {
		return nil, errors.New("stale candles")
	}
	return bars, nil
}
