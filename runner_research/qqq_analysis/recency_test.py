"""
recency_test.py — "Are recent chart patterns more tradable than older ones?" (QQQ, the playbook)

Tested 2026-07-07 on the FINAL early-low-hold playbook (check 11:00, both filters: skip
big-body-yesterday + require session low > premarket low), 431 trades, 2018-2026.

VERDICT: NOT supported for this playbook — and the naive "trade it when it's hot" rule BACKFIRES.

1) Edge over time is STATIONARY: Spearman(trade order, pnl) rho=0.03 (p=0.51);
   year-mean slope +0.28 bps/yr (p=0.74). No growth, no decay.
2) Recent half is if anything WEAKER: old half (2018-2022) mean +7.2 bps / 36% win vs
   new half (2022-2026) +5.4 bps / 32%. 2025 (last full year) was the weakest (-1.0 bps mean);
   2026-partial strong (+18.1, n=33) but small.
3) RECENCY-GATE experiment (only trade when trailing-K-trade mean > 0, causal):
   K=80 -> the SKIPPED block averaged +13.0 bps. The gate would have removed the BEST trades.
   The edge MEAN-REVERTS at the strategy level: weak stretches precede strong ones, not more
   weak ones. Strategy-momentum ("trade the pattern while it's working") is counterproductive.

WHERE THE INTUITION IS RIGHT: as a VALIDATION discipline, not a timing signal. Everything this
project rejected (OR30 system, gap playbook C4/C5, above_pm_high, gap ladder) died precisely
because it failed on the RECENT (2022-26) block after fitting the older one. So we already
privilege recent tradability — as the gate for what to BELIEVE, never as a switch for when to
trade a believed edge. Recent data = the truth test; it is not a market-timing input here.

CONTEXT: volatility ~doubled mid-sample (the long-known regime shift); it scaled wins AND losses
together, changing magnitude not edge (consistent with the stationary per-trade result).
"""
