package bot

import (
	"context"
	"errors"
	"github.com/shopspring/decimal"
	"os"
	"path/filepath"
	"time"
)

type MarginPaper struct {
	Mode                                                               string
	InitialEquity, Cash, Debt, InterestPaid, HourlyRate, Equity, Gross decimal.Decimal
	Holdings                                                           map[string]decimal.Decimal
	Collateral                                                         map[string]decimal.Decimal
	LastAccrual                                                        time.Time
	Opened                                                             map[string]bool
	Fills                                                              []Order
	Halted                                                             string
}

func (s *MarginPaper) Accrue(now time.Time) error {
	if now.Before(s.LastAccrual) || s.HourlyRate.IsNegative() || s.Debt.IsNegative() {
		return errors.New("invalid margin accrual clock/rate")
	}
	interest := s.Debt.Mul(s.HourlyRate).Mul(decimal.NewFromFloat(now.Sub(s.LastAccrual).Hours()))
	s.Debt = s.Debt.Add(interest)
	s.InterestPaid = s.InterestPaid.Add(interest)
	s.LastAccrual = now
	return nil
}

// MarginPaperStep models an explicit order, without ever invoking Place. A
// separate ledger keeps principal, interest and existing collateral identifiable.
func (c *Client) MarginPaperStep(ctx context.Context, dir, symbol string, amount decimal.Decimal) (MarginPaper, error) {
	unlock, err := Lock(dir)
	if err != nil {
		return MarginPaper{}, err
	}
	defer unlock()
	path := filepath.Join(dir, "margin-paper.json")
	s := MarginPaper{}
	err = Load(path, &s)
	if os.IsNotExist(err) {
		snapshot, e := c.FundingSnapshot(ctx)
		if e != nil {
			return s, e
		}
		for _, b := range snapshot.Borrowing {
			v, e := decimal.NewFromString(b.Borrowed)
			if e != nil || !v.IsZero() {
				return s, errors.New("existing debt cannot be omitted from paper initialization")
			}
		}
		s = MarginPaper{Mode: "margin_paper", InitialEquity: snapshot.PricedFreeEquity, Cash: snapshot.FreeUSDT, Holdings: map[string]decimal.Decimal{}, Collateral: map[string]decimal.Decimal{}, Opened: map[string]bool{}, LastAccrual: time.Now().UTC()}
		for _, a := range snapshot.Assets {
			if a.Excluded == "" && a.Symbol != "" {
				s.Holdings[a.Symbol] = a.Available
				s.Collateral[a.Symbol] = a.Available
			}
		}
		if e = Save(filepath.Join(dir, "initial-account.json"), snapshot); e != nil {
			return s, e
		}
	} else if err != nil {
		return s, err
	}
	if s.Mode != "margin_paper" || s.Holdings == nil || s.Opened == nil || !s.InitialEquity.IsPositive() {
		return s, errors.New("invalid margin paper state")
	}
	if s.Halted != "" {
		return s, errors.New(s.Halted)
	}
	if err = s.Accrue(time.Now().UTC()); err != nil {
		return s, err
	}
	gross := decimal.Zero
	for pair, qty := range s.Holdings {
		book, e := c.Book(ctx, pair)
		if e != nil {
			return s, e
		}
		bid, _ := decimal.NewFromString(book.Bids[0])
		gross = gross.Add(qty.Mul(bid))
	}
	s.Gross = gross
	s.Equity = s.Cash.Add(gross).Sub(s.Debt)
	if s.Debt.IsPositive() && (!s.Equity.IsPositive() || s.Equity.LessThan(gross.Mul(decimal.NewFromFloat(.2))) || gross.GreaterThan(s.Equity.Mul(decimal.NewFromFloat(1.25)))) {
		s.Halted = "margin buffer or leverage limit; simulated orders halted"
		if err = Save(path, s); err != nil {
			return s, err
		}
		return s, errors.New(s.Halted)
	}
	if s.Opened[symbol] {
		return s, Save(path, s)
	}
	plan, err := c.PlanFunding(ctx, symbol, "margin", amount)
	if err != nil {
		return s, err
	}
	max := decimal.Min(plan.AllowedQuote, s.Equity.Mul(decimal.NewFromFloat(.05))).Div(decimal.NewFromFloat(1.003))
	if !max.IsPositive() {
		return s, errors.New("no margin capacity")
	}
	markets, err := c.Markets(ctx)
	if err != nil {
		return s, err
	}
	var market Market
	for _, m := range markets {
		if m.Symbol == symbol {
			market = m
		}
	}
	book, err := c.Book(ctx, symbol)
	if err != nil {
		return s, err
	}
	o, err := BuildOrder(market, book, "BUY", "margin-paper-"+symbol, max, decimal.Zero, .003)
	if err != nil {
		return s, err
	}
	q, _ := decimal.NewFromString(o.Quantity)
	p, _ := decimal.NewFromString(o.Price)
	cost := q.Mul(p).Mul(decimal.NewFromFloat(1.003))
	borrow := decimal.Max(decimal.Zero, cost.Sub(s.Cash))
	newDebt := s.Debt.Add(borrow)
	newGross := gross.Add(q.Mul(p))
	newEquity := s.Equity.Sub(q.Mul(p).Mul(decimal.NewFromFloat(.003)))
	if newGross.GreaterThan(newEquity.Mul(decimal.NewFromFloat(1.25))) || newDebt.GreaterThan(newEquity.Mul(decimal.NewFromFloat(.25))) {
		return s, errors.New("new order exceeds paper margin cap")
	}
	borrowPlan := decimal.Max(decimal.Zero, plan.AllowedQuote.Sub(plan.Snapshot.FreeUSDT))
	if borrow.IsPositive() && borrowPlan.IsPositive() {
		s.HourlyRate = plan.HourlyInterestStress.Div(borrowPlan)
	}
	s.Cash = decimal.Max(decimal.Zero, s.Cash.Sub(cost))
	s.Debt = newDebt
	s.Holdings[symbol] = s.Holdings[symbol].Add(q)
	s.Gross = newGross
	s.Equity = newEquity
	s.Opened[symbol] = true
	o.AllowBorrow = borrow.IsPositive()
	s.Fills = append(s.Fills, o)
	return s, Save(path, s)
}

func (c *Client) MarginPaperClose(ctx context.Context, dir, symbol string) (MarginPaper, error) {
	unlock, err := Lock(dir)
	if err != nil {
		return MarginPaper{}, err
	}
	defer unlock()
	path := filepath.Join(dir, "margin-paper.json")
	var s MarginPaper
	if err = Load(path, &s); err != nil {
		return s, err
	}
	if s.Mode != "margin_paper" || s.Holdings == nil || s.Collateral == nil {
		return s, errors.New("invalid margin ledger")
	}
	if err = s.Accrue(time.Now().UTC()); err != nil {
		return s, err
	}
	qty := s.Holdings[symbol].Sub(s.Collateral[symbol])
	if !qty.IsPositive() {
		return s, errors.New("no borrowed overlay position to close")
	}
	markets, err := c.Markets(ctx)
	if err != nil {
		return s, err
	}
	var market Market
	for _, m := range markets {
		if m.Symbol == symbol {
			market = m
		}
	}
	book, err := c.Book(ctx, symbol)
	if err != nil {
		return s, err
	}
	o, err := BuildOrder(market, book, "SELL", "margin-paper-close-"+symbol, decimal.Zero, qty, .003)
	if err != nil {
		return s, err
	}
	filled, _ := decimal.NewFromString(o.Quantity)
	price, _ := decimal.NewFromString(o.Price)
	s.Cash = s.Cash.Add(filled.Mul(price).Mul(decimal.NewFromFloat(.997)))
	repay := decimal.Min(s.Cash, s.Debt)
	s.Cash = s.Cash.Sub(repay)
	s.Debt = s.Debt.Sub(repay)
	s.Holdings[symbol] = s.Holdings[symbol].Sub(filled)
	if filled.Equal(qty) {
		delete(s.Opened, symbol)
	}
	s.Fills = append(s.Fills, o)
	gross := decimal.Zero
	for pair, q := range s.Holdings {
		b, e := c.Book(ctx, pair)
		if e != nil {
			return s, e
		}
		bid, _ := decimal.NewFromString(b.Bids[0])
		gross = gross.Add(q.Mul(bid))
	}
	s.Gross = gross
	s.Equity = s.Cash.Add(gross).Sub(s.Debt)
	return s, Save(path, s)
}
