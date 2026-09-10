package bot

import (
	"context"
	"errors"
	"fmt"
	"github.com/shopspring/decimal"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"time"
)

type Collateral struct {
	Currency    string `json:"currency"`
	Rate        string `json:"collateralRate"`
	Initial     string `json:"initialMarginRate"`
	Maintenance string `json:"maintenanceMarginRate"`
}
type BorrowRate struct {
	Currency string `json:"currency"`
	Hourly   string `json:"hourlyBorrowRate"`
	Daily    string `json:"dailyBorrowRate"`
	Limit    string `json:"borrowLimit"`
}
type BorrowTier struct {
	Tier  string       `json:"tier"`
	Rates []BorrowRate `json:"rates"`
}
type MaxSize struct {
	AvailableBuy  string `json:"availableBuy"`
	MaxBuy        string `json:"maxAvailableBuy"`
	AvailableSell string `json:"availableSell"`
	MaxSell       string `json:"maxAvailableSell"`
	MaxLeverage   int    `json:"maxLeverage"`
}

func (c *Client) Collateral(ctx context.Context) ([]Collateral, error) {
	var r []Collateral
	e := c.request(ctx, "GET", "/markets/collateralInfo", nil, nil, false, &r)
	return r, e
}
func (c *Client) BorrowRates(ctx context.Context) ([]BorrowTier, error) {
	var r []BorrowTier
	e := c.request(ctx, "GET", "/markets/borrowRatesInfo", nil, nil, false, &r)
	return r, e
}
func (c *Client) MaxSize(ctx context.Context, symbol string) (MaxSize, error) {
	var r MaxSize
	e := c.request(ctx, "GET", "/margin/maxSize", url.Values{"symbol": {symbol}}, nil, true, &r)
	return r, e
}

type AssetValue struct {
	Currency, AccountType     string
	Available, Hold           decimal.Decimal
	BidValue, CollateralValue decimal.Decimal
	Symbol                    string
	Excluded                  string
}
type FundingSnapshot struct {
	AsOf                                        time.Time
	Assets                                      []AssetValue
	PricedFreeEquity, FreeUSDT, CollateralValue decimal.Decimal
	Margin                                      Margin
	Borrowing                                   []Borrow
	UnpricedAssets                              int
	ReadOnly                                    bool
}

func (c *Client) FundingSnapshot(ctx context.Context) (FundingSnapshot, error) {
	s := FundingSnapshot{AsOf: time.Now().UTC(), ReadOnly: true}
	accounts, err := c.Balances(ctx)
	if err != nil {
		return s, err
	}
	s.Margin, err = c.Margin(ctx)
	if err != nil {
		return s, err
	}
	s.Borrowing, err = c.Borrowing(ctx)
	if err != nil {
		return s, err
	}
	coll, err := c.Collateral(ctx)
	if err != nil {
		return s, err
	}
	rates := map[string]decimal.Decimal{}
	for _, r := range coll {
		v, e := decimal.NewFromString(r.Rate)
		if e != nil || v.IsNegative() || v.GreaterThan(decimal.NewFromInt(1)) {
			return s, errors.New("invalid collateral haircut")
		}
		rates[r.Currency] = v
	}
	markets, err := c.Markets(ctx)
	if err != nil {
		return s, err
	}
	marketMap := map[string]Market{}
	for _, m := range markets {
		if m.Quote == "USDT" {
			marketMap[m.Base] = m
		}
	}
	for _, a := range accounts {
		for _, b := range a.Balances {
			v, e := decimal.NewFromString(b.Available)
			h, he := decimal.NewFromString(b.Hold)
			if e != nil || he != nil {
				return s, errors.New("invalid balance")
			}
			if v.IsZero() && h.IsZero() {
				continue
			}
			row := AssetValue{Currency: b.Currency, AccountType: a.Type, Available: v, Hold: h}
			if a.Type != "SPOT" {
				row.Excluded = "account type not covered by spot API executor"
			} else if b.Currency == "USDT" {
				row.BidValue = v
				s.FreeUSDT = s.FreeUSDT.Add(v)
			} else if m, ok := marketMap[b.Currency]; ok && m.State == "NORMAL" {
				row.Symbol = m.Symbol
				book, e := c.Book(ctx, m.Symbol)
				if e != nil {
					row.Excluded = "no fresh executable direct USDT quote"
				} else {
					bid, _ := decimal.NewFromString(book.Bids[0])
					row.BidValue = v.Mul(bid)
					minQ, eq := decimal.NewFromString(m.Limits.MinQuantity)
					minA, ea := decimal.NewFromString(m.Limits.MinAmount)
					if eq != nil || ea != nil || v.LessThan(minQ) || row.BidValue.LessThan(minA) {
						row.Excluded = "below exchange minimum; dust not allocated"
					}
				}
			} else {
				row.Excluded = "no active direct USDT market"
			}
			if row.Excluded != "" {
				s.UnpricedAssets++
			} else {
				row.CollateralValue = row.BidValue.Mul(rates[b.Currency])
				s.PricedFreeEquity = s.PricedFreeEquity.Add(row.BidValue)
				s.CollateralValue = s.CollateralValue.Add(row.CollateralValue)
			}
			s.Assets = append(s.Assets, row)
		}
	}
	return s, nil
}

// InitializeFromAccount mirrors inventory, not cash proceeds. It never transfers,
// sells or borrows on the real account. Existing ledgers cannot be replaced.
func (e *Engine) InitializeFromAccount(ctx context.Context) error {
	if e.Config.Mode == "live" {
		if err := e.Ready(ctx); err != nil {
			return err
		}
	}
	if _, err := os.Stat(e.path()); !os.IsNotExist(err) {
		return errors.New("ledger exists or cannot be inspected")
	}
	snapshot, err := e.Client.FundingSnapshot(ctx)
	if err != nil {
		return err
	}
	for _, b := range snapshot.Borrowing {
		v, err := decimal.NewFromString(b.Borrowed)
		if err != nil || !v.IsZero() {
			return errors.New("indebted accounts require a margin ledger; cannot mirror into cash ledger")
		}
	}
	if !snapshot.PricedFreeEquity.IsPositive() {
		return errors.New("no priced inventory")
	}
	budget := decimal.Min(e.Config.Budget, snapshot.PricedFreeEquity)
	fraction := budget.Div(snapshot.PricedFreeEquity)
	s := State{Schema: "poloniex-bot-v1", Mode: e.Config.Mode, Budget: budget, Cash: snapshot.FreeUSDT.Mul(fraction), HighWater: budget, DayStart: budget, Holdings: map[string]Position{}, Processed: map[string]bool{}, Cooldown: map[string]time.Time{}, AccountBacked: true}
	for _, a := range snapshot.Assets {
		if a.Excluded != "" || a.Currency == "USDT" {
			continue
		}
		if a.Available.IsNegative() {
			return errors.New("negative asset inventory")
		}
		if a.Available.IsPositive() {
			s.Holdings[a.Symbol] = Position{Quantity: a.Available.Mul(fraction), Peak: a.BidValue.Div(a.Available), Entered: time.Now().UTC(), Imported: true}
		}
	}
	if err = Save(filepath.Join(e.Config.StateDir, "account-snapshot.json"), snapshot); err != nil {
		return err
	}
	if err = Save(e.path(), s); err != nil {
		return err
	}
	return nil
}

type FundingPlan struct {
	Snapshot                                           FundingSnapshot
	FundingMode, Symbol                                string
	Side                                               string
	RequestedQuote, AllowedQuote, HourlyInterestStress decimal.Decimal
	ConversionCandidates                               []string
	BorrowPossible                                     bool
	Reasons                                            []string
	LiveOrdersSubmitted                                bool
}

// Margin plan deliberately values ETH collateral separately from spendable USDT.
// Borrowing approval is constrained by exchange max size and conservative headroom.
func (c *Client) PlanFunding(ctx context.Context, symbol, mode string, amount decimal.Decimal) (FundingPlan, error) {
	s, err := c.FundingSnapshot(ctx)
	p := FundingPlan{Snapshot: s, FundingMode: mode, Symbol: symbol, Side: "BUY", RequestedQuote: amount}
	if err != nil {
		return p, err
	}
	if !amount.IsPositive() {
		return p, errors.New("positive quote amount required")
	}
	if mode == "convert" {
		p.AllowedQuote = decimal.Min(amount, decimal.Max(decimal.Zero, s.FreeUSDT))
		for _, a := range s.Assets {
			if a.Symbol != "" && a.Excluded == "" && a.Available.IsPositive() {
				p.ConversionCandidates = append(p.ConversionCandidates, a.Symbol)
			}
		}
		sort.Strings(p.ConversionCandidates)
		p.Reasons = append(p.Reasons, "Existing inventory must be converted in reconciled fills before resulting USDT can be spent")
		return p, nil
	}
	if mode != "margin" {
		return p, errors.New("funding must be convert or margin")
	}
	size, err := c.MaxSize(ctx, symbol)
	if err != nil {
		return p, err
	}
	maxBuy, err := decimal.NewFromString(size.MaxBuy)
	if err != nil {
		return p, err
	}
	free, err := decimal.NewFromString(s.Margin.Free)
	if err != nil {
		return p, err
	}
	if size.MaxLeverage < 2 {
		p.Reasons = append(p.Reasons, "market has no margin capacity")
		return p, nil
	}
	headroom := decimal.Min(free.Mul(decimal.NewFromFloat(.25)), decimal.Max(decimal.Zero, s.PricedFreeEquity).Mul(decimal.NewFromFloat(.25)))
	p.AllowedQuote = decimal.Max(decimal.Zero, decimal.Min(amount, decimal.Min(maxBuy, headroom)))
	p.BorrowPossible = p.AllowedQuote.GreaterThan(s.FreeUSDT)
	tiers, err := c.BorrowRates(ctx)
	if err != nil {
		return p, err
	}
	worst := decimal.Zero
	for _, tier := range tiers {
		for _, r := range tier.Rates {
			if r.Currency == "USDT" {
				v, e := decimal.NewFromString(r.Hourly)
				if e != nil || v.IsNegative() {
					return p, errors.New("invalid borrowing rate")
				}
				worst = decimal.Max(worst, v)
			}
		}
	}
	if !worst.IsPositive() {
		p.AllowedQuote = decimal.Zero
		p.BorrowPossible = false
		p.Reasons = append(p.Reasons, "USDT borrow cost unavailable")
	} else {
		borrow := decimal.Max(decimal.Zero, p.AllowedQuote.Sub(s.FreeUSDT))
		p.HourlyInterestStress = borrow.Mul(worst).Mul(decimal.NewFromInt(2))
	}
	p.Reasons = append(p.Reasons, fmt.Sprintf("Read-only plan; %.2f%% of free margin and equity ceiling; current worst-tier rate doubled", 25.), "Historical borrow availability and margin haircuts are not implied by today's limits")
	return p, nil
}
