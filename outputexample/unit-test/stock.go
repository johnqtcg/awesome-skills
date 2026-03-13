package unit_test

func maxProfitK(prices []int, k int) int {
	n := len(prices)
	if n == 0 {
		return 0
	}
	dp := make([][]int, n)
	// 可以买卖k次，则一共有2*k+1种情况
	for i := 0; i < n; i++ {
		dp[i] = make([]int, 2*k+1)
	}
	// 奇数代表买入，第一天无论是第几次买入，所获得的最大价值都是-prices[0]
	for i := 1; i < 2*k+1; i += 2 {
		dp[0][i] = -prices[0]
	}
	for i := 1; i < n; i++ {
		for j := 1; j < 2*k+1; j++ {
			// j为奇数，代表买入
			if j%2 == 1 {
				dp[i][j] = Max(dp[i-1][j], dp[i-1][j-1]-prices[i])
			} else {
				// j为偶数，代表卖出
				dp[i][j] = Max(dp[i-1][j], dp[i-1][j-1]+prices[i])
			}
		}
	}
	return dp[n-1][2*k]
}

func Max(a, b int) int {
	if a >= b {
		return a
	}
	return b
}
