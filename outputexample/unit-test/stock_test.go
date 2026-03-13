package unit_test

import "testing"

/*
go test -run TestMaxProfitK -v .
=== RUN   TestMaxProfitK
=== PAUSE TestMaxProfitK
=== CONT  TestMaxProfitK
=== RUN   TestMaxProfitK/empty_prices_returns_zero
=== PAUSE TestMaxProfitK/empty_prices_returns_zero
=== RUN   TestMaxProfitK/zero_transactions_allowed_returns_zero
=== PAUSE TestMaxProfitK/zero_transactions_allowed_returns_zero
=== RUN   TestMaxProfitK/single_day_cannot_make_profit
=== PAUSE TestMaxProfitK/single_day_cannot_make_profit
=== RUN   TestMaxProfitK/two_transactions_capture_separated_gains
=== PAUSE TestMaxProfitK/two_transactions_capture_separated_gains
=== RUN   TestMaxProfitK/large_k_still_respects_best_achievable_profit
=== PAUSE TestMaxProfitK/large_k_still_respects_best_achievable_profit
=== RUN   TestMaxProfitK/killer_case_last_day_sell_must_be_counted
=== PAUSE TestMaxProfitK/killer_case_last_day_sell_must_be_counted
=== CONT  TestMaxProfitK/empty_prices_returns_zero
=== CONT  TestMaxProfitK/single_day_cannot_make_profit
=== CONT  TestMaxProfitK/zero_transactions_allowed_returns_zero
=== CONT  TestMaxProfitK/two_transactions_capture_separated_gains
=== CONT  TestMaxProfitK/large_k_still_respects_best_achievable_profit
=== CONT  TestMaxProfitK/killer_case_last_day_sell_must_be_counted
--- PASS: TestMaxProfitK (0.00s)
    --- PASS: TestMaxProfitK/empty_prices_returns_zero (0.00s)
    --- PASS: TestMaxProfitK/single_day_cannot_make_profit (0.00s)
    --- PASS: TestMaxProfitK/zero_transactions_allowed_returns_zero (0.00s)
    --- PASS: TestMaxProfitK/two_transactions_capture_separated_gains (0.00s)
    --- PASS: TestMaxProfitK/large_k_still_respects_best_achievable_profit (0.00s)
    --- PASS: TestMaxProfitK/killer_case_last_day_sell_must_be_counted (0.00s)
PASS
ok      unit-test       0.350s
*/

func TestMaxProfitK(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name   string
		prices []int
		k      int
		want   int
	}{
		{
			name:   "empty prices returns zero",
			prices: nil,
			k:      2,
			want:   0,
		},
		{
			name:   "zero transactions allowed returns zero",
			prices: []int{3, 2, 6, 5, 0, 3},
			k:      0,
			want:   0,
		},
		{
			name:   "single day cannot make profit",
			prices: []int{5},
			k:      3,
			want:   0,
		},
		{
			name:   "two transactions capture separated gains",
			prices: []int{3, 2, 6, 5, 0, 3},
			k:      2,
			want:   7,
		},
		{
			name:   "large k still respects best achievable profit",
			prices: []int{2, 4, 1},
			k:      5,
			want:   2,
		},
		{
			name:   "killer case last day sell must be counted",
			prices: []int{2, 4, 1, 7},
			k:      1,
			want:   6,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			got := maxProfitK(tt.prices, tt.k)
			if got != tt.want {
				t.Errorf("maxProfitK(%v, %d) = %d, want %d", tt.prices, tt.k, got, tt.want)
			}
		})
	}
}
