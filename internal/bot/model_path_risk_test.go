package bot

import (
	"math"
	"testing"
	"time"
)

func pathRiskHistory() []Candle {
	bars := make([]Candle, 2400)
	start := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC).UnixMilli()
	for i := range bars {
		price := 100 * math.Pow(1.001, float64(i))
		bars[i] = Candle{Start: start + int64(i)*3600000, Open: price,
			Close: price * 1.001, High: price * 1.002, Low: price * .999, Volume: 10000}
	}
	return bars
}

func TestFallbackFoldRejectsRecoveredHoldingDrawdown(t *testing.T) {
	regular := pathRiskHistory()
	control, err := Train("TEST_USDT", regular)
	if err != nil {
		t.Fatal(err)
	}
	if !control.Accepted {
		t.Fatalf("rising-price control should qualify: %+v", control.Folds)
	}
	for _, fold := range control.Folds {
		if math.Abs(fold.MaxDrawdown-RoundTripCost) > 1e-12 {
			t.Fatalf("entry cost missing from drawdown: %.12f", fold.MaxDrawdown)
		}
	}
	rows := samples(regular)
	first := len(rows)/2 + 3*((len(rows)-len(rows)/2)/4)
	dip := rows[first].Index + 1 + Horizon/2
	changed := append([]Candle(nil), regular...)
	changed[dip].Close *= .6
	changed[dip].Low = changed[dip].Close * .999
	candidate, err := Train("TEST_USDT", changed)
	if err != nil {
		t.Fatal(err)
	}
	for i, fold := range candidate.Folds {
		if fold.Net != control.Folds[i].Net || fold.Trades != control.Folds[i].Trades {
			t.Fatalf("recovered close changed terminal returns/trades in fold %d: got=%+v old=%+v", i, fold, control.Folds[i])
		}
	}
	if candidate.Folds[3].MaxDrawdown < .35 || candidate.Accepted {
		t.Fatalf("accepted hidden holding loss: accepted=%v maximumDD=%.8f exitNet=%.8f", candidate.Accepted,
			candidate.Folds[3].MaxDrawdown, candidate.Folds[3].Net)
	}
}

func TestFallbackRiskReceiptsNeedFiniteDrawdownAndCurrentValidation(t *testing.T) {
	model, err := Train("TEST_USDT", pathRiskHistory())
	if err != nil {
		t.Fatal(err)
	}
	if !model.Valid(model.TrainedThrough.Add(time.Hour)) {
		t.Fatal("valid current path receipt rejected")
	}
	for _, dd := range []float64{math.NaN(), math.Inf(1), math.Inf(-1), -.01} {
		folds := append([]Fold(nil), model.Folds...)
		folds[0].MaxDrawdown = dd
		if accepted(folds) {
			t.Fatalf("invalid drawdown accepted: %v", dd)
		}
	}
	for _, version := range []string{"", "exit-only"} {
		old := model
		old.ValidationSchema = version
		old.Hash = old.checksum()
		if old.Valid(old.TrainedThrough.Add(time.Hour)) {
			t.Fatalf("old validation contract accepted: %q", version)
		}
	}
}
