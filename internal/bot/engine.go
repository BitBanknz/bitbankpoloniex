package bot

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"github.com/shopspring/decimal"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

type Config struct {
	ExperimentalFallback bool
	Mode                 string
	StateDir             string
	PredictionURL        string
	Budget               decimal.Decimal
	MaxOrder             decimal.Decimal
	MinVolume            float64
	MaxSpread            float64
	FeeRate              decimal.Decimal
	MaxOrdersDay         int
	Slots                int
}

func DefaultConfig() Config {
	return Config{Mode: "paper", StateDir: "data/paper", PredictionURL: "https://bitbank.nz/api/trading-bot/rotation-signals", Budget: decimal.NewFromInt(1000), MaxOrder: decimal.NewFromInt(25), MinVolume: 100000, MaxSpread: .003, FeeRate: decimal.NewFromFloat(.003), MaxOrdersDay: 12, Slots: 4}
}
func (c Config) Validate() error {
	if c.ExperimentalFallback && c.Mode != "paper" {
		return errors.New("experimental policy is paper-only")
	}
	if c.Mode != "paper" && c.Mode != "live" {
		return errors.New("mode must be paper or live")
	}
	if !c.Budget.IsPositive() || !c.MaxOrder.IsPositive() || c.MaxOrder.GreaterThan(c.Budget.Mul(decimal.NewFromFloat(.1))) || c.Slots < 1 || c.Slots > 4 || c.MaxOrdersDay < 1 || c.MaxOrdersDay > 50 || !finite(c.MaxSpread) || c.MaxSpread <= 0 || c.MaxSpread > .01 || !finite(c.MinVolume) || c.MinVolume < 10000 || c.FeeRate.LessThan(decimal.NewFromFloat(.003)) || c.FeeRate.GreaterThan(decimal.NewFromFloat(.02)) {
		return errors.New("invalid budget or risk limits")
	}
	return nil
}

type Position struct {
	Imported bool
	Quantity decimal.Decimal
	Peak     decimal.Decimal
	Entered  time.Time
}
type Pending struct {
	Source   string
	Order    Order
	Decision string
	Created  time.Time
}
type Fill struct {
	Source                string
	ExchangeTrades        []Trade `json:",omitempty"`
	Order                 Order
	Quantity, Amount, Fee decimal.Decimal
	At                    time.Time
	Mode                  string
}
type State struct {
	AccountBacked                     bool
	Schema                            string
	Mode                              string
	Budget, Cash, HighWater, DayStart decimal.Decimal
	Day                               string
	OrdersToday                       int
	Holdings                          map[string]Position
	Processed                         map[string]bool
	Pending                           *Pending
	Fills                             []Fill
	Halted                            string
	LastCycle                         time.Time
	LastSource                        string
	Cooldown                          map[string]time.Time
	Equity                            []EquityPoint `json:",omitempty"`
}
type EquityPoint struct {
	At    time.Time
	Value decimal.Decimal
}

// Report summarises a ledger from its hourly marked equity series.
type Report struct {
	Mode, Halted, LastSource  string
	Budget, Equity, HighWater decimal.Decimal
	ReturnPct, MaxDrawdownPct float64
	Points, Fills, Holdings   int
	First, Last               time.Time
}

func Summarize(s State) Report {
	r := Report{Mode: s.Mode, Halted: s.Halted, LastSource: s.LastSource, Budget: s.Budget, HighWater: s.HighWater, Points: len(s.Equity), Fills: len(s.Fills), Holdings: len(s.Holdings)}
	if len(s.Equity) == 0 {
		r.Equity = s.Cash
		return r
	}
	r.First, r.Last, r.Equity = s.Equity[0].At, s.Equity[len(s.Equity)-1].At, s.Equity[len(s.Equity)-1].Value
	peak := s.Equity[0].Value
	for _, p := range s.Equity {
		if p.Value.GreaterThan(peak) {
			peak = p.Value
		}
		if peak.IsPositive() {
			if dd, _ := peak.Sub(p.Value).Div(peak).Mul(decimal.NewFromInt(100)).Float64(); dd > r.MaxDrawdownPct {
				r.MaxDrawdownPct = dd
			}
		}
	}
	if s.Budget.IsPositive() {
		r.ReturnPct, _ = r.Equity.Sub(s.Budget).Div(s.Budget).Mul(decimal.NewFromInt(100)).Float64()
	}
	return r
}

const maxEquityPoints = 24 * 400

func (s *State) markEquity(now time.Time, equity decimal.Decimal) {
	hour := now.UTC().Truncate(time.Hour)
	if n := len(s.Equity); n > 0 && !s.Equity[n-1].At.Before(hour) {
		s.Equity[n-1].Value = equity
		return
	}
	s.Equity = append(s.Equity, EquityPoint{At: hour, Value: equity})
	if len(s.Equity) > maxEquityPoints {
		s.Equity = append([]EquityPoint(nil), s.Equity[len(s.Equity)-maxEquityPoints:]...)
	}
}

type Engine struct {
	Client *Client
	Config Config
}

func (e *Engine) path() string { return filepath.Join(e.Config.StateDir, "state.json") }
func (e *Engine) Initialize() error {
	if err := e.Config.Validate(); err != nil {
		return err
	}
	if _, err := os.Stat(e.path()); !os.IsNotExist(err) {
		return errors.New("state exists or cannot be inspected")
	}
	s := State{Schema: "poloniex-bot-v1", Mode: e.Config.Mode, Budget: e.Config.Budget, Cash: e.Config.Budget, HighWater: e.Config.Budget, DayStart: e.Config.Budget, Holdings: map[string]Position{}, Processed: map[string]bool{}, Cooldown: map[string]time.Time{}}
	return Save(e.path(), s)
}
func (e *Engine) read() (State, error) {
	var s State
	err := Load(e.path(), &s)
	if err != nil {
		return s, err
	}
	if s.Schema != "poloniex-bot-v1" || s.Mode != e.Config.Mode || (!s.AccountBacked && !s.Budget.Equal(e.Config.Budget)) || s.Holdings == nil || s.Processed == nil || s.Cooldown == nil || s.Cash.IsNegative() || !s.HighWater.IsPositive() {
		return s, errors.New("state/config mismatch or invalid ledger")
	}
	for _, p := range s.Holdings {
		if !p.Quantity.IsPositive() || !p.Peak.IsPositive() || p.Entered.IsZero() || p.Entered.After(time.Now().Add(5*time.Second)) {
			return s, errors.New("invalid position state")
		}
	}
	return s, nil
}
func (e *Engine) accountReady(ctx context.Context) (map[string]decimal.Decimal, error) {
	m, err := e.Client.Margin(ctx)
	if err != nil {
		return nil, err
	}
	for _, v := range []string{m.Used, m.Maintenance} {
		n, err := decimal.NewFromString(v)
		if err != nil || !n.IsZero() {
			return nil, errors.New("account has margin exposure or unknown margin state")
		}
	}
	borrowed, err := e.Client.Borrowing(ctx)
	if err != nil {
		return nil, err
	}
	for _, b := range borrowed {
		v, err := decimal.NewFromString(b.Borrowed)
		if err != nil || !v.IsZero() {
			return nil, errors.New("borrowed assets present")
		}
	}
	orders, err := e.Client.OpenOrders(ctx)
	if err != nil {
		return nil, err
	}
	if len(orders) > 0 {
		return nil, errors.New("open exchange orders require reconciliation")
	}
	accounts, err := e.Client.Balances(ctx)
	if err != nil {
		return nil, err
	}
	balances := map[string]decimal.Decimal{}
	spots := 0
	for _, a := range accounts {
		if a.Type != "SPOT" {
			continue
		}
		spots++
		for _, b := range a.Balances {
			v, err := decimal.NewFromString(b.Available)
			if err != nil || v.IsNegative() {
				return nil, errors.New("negative or invalid account balance")
			}
			balances[b.Currency] = v
		}
	}
	if spots != 1 {
		return nil, errors.New("expected exactly one spot account")
	}
	return balances, nil
}
func (e *Engine) Ready(ctx context.Context) error { _, err := e.accountReady(ctx); return err }

// intentGrace is how long an unknown client order ID must stay unknown before
// a pending intent is treated as never accepted.
const intentGrace = 2 * time.Minute

func (e *Engine) resolve(ctx context.Context, s *State) error {
	if s.Pending == nil {
		return nil
	}
	p := s.Pending
	r, err := e.Client.Lookup(ctx, p.Order.ClientID)
	if err != nil {
		var he *HTTPError
		// The exchange indexes accepted orders by client ID immediately. An
		// unknown ID well after submission means the order was never accepted
		// (e.g. a rejected request), so the intent is released and the decision
		// may be retried; ambiguous transport errors still block.
		if errors.As(err, &he) && he.Status == http.StatusNotFound && !p.Created.IsZero() && time.Since(p.Created) >= intentGrace {
			delete(s.Processed, p.Decision)
			if s.OrdersToday > 0 {
				s.OrdersToday--
			}
			s.Pending = nil
			return Save(e.path(), s)
		}
		return fmt.Errorf("pending order unresolved; no resubmission: %w", err)
	}
	if r.ClientID != p.Order.ClientID || r.Symbol != p.Order.Symbol || r.Side != p.Order.Side {
		return errors.New("order reconciliation identity mismatch")
	}
	if r.State != "FILLED" && r.State != "CANCELED" && r.State != "PARTIALLY_CANCELED" {
		return errors.New("order is not terminal; new orders blocked")
	}
	qty, err := decimal.NewFromString(r.FilledQuantity)
	if err != nil || qty.IsNegative() {
		return errors.New("invalid filled quantity")
	}
	amount, err := decimal.NewFromString(r.FilledAmount)
	if err != nil || amount.IsNegative() {
		return errors.New("invalid filled amount")
	}
	ordered, _ := decimal.NewFromString(p.Order.Quantity)
	if qty.IsZero() && !amount.IsZero() {
		return errors.New("nonzero amount for zero fill")
	}
	if qty.GreaterThan(ordered) {
		return errors.New("filled quantity exceeds order")
	}
	if qty.IsPositive() {
		trades, err := e.Client.Trades(ctx, r.ID)
		if err != nil {
			return err
		}
		totalQ, totalA, quoteFee, baseFee := decimal.Zero, decimal.Zero, decimal.Zero, decimal.Zero
		otherFees := map[string]decimal.Decimal{}
		seen := map[string]bool{}
		base := strings.TrimSuffix(p.Order.Symbol, "_USDT")
		for _, t := range trades {
			if t.ID == "" || seen[t.ID] || t.OrderID != r.ID || t.Symbol != p.Order.Symbol || t.Side != p.Order.Side {
				return errors.New("invalid reconciliation trade identity")
			}
			seen[t.ID] = true
			q, eq := decimal.NewFromString(t.Quantity)
			a, ea := decimal.NewFromString(t.Amount)
			f, ef := decimal.NewFromString(t.FeeAmount)
			if eq != nil || ea != nil || ef != nil || !q.IsPositive() || !a.IsPositive() || f.IsNegative() {
				return errors.New("invalid trade amounts")
			}
			totalQ = totalQ.Add(q)
			totalA = totalA.Add(a)
			switch t.FeeCurrency {
			case "USDT":
				quoteFee = quoteFee.Add(f)
			case base:
				baseFee = baseFee.Add(f)
			default:
				// Poloniex fee-asset discounts charge in a held third asset (e.g. TRX).
				// It must come out of a tracked holding of that asset, or accounting stops.
				if !f.IsZero() {
					otherFees[t.FeeCurrency] = otherFees[t.FeeCurrency].Add(f)
				}
			}
		}
		if !totalQ.Equal(qty) || !totalA.Equal(amount) {
			return errors.New("order/trade totals not yet reconciled")
		}
		netQty := qty
		if p.Order.Side == "BUY" {
			netQty = qty.Sub(baseFee)
			if !netQty.IsPositive() || amount.Add(quoteFee).GreaterThan(s.Cash) {
				return errors.New("fill exceeds tracked cash")
			}
		} else {
			netQty = qty.Add(baseFee)
			if netQty.GreaterThan(s.Holdings[p.Order.Symbol].Quantity) {
				return errors.New("fill exceeds tracked holdings")
			}
		}
		for cur, f := range otherFees {
			pos, held := s.Holdings[cur+"_USDT"]
			if !held || pos.Quantity.LessThan(f) {
				return errors.New("third-currency fee requires operator accounting")
			}
		}
		e.apply(s, p.Order, netQty, amount, quoteFee)
		for cur, f := range otherFees {
			pos := s.Holdings[cur+"_USDT"]
			pos.Quantity = pos.Quantity.Sub(f)
			s.Holdings[cur+"_USDT"] = pos
		}
		s.Fills[len(s.Fills)-1].ExchangeTrades = trades
	}
	s.Pending = nil
	return Save(e.path(), s)
}
func (e *Engine) submit(ctx context.Context, s *State, o Order, decision, source string) error {
	s.Processed[decision] = true
	s.OrdersToday++
	s.Pending = &Pending{Order: o, Decision: decision, Created: time.Now().UTC(), Source: source}
	if err := Save(e.path(), s); err != nil {
		return err
	}
	if e.Config.Mode == "live" {
		_, err := e.Client.Place(ctx, o)
		if err != nil {
			return fmt.Errorf("submission uncertain; pending intent retained: %w", err)
		}
		return e.resolve(ctx, s)
	}
	qty, _ := decimal.NewFromString(o.Quantity)
	price, _ := decimal.NewFromString(o.Price)
	amount := qty.Mul(price)
	fee := amount.Mul(e.Config.FeeRate)
	e.apply(s, o, qty, amount, fee)
	s.Pending = nil
	return Save(e.path(), s)
}
func (e *Engine) apply(s *State, o Order, qty, amount, fee decimal.Decimal) {
	p := s.Holdings[o.Symbol]
	price, _ := decimal.NewFromString(o.Price)
	if o.Side == "BUY" {
		s.Cash = s.Cash.Sub(amount).Sub(fee)
		p.Quantity = p.Quantity.Add(qty)
		if p.Entered.IsZero() {
			p.Entered = time.Now().UTC()
			p.Peak = price
		}
	} else {
		s.Cash = s.Cash.Add(amount).Sub(fee)
		p.Quantity = p.Quantity.Sub(qty)
	}
	if p.Quantity.IsPositive() {
		s.Holdings[o.Symbol] = p
	} else {
		delete(s.Holdings, o.Symbol)
		s.Cooldown[o.Symbol] = time.Now().Add(72 * time.Hour)
	}
	source := ""
	if s.Pending != nil {
		source = s.Pending.Source
	}
	s.Fills = append(s.Fills, Fill{Source: source, Order: o, Quantity: qty, Amount: amount, Fee: fee, At: time.Now().UTC(), Mode: e.Config.Mode})
}

// ErrEntriesPaused reports a completed cycle whose entries were skipped because no
// signal source was usable; stop checks still ran and state was saved.
var ErrEntriesPaused = errors.New("BitBank unavailable and no accepted fallback; entries paused")

func (e *Engine) Cycle(ctx context.Context) error {
	if err := e.Config.Validate(); err != nil {
		return err
	}
	if _, err := os.Stat(filepath.Join(e.Config.StateDir, "STOP")); err == nil {
		return errors.New("STOP file present")
	} else if !os.IsNotExist(err) {
		return err
	}
	s, err := e.read()
	if err != nil {
		return err
	}
	if s.Pending != nil {
		if e.Config.Mode == "paper" {
			p := s.Pending
			qty, _ := decimal.NewFromString(p.Order.Quantity)
			price, _ := decimal.NewFromString(p.Order.Price)
			amount := qty.Mul(price)
			e.apply(&s, p.Order, qty, amount, amount.Mul(e.Config.FeeRate))
			s.Pending = nil
			if err = Save(e.path(), s); err != nil {
				return err
			}
		} else {
			if err = e.resolve(ctx, &s); err != nil {
				return err
			}
		}
	}
	if s.Halted != "" {
		return fmt.Errorf("ledger halted: %s", s.Halted)
	}
	markets, err := e.Client.Universe(ctx, e.Config.MinVolume)
	if err != nil {
		return err
	}
	if len(markets) == 0 {
		return errors.New("no liquid markets")
	}
	bySymbol := make(map[string]Market, len(markets))
	for _, m := range markets {
		bySymbol[m.Symbol] = m
	}
	// Keep held markets available for exits even when their volume drops.
	all, err := e.Client.Markets(ctx)
	if err != nil {
		return err
	}
	for _, m := range all {
		if _, ok := s.Holdings[m.Symbol]; ok {
			bySymbol[m.Symbol] = m
		}
	}
	books := make(map[string]Book, len(s.Holdings))
	now := time.Now()
	equity := s.Cash
	for symbol, p := range s.Holdings {
		b, err := e.Client.Book(ctx, symbol)
		if err != nil {
			return err
		}
		books[symbol] = b
		bid, _ := decimal.NewFromString(b.Bids[0])
		equity = equity.Add(p.Quantity.Mul(bid))
		if bid.GreaterThan(p.Peak) {
			p.Peak = bid
			s.Holdings[symbol] = p
		}
	}
	if equity.GreaterThan(s.HighWater) {
		s.HighWater = equity
	}
	s.markEquity(now, equity)
	day := now.UTC().Format("2006-01-02")
	if day != s.Day {
		s.Day = day
		s.OrdersToday = 0
		s.DayStart = equity
	}
	peakBand := s.HighWater.Mul(decimal.NewFromFloat(.9))
	dayBand := s.DayStart.Mul(decimal.NewFromFloat(.97))
	if equity.LessThan(peakBand) || equity.LessThan(dayBand) {
		s.Halted = "drawdown or daily loss limit; operator review required"
		_ = Save(e.path(), s)
		return errors.New(s.Halted)
	}
	prediction, predErr := FetchPrediction(ctx, e.Config.PredictionURL)
	scores := map[string]float64{}
	observed := map[string]bool{}
	source := "bitbank_rotation"
	ready := false
	decisionHour := now.UTC().Truncate(time.Hour)
	if predErr == nil {
		scores = prediction.Scores()
		for symbol := range scores {
			observed[symbol] = true
		}
		ready = !now.Before(prediction.Execution)
		decisionHour = prediction.Execution
	} else {
		source = "go_boosted_fallback"
		models := map[string]Model{}
		if Load(filepath.Join(e.Config.StateDir, "models.json"), &models) == nil {
			for _, m := range markets {
				model, ok := models[m.Symbol]
				if !ok || model.Symbol != m.Symbol || !model.Valid(now) {
					continue
				}
				bars, err := e.Client.History(ctx, m.Symbol, 200)
				if err != nil {
					continue
				}
				p, err := model.Forecast(bars, now)
				if err == nil {
					observed[m.Symbol] = true
					ready = true
					if p > RoundTripCost {
						scores[m.Symbol] = p
					}
				}
			}
		}
	}
	if predErr != nil && !ready && e.Config.ExperimentalFallback {
		candidate, err := e.Client.ResearchSignals(ctx, e.Config.StateDir, markets)
		if err == nil {
			scores = candidate.Scores
			observed = candidate.Observed
			source = candidate.Source
			ready = true
		}
	}
	ranked := Targets(scores, markets, e.Config.Slots)
	desired := make(map[string]bool, len(ranked))
	for _, symbol := range ranked {
		desired[symbol] = true
	}
	symbols := make([]string, 0, len(s.Holdings))
	for symbol := range s.Holdings {
		symbols = append(symbols, symbol)
	}
	sort.Strings(symbols)
	// Exits never remove desired holdings, so needsCash and the funding floor
	// are fixed for the whole exit scan instead of rebuilt per position.
	needsCash := false
	for target := range desired {
		if _, held := s.Holdings[target]; !held {
			needsCash = true
			break
		}
	}
	fundingFloor := s.Budget.Mul(decimal.NewFromFloat(.4)).Add(e.Config.MaxOrder.Mul(decimal.NewFromFloat(1.003)))
	// Exit only tracked bot holdings. Untracked account ETH is never sold implicitly.
	for _, symbol := range symbols {
		p := s.Holdings[symbol]
		b := books[symbol]
		bid, _ := decimal.NewFromString(b.Bids[0])
		stop := bid.LessThanOrEqual(p.Peak.Mul(decimal.NewFromFloat(.9)))
		riskOff := e.Config.ExperimentalFallback && len(desired) == 0
		fundingExit := (needsCash || riskOff) && s.AccountBacked && p.Imported && ready && !desired[symbol] && (riskOff || s.Cash.LessThan(fundingFloor))
		exit := ready && observed[symbol] && !desired[symbol] && now.Sub(p.Entered) >= 72*time.Hour
		if !stop && !exit && !fundingExit {
			continue
		}
		if err = e.trade(ctx, &s, bySymbol[symbol], b, "SELL", decisionHour, source); err != nil {
			return err
		}
	}
	if ready {
		for _, symbol := range ranked {
			activeSlots := 0
			for _, p := range s.Holdings {
				if !p.Imported {
					activeSlots++
				}
			}
			if activeSlots >= e.Config.Slots {
				break
			}
			if _, held := s.Holdings[symbol]; held || now.Before(s.Cooldown[symbol]) {
				continue
			}
			b, err := e.Client.Book(ctx, symbol)
			if err != nil {
				continue
			}
			if err = e.trade(ctx, &s, bySymbol[symbol], b, "BUY", decisionHour, source); err != nil {
				return err
			}
		}
	}
	s.LastCycle = now.UTC()
	s.LastSource = source
	if !ready {
		s.LastSource = "waiting_for_execution_or_validated_fallback"
	}
	if err = Save(e.path(), s); err != nil {
		return err
	}
	if predErr != nil && !ready {
		return ErrEntriesPaused
	}
	return nil
}
func (e *Engine) trade(ctx context.Context, s *State, m Market, b Book, side string, hour time.Time, source string) error {
	key := fmt.Sprintf("%s|%s|%s", hour.Format(time.RFC3339), m.Symbol, side)
	if s.AccountBacked && s.Holdings[m.Symbol].Imported && side == "SELL" {
		key += fmt.Sprintf("|allocation-%d", s.OrdersToday)
	}
	if s.Processed[key] || s.OrdersToday >= e.Config.MaxOrdersDay {
		return nil
	}
	if _, err := os.Stat(filepath.Join(e.Config.StateDir, "STOP")); err == nil {
		return errors.New("STOP file present")
	} else if !os.IsNotExist(err) {
		return err
	}
	hash := sha256.Sum256([]byte(e.Config.Mode + "|" + key))
	id := "bbp-" + hex.EncodeToString(hash[:20])
	limit := decimal.Min(e.Config.MaxOrder, s.Budget.Mul(decimal.NewFromFloat(.1)))
	onePlusFee := decimal.NewFromInt(1).Add(e.Config.FeeRate)
	spend := decimal.Min(limit, s.Cash.Sub(s.Budget.Mul(decimal.NewFromFloat(.4))).Div(onePlusFee))
	if side == "BUY" && !spend.IsPositive() {
		return nil
	}
	owned := s.Holdings[m.Symbol].Quantity
	o, err := BuildOrder(m, b, side, id, spend, owned, e.Config.MaxSpread)
	if err != nil {
		return nil
	}
	if side == "SELL" {
		q, _ := decimal.NewFromString(o.Quantity)
		price, _ := decimal.NewFromString(o.Price)
		maxQ := limit.Div(price).RoundFloor(int32(m.Limits.QuantityScale))
		if q.GreaterThan(maxQ) {
			o, err = BuildOrder(m, b, side, id, spend, maxQ, e.Config.MaxSpread)
			if err != nil {
				return nil
			}
		}
	}
	if e.Config.Mode == "live" {
		balances, err := e.accountReady(ctx)
		if err != nil {
			return err
		}
		qty, _ := decimal.NewFromString(o.Quantity)
		price, _ := decimal.NewFromString(o.Price)
		if side == "BUY" && balances["USDT"].LessThan(qty.Mul(price).Mul(onePlusFee)) {
			return errors.New("insufficient free USDT; existing ETH is not cash")
		}
		if side == "SELL" && balances[m.Base].LessThan(qty) {
			return errors.New("tracked holdings exceed free exchange balance")
		}
	}
	if !freshMS(b.TS, time.Now(), 30*time.Second) {
		return errors.New("book expired during preflight")
	}
	return e.submit(ctx, s, o, key, source)
}
func (e *Engine) TrainFallback(ctx context.Context, maxMarkets int) error {
	markets, err := e.Client.Universe(ctx, e.Config.MinVolume)
	if err != nil {
		return err
	}
	if maxMarkets > 0 && len(markets) > maxMarkets {
		markets = markets[:maxMarkets]
	}
	models := make(map[string]Model, len(markets))
	report := make(map[string]any, len(markets))
	var mu sync.Mutex
	jobs := make(chan Market, len(markets))
	for _, m := range markets {
		jobs <- m
	}
	close(jobs)
	var wg sync.WaitGroup
	for worker := 0; worker < 4 && worker < len(markets); worker++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for m := range jobs {
				log.Printf("validating fallback: %s", m.Symbol)
				bars, err := e.Client.History(ctx, m.Symbol, 3000)
				mu.Lock()
				if err != nil {
					report[m.Symbol] = err.Error()
					mu.Unlock()
					continue
				}
				model, err := Train(m.Symbol, bars)
				if err != nil {
					report[m.Symbol] = err.Error()
				} else {
					models[m.Symbol] = model
					report[m.Symbol] = map[string]any{"accepted": model.Accepted, "folds": model.Folds}
				}
				mu.Unlock()
			}
		}()
	}
	wg.Wait()
	if err = Save(filepath.Join(e.Config.StateDir, "validation.json"), report); err != nil {
		return err
	}
	if len(models) == 0 {
		return errors.New("no trainable markets; previous model file retained")
	}
	return Save(filepath.Join(e.Config.StateDir, "models.json"), models)
}
func (e *Engine) Status() (State, error) { return e.read() }
func AccountSummary(accounts []Account) []map[string]string {
	out := []map[string]string{}
	for _, a := range accounts {
		for _, b := range a.Balances {
			v, e := decimal.NewFromString(b.Available)
			h, he := decimal.NewFromString(b.Hold)
			if e == nil && he == nil && (!v.IsZero() || !h.IsZero()) {
				out = append(out, map[string]string{"account_type": a.Type, "currency": strings.ToUpper(b.Currency), "available": v.String(), "hold": h.String()})
			}
		}
	}
	return out
}
