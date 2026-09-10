package bot

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"math"
	"sort"
	"time"
)

// Fixed model family/parameters. No hyperparameter search against the held-out folds.
// This is native Go gradient boosting with depth-one trees, not an XGBoost/LightGBM binary.
const FeatureSchema = "returns-1-6-24-168-vol24-range24-v1"
const Horizon = 24
const RoundTripCost = .006 // doubled 15bps per side; fixed conservative validation cost

type Features [6]float64
type Stump struct {
	Feature          int
	Cut, Left, Right float64
}
type Ensemble struct {
	Bias  float64
	Trees []Stump
}

func (m Ensemble) Predict(x Features) float64 {
	p := m.Bias
	for _, t := range m.Trees {
		if x[t.Feature] <= t.Cut {
			p += t.Left
		} else {
			p += t.Right
		}
	}
	return p
}
func features(b []Candle, i int) Features {
	x := Features{}
	for k, h := range []int{1, 6, 24, 168} {
		x[k] = b[i].Close/b[i-h].Close - 1
	}
	sum, sum2, span := 0., 0., 0.
	for j := i - 23; j <= i; j++ {
		r := b[j].Close/b[j-1].Close - 1
		sum += r
		sum2 += r * r
		span += (b[j].High - b[j].Low) / b[j].Close
	}
	x[4] = math.Sqrt(math.Max(0, sum2/24-math.Pow(sum/24, 2)))
	x[5] = span / 24
	return x
}

type sample struct {
	X     Features
	Y     float64
	Index int
}

func samples(b []Candle) []sample {
	s := make([]sample, 0, len(b))
	for i := 168; i+Horizon+1 < len(b); i++ {
		s = append(s, sample{features(b, i), b[i+Horizon+1].Open/b[i+1].Open - 1, i})
	}
	return s
}
func fit(s []sample) Ensemble {
	m := Ensemble{}
	if len(s) == 0 {
		return m
	}
	for _, r := range s {
		m.Bias += r.Y
	}
	m.Bias /= float64(len(s))
	pred := make([]float64, len(s))
	for i := range pred {
		pred[i] = m.Bias
	}
	vals := make([]float64, len(s))
	for round := 0; round < 32; round++ {
		best := Stump{}
		loss := math.Inf(1)
		for f := 0; f < 6; f++ {
			for i, r := range s {
				vals[i] = r.X[f]
			}
			sort.Float64s(vals)
			for k := 1; k < 16; k++ {
				cut := vals[k*len(vals)/16]
				l, r, nl, nr := 0., 0., 0, 0
				for i, row := range s {
					v := row.Y - pred[i]
					if row.X[f] <= cut {
						l += v
						nl++
					} else {
						r += v
						nr++
					}
				}
				if nl < 24 || nr < 24 {
					continue
				}
				l /= float64(nl)
				r /= float64(nr)
				err := 0.
				for i, row := range s {
					v := l
					if row.X[f] > cut {
						v = r
					}
					err += math.Pow(row.Y-pred[i]-v, 2)
				}
				if err < loss {
					loss = err
					best = Stump{f, cut, .05 * l, .05 * r}
				}
			}
		}
		if math.IsInf(loss, 1) {
			break
		}
		m.Trees = append(m.Trees, best)
		for i, row := range s {
			if row.X[best.Feature] <= best.Cut {
				pred[i] += best.Left
			} else {
				pred[i] += best.Right
			}
		}
	}
	return m
}

type Fold struct {
	TrainLast   int64
	TestFirst   int64
	TestLast    int64
	Trades      int
	Net         float64
	MaxDrawdown float64
	ModelMSE    float64
	ZeroMSE     float64
}
type Model struct {
	Symbol         string
	Schema         string
	TrainedThrough time.Time
	Expires        time.Time
	Folds          []Fold
	Accepted       bool
	Ensemble       Ensemble
	Hash           string
}

func (m Model) checksum() string {
	m.Hash = ""
	b, _ := json.Marshal(m)
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}
func (m Model) Valid(now time.Time) bool {
	if m.Schema != FeatureSchema || m.Hash != m.checksum() || !m.Accepted || m.TrainedThrough.After(now) || !m.Expires.After(now) || m.Expires.Sub(m.TrainedThrough) > 7*24*time.Hour || len(m.Folds) != 4 || !finite(m.Ensemble.Bias) {
		return false
	}
	for _, t := range m.Ensemble.Trees {
		if t.Feature < 0 || t.Feature >= 6 || !finite(t.Cut) || !finite(t.Left) || !finite(t.Right) {
			return false
		}
	}
	return accepted(m.Folds)
}
func finite(x float64) bool { return !math.IsNaN(x) && !math.IsInf(x, 0) }
func accepted(folds []Fold) bool {
	positive, trades := 0, 0
	net, modelMSE, zeroMSE := 0., 0., 0.
	var last int64
	for _, f := range folds {
		if f.TrainLast >= f.TestFirst || f.TestFirst <= last || f.TestLast < f.TestFirst || f.MaxDrawdown > .15 || !finite(f.Net) || !finite(f.ModelMSE) || !finite(f.ZeroMSE) {
			return false
		}
		last = f.TestLast
		if f.Net > 0 {
			positive++
		}
		trades += f.Trades
		net += f.Net
		modelMSE += f.ModelMSE
		zeroMSE += f.ZeroMSE
	}
	return len(folds) == 4 && positive >= 3 && trades >= 12 && net > 0 && modelMSE < zeroMSE
}
func Train(symbol string, b []Candle) (Model, error) {
	m := Model{Symbol: symbol, Schema: FeatureSchema}
	if len(b) < 2400 {
		return m, errors.New("need at least 2400 contiguous completed hourly bars")
	}
	for i, c := range b {
		if !finite(c.Close) || !finite(c.Open) || c.Close <= 0 || c.Open <= 0 || (i > 0 && c.Start-b[i-1].Start != 3600000) {
			return m, errors.New("invalid training history")
		}
	}
	s := samples(b)
	initial := len(s) / 2
	foldSize := (len(s) - initial) / 4
	for k := 0; k < 4; k++ {
		start := initial + k*foldSize
		end := start + foldSize
		if k == 3 {
			end = len(s)
		}
		cut := start - Horizon - 1
		if cut < 100 {
			return m, errors.New("insufficient purged train set")
		}
		model := fit(s[:cut])
		f := Fold{TrainLast: b[s[cut-1].Index+Horizon+1].Start, TestFirst: b[s[start].Index].Start, TestLast: b[s[end-1].Index+Horizon+1].Start}
		equity, peak := 1., 1.
		for j := start; j+Horizon+1 < end; j += Horizon {
			row := s[j]
			p := model.Predict(row.X)
			f.ModelMSE += (p - row.Y) * (p - row.Y)
			f.ZeroMSE += row.Y * row.Y
			if p > RoundTripCost {
				equity *= 1 + row.Y - RoundTripCost
				f.Trades++
				peak = math.Max(peak, equity)
				f.MaxDrawdown = math.Max(f.MaxDrawdown, 1-equity/peak)
			}
		}
		f.Net = equity - 1
		// End each fold before the next fold's decision boundary, with labels purged too.
		f.TestLast = b[s[end-1].Index].Start
		m.Folds = append(m.Folds, f)
	}
	m.Accepted = accepted(m.Folds)
	m.Ensemble = fit(s)
	m.TrainedThrough = time.UnixMilli(b[len(b)-1].Start + 3600000).UTC()
	m.Expires = m.TrainedThrough.Add(7 * 24 * time.Hour)
	m.Hash = m.checksum()
	return m, nil
}
func (m Model) Forecast(b []Candle, now time.Time) (float64, error) {
	if !m.Valid(now) || len(b) < 169 {
		return 0, errors.New("fallback model is absent, expired or unvalidated")
	}
	last := b[len(b)-1]
	if last.Start+3600000 < now.Truncate(time.Hour).UnixMilli() || last.Start+3600000 > now.UnixMilli() || m.TrainedThrough.After(time.UnixMilli(last.Start+3600000)) {
		return 0, errors.New("fallback clock invalid")
	}
	p := m.Ensemble.Predict(features(b, len(b)-1))
	if !finite(p) {
		return 0, errors.New("invalid prediction")
	}
	return p, nil
}
