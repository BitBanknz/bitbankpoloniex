package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/joho/godotenv"
	"github.com/lee101/bitbankpoloniex/internal/bot"
	"github.com/shopspring/decimal"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

func main() {
	if err := run(); err != nil {
		log.Print(err)
		os.Exit(1)
	}
}
func run() error {
	cfg := bot.DefaultConfig()
	command := flag.String("command", "status", "status, doctor, coverage, init, once, run, train")
	experimental := flag.Bool("experimental-fallback", false, "paper-only exploratory trend20/BTC fallback; not live validated")
	mode := flag.String("mode", "paper", "paper or live")
	state := flag.String("state", "data/paper", "state directory; separate paper and live")
	env := flag.String("env", ".env", "dotenv file (never executed as shell)")
	budget := flag.String("budget", "1000", "USDT budget assigned to this bot")
	maxOrder := flag.String("max-order", "25", "maximum USDT per order")
	endpoint := flag.String("predictions", cfg.PredictionURL, "BitBank rank endpoint")
	ack := flag.Bool("enable-live-orders", false, "explicitly enable real order submission")
	interval := flag.Duration("interval", time.Minute, "cycle interval")
	symbol := flag.String("symbol", "ETH_USDT", "market for funding plan")
	funding := flag.String("funding", "convert", "convert or margin for read-only plan")
	archiveDir := flag.String("archive", "data/archive-daily", "historical archive directory")
	candleInterval := flag.String("candle-interval", "DAY_1", "DAY_1 or HOUR_1")
	maxMarkets := flag.Int("markets", 25, "maximum liquid markets for training; 0 means all")
	flag.Parse()
	// Resolve credentials as a pair. Never mix an inherited key with a project secret.
	key, secret := os.Getenv("POLONIEX_API_KEY"), os.Getenv("POLONIEX_SECRET_KEY")
	if values, readErr := godotenv.Read(*env); readErr == nil {
		key, secret = values["POLONIEX_API_KEY"], values["POLONIEX_SECRET_KEY"]
	} else if !os.IsNotExist(readErr) {
		return errors.New("cannot parse dotenv file")
	}
	var err error
	cfg.Mode = *mode
	cfg.ExperimentalFallback = *experimental
	cfg.StateDir = *state
	cfg.PredictionURL = *endpoint
	cfg.Budget, err = decimal.NewFromString(*budget)
	if err != nil {
		return errors.New("invalid budget")
	}
	cfg.MaxOrder, err = decimal.NewFromString(*maxOrder)
	if err != nil {
		return errors.New("invalid maximum order")
	}
	if err = cfg.Validate(); err != nil {
		return err
	}
	if *interval < 30*time.Second {
		return errors.New("interval must be at least 30s")
	}
	if cfg.Mode == "live" {
		explicitBudget := false
		flag.Visit(func(f *flag.Flag) {
			if f.Name == "budget" {
				explicitBudget = true
			}
		})
		if !*ack || !explicitBudget || cfg.StateDir == "data/paper" {
			return errors.New("live mode requires --enable-live-orders, explicit --budget, and separate --state")
		}
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	client := bot.NewClient(key, secret)
	engine := bot.Engine{Client: client, Config: cfg}
	output := func(v any) error { enc := json.NewEncoder(os.Stdout); enc.SetIndent("", "  "); return enc.Encode(v) }
	switch *command {
	case "margin-paper-close":
		if cfg.Mode != "paper" {
			return errors.New("margin paper cannot submit live orders")
		}
		s, err := client.MarginPaperClose(ctx, cfg.StateDir, *symbol)
		if err != nil {
			return err
		}
		return output(s)
	case "margin-paper":
		if cfg.Mode != "paper" {
			return errors.New("margin-paper cannot submit live orders")
		}
		s, err := client.MarginPaperStep(ctx, cfg.StateDir, *symbol, cfg.MaxOrder)
		if err != nil {
			return err
		}
		return output(s)
	case "research-signals":
		m, err := client.Universe(ctx, cfg.MinVolume)
		if err != nil {
			return err
		}
		s, err := client.ResearchSignals(ctx, cfg.StateDir, m)
		if err != nil {
			return err
		}
		return output(s)
	case "account-plan":
		p, err := client.PlanFunding(ctx, *symbol, *funding, cfg.MaxOrder)
		if err != nil {
			return err
		}
		return output(p)
	case "archive":
		return client.Archive(ctx, *archiveDir, *candleInterval, *maxMarkets)
	case "doctor":
		accounts, err := client.Balances(ctx)
		if err != nil {
			return err
		}
		m, marginErr := client.Margin(ctx)
		r := map[string]any{"balances": bot.AccountSummary(accounts), "live_orders_submitted": false}
		if marginErr != nil {
			r["margin_error"] = marginErr.Error()
		} else {
			r["margin"] = m
		}
		if err = engine.Ready(ctx); err != nil {
			r["execution_readiness"] = err.Error()
		} else {
			r["execution_readiness"] = "read checks passed; write permission unverified"
		}
		return output(r)
	case "coverage":
		markets, err := client.Universe(ctx, cfg.MinVolume)
		if err != nil {
			return err
		}
		p, pe := bot.FetchPrediction(ctx, cfg.PredictionURL)
		covered := []string{}
		if pe == nil {
			covered = bot.Targets(p.Scores(), markets, len(markets))
		}
		r := map[string]any{"liquid_usdt_markets": len(markets), "bitbank_covered": covered, "markets": markets}
		if pe != nil {
			r["prediction_error"] = pe.Error()
		}
		return output(r)
	case "status":
		s, err := engine.Status()
		if err != nil {
			return err
		}
		return output(s)
	}
	lockDir := cfg.StateDir
	if *command == "train" {
		lockDir = filepath.Join(cfg.StateDir, "training")
	}
	unlock, err := bot.Lock(lockDir)
	if err != nil {
		return err
	}
	defer unlock()
	switch *command {
	case "init-account":
		return engine.InitializeFromAccount(ctx)
	case "init":
		if cfg.Mode == "live" {
			if err = engine.Ready(ctx); err != nil {
				return err
			}
		}
		return engine.Initialize()
	case "train":
		return engine.TrainFallback(ctx, *maxMarkets)
	case "once":
		return engine.Cycle(ctx)
	case "run":
		ticker := time.NewTicker(*interval)
		defer ticker.Stop()
		failures := 0
		for {
			if err = engine.Cycle(ctx); err != nil {
				failures++
				log.Printf("cycle blocked (%d): %v", failures, err)
			} else {
				failures = 0
				log.Print("cycle complete")
			}
			if failures >= 5 {
				return errors.New("five consecutive failures; circuit open")
			}
			select {
			case <-ctx.Done():
				return nil
			case <-ticker.C:
			}
		}
	default:
		return fmt.Errorf("unknown command %q", *command)
	}
}
