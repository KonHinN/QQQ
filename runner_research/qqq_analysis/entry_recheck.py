"""
entry_recheck.py — RETRACTION: the v2 "VWAP-pullback entry" was a look-ahead artifact.

Flagged 2026-07 on user review ("is it limit at VWAP or market at 11:00? the example buys at
11:00"). Trace of upgrade_lab.sim(mode='E1_vwap_pull'): entry defaults to the 11:00 close, but if
a VWAP touch occurs anywhere in the next 30 min it RETROACTIVELY uses that (lower) bar's close.
A trader at 11:00 cannot know a pullback is coming -> hindsight cherry-pick.

Clean causal comparison, QQQ 2018-2026, 463 firing days, 1 tick/side:
  v1  market @ 11:00                              mean +6.7 bps  win 34.6%  8/9 yrs   <- CORRECT
  v2  pullback as-coded (LOOK-AHEAD)              mean +10.9    win 38.7%  9/9       <- INFLATED
  Rule B  limit@VWAP, chase 11:30 if unfilled     mean +4.5     win 33.5%  8/9       (causal, worse)
  Rule B-skip  limit@VWAP, skip if unfilled        mean -1.0     n=162      2/9       (skips the
                 no-pullback days = exactly the strong trending winners; kills the fat tail)

CONCLUSION: the honest entry is MARKET AT 11:00 (v1). The limit-at-VWAP idea, done causally, is
worse than market@11:00 because the 65% of days that never pull back are the trending days you
must not chase or skip. The "v2 upgrade" (+10.9 bps, 9/9 yrs) is withdrawn; the playbook entry
reverts to v1. All artifacts built on v2 (tqqq_backtest, tqqq one-pager, upgrade page) corrected.

Net effect on TQQQ $100k backtest (market@11:00): per-trade +27->+15 bps; end $338k->$190k;
CAGR 15.4%->7.9%; max DD -6.9%->-14.2%; 9/9->8/9 positive years (2025 now -6%).
"""
