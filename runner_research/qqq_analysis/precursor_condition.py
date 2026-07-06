"""
precursor_condition.py — t-1..t-3 features as CONDITIONERS of the early-low-hold playbook (QQQ).

Ran 2026-07-06. DEV 2018-21 battery (8 features x trade PnL @11:00 check), then a single VAL
look (2022-24 + 2025-26 ref) for the two declared picks. Results (tables/PRECOND_dev_trades.csv):

DEV (base +3.7 bps): gap_up_t0 +5.4 diff (3/4) | prior_dn +2.1 (3/4) | up3 +2.7 (2/4)
  big_dn1 -16.8 (0/2) | big_up1 -9.6 (0/4) | thrust_pause -9.7 | prior_wide -5.4
VAL picks:
  big_body1 (t-1 |body| >= trailing P80, either direction) -> SKIP filter:
    DEV worse 6/6 year-samples; VAL diff -6.0 (helps 2/3 yrs); 2025-26 diff -6.4. VALIDATED (modest).
  gap_up_t0 tilt: VAL diff +0.8, 2025 +1.1 (vs +5.4 DEV) -> direction holds, too small to act on.

Frozen refinement adopted: skip the 11:00 early-low-hold entry when YESTERDAY's body was
top-quintile (trailing 20d P80). Removes ~11% of trades earning ~0; lifts remaining book ~+1 bp.

Companion result, same date: frozen C1-C5 verdicts per year (oos_validate.py, tables/OOS_QQQ_20xx):
C1 gap ladder era-split (alive 2018-21, dead 2022-24) · C2 up3 contraction weak-but-persistent
(right sign 6/7) · C3 thrust-pause DEAD (refuted 6/7) · C4 gap-down bounce playbook FAILED its
2022 gate (med -33.8 bps, refuted) · C5 PM-check DEAD (refuted/weakened 6/7).

Features mirror runners.build_frame (trailing-quantile bodies, shift(1..3));
trades from check_ladder.trades(f, 90, 1).
"""
