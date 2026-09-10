package bot

import (
	"math/rand/v2"
	"testing"
)

// fitBenchCandles is deliberately synthetic: the benchmark guards training
// speed, not signal quality (gated by quality_test.go on real semantics).
func fitBenchCandles(n int) []Candle {
	rng := rand.New(rand.NewPCG(1, 0))
	price := 100.0
	start := int64(1700000000000)
	b := make([]Candle, n)
	for i := range b {
		open := price
		price = open * (1 + rng.NormFloat64()*0.01)
		high := max(open, price) * 1.001
		low := min(open, price) * 0.999
		b[i] = Candle{Start: start + int64(i)*3600000, Open: open, High: high, Low: low, Close: price, Volume: 1000}
	}
	return b
}

func BenchmarkFit(b *testing.B) {
	s := samples(fitBenchCandles(3000))
	b.ResetTimer()
	for range b.N {
		fit(s)
	}
}
