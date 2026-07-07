"""
pm_conditioners.py — Can the premarket findings add to the early-low-hold playbook? (QQQ)

Ran 2026-07-07 on canonical qqq_full/ (2018-2026). Tested 4 PM-derived cuts as CONDITIONERS
of the validated early-low-hold long (check 11:00), DEV 2018-21 -> VAL 2022-26. Full detail in
the session; headline diffs (trade-PnL of fires WITH feature minus WITHOUT):

  feature            DEV diff (yrs)   VAL diff (yrs)   verdict
  above_pm_high      +13.8 (4/4)      -2.1  (2/5)      TRAP — breakout-chase in disguise, FAILED OOS
  low_above_pm_low   +4.4  (4/4)      +5.2  (3/5)      KEEPER — held; strength confirmation
  gap_up             +5.4  (3/4)      +2.3  (4/5)      mild tilt, too small to act on
  pm_tight           +2.2  (3/4)      -1.4  (1/5)      dead

KEEPER: low_above_pm_low = the session's low (as of 11:00) never dipped below the premarket low,
i.e. RTH held entirely above the overnight range = genuine strength. Stacks with the adopted
big-body-yesterday skip (pooled 2018-2026, 840 fires):
  raw                        n=840  mean 3.6 bps  win 31.7%  7/9 positive years
  + skip big-body            n=668  mean 5.8      win 33.2%  7/9
  + PM-strength (low>PMlow)  n=589  mean 5.0      win 33.1%  8/9
  + BOTH filters             n=471  mean 6.3      win 34.2%  8/9   (keeps 56% of fires)

HONEST CAVEAT: both filters ~double per-trade edge (3.6->6.3) and lift consistency (7/9->8/9),
but TOTAL annual PnL is ~unchanged (~330 bps/yr either way) because trade count falls
proportionally (~93->~52/yr). The value is RISK-ADJUSTED: steadier equity, fewer bad trades,
higher conviction per trade — NOT more absolute return. Adopt if you prefer fewer/cleaner
trades; skip if you want maximum trade frequency.

REFUTED-as-addition (do NOT add): PM-zone breakout entry (above_pm_high) — the ~85% first-hour
breakout-failure finding (pm_zone_study.py) is exactly why chasing the PM-high hold fails OOS.
"""
