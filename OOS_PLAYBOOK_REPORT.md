# OOS Validation Report — OR30 & Noon-Check Playbooks (2018–2024 QQQ/SPY/IWM)

Date: 2026-07-06. Data: 21 symbol-year files (QQQ/SPY/IWM × 2018–2024), 1-min extended-hours,
UNADJUSTED — validated clean (full trading years, ~248 complete 390-bar days each, spot prices
match actual traded prices to the cent: QQQ COVID low 164.93 ✓, SPY 218.26 ✓, SPY 2022-01-03
close 477.76 ✓, QQQ 2024 close 511.21 ✓).

Code: `qqq_analysis/oos_playbooks.py` (frozen-spec test) and `qqq_analysis/oos_improve.py`
(variant pass, DEV 2018–2021 / VAL 2022–2024 split). Full tables in
`qqq_analysis/output/tables/OOSPB_*.csv` and `IMP_*.csv`.

---

## Verdict summary

| Playbook | Component | Verdict |
|---|---|---|
| OR30 break→pullback (R-system) | profit profile (+11%/yr, −3.8% DD in-sample) | **REFUTED** |
| OR30 | any rescue variant (longs-only / tighter stop / OR15) | **REFUTED** — none helps |
| Noon-check | firing rate + trend-day label lift (41% vs 17%) | **CONFIRMED — 21/21 symbol-years** |
| Noon-check | frozen trade economics (HOD target / VWAP stop) | **REFUTED** (≈0 mean) |
| Noon-check | improved exit engine "B1" (drop target, run to 15:57) | **PROMISING** — positive mean in DEV, VAL, and 2025-26, QQQ/SPY only |

## P1 — OR30 system (frozen spec, $10k @ 1% risk)

The in-sample profile does not survive. QQQ 2018–2024 yearly returns:
+1.8, +7.3, **−8.5**, +2.5, −3.1, −5.7, +1.7 % → average ≈ **−0.6%/yr** (vs +11.0% in-sample);
win rate ~50% (vs 62%); worst drawdown −10% (2020). SPY averages ≈ +2.0%/yr, IWM ≈ +3.6%/yr —
positive but small, with mixed halves and no consistency. Pooled across all 21 symbol-years the
mean trade is +0.8–1.6 bps net — indistinguishable from zero after any real slippage beyond
1 tick. The 2025-26 in-sample year (+11%) turns out to be the best year in the whole panel:
textbook selection on a drift year.

Variant pass (pre-registered from HANDOFF §6.3, DEV 2018–21 → VAL 2022–24):
longs-only slightly worse; stop@75%-retrace no better (median goes negative); OR15 clearly
worse (−2 to −3%/yr). **Recommendation: retire OR30 as a trading system.** The underlying
market-structure findings (the morning-leg clock, pullback geometry) remain descriptively valid;
they just don't convert to net edge at these costs.

Caveat noted: per-year files reset the short gate's 30-day warm-up, so each year's first ~6
weeks trade long-only. This slightly under-tests the short book, but shorts were n=11/yr
in-sample — the long side is what failed.

## P2 — Noon-check

**The signal is real.** Fires 27–39% of days everywhere (in-sample 35%); trend-up rate on fire
days beats base in **every one of 21 symbol-years** (typically 2–2.5×: e.g. QQQ 2022 52.5% vs
21.0%; SPY 2022 56.1% vs 21.8%). This is the strongest cross-sectional replication in the
project — the noon-check is a genuine trend-day classifier, and notably strongest in the 2022
bear year, so it is not a drift artifact.

**The frozen trade wastes it.** Median +1–2 bps, mean ≈ 0 across all years: the standing-HOD
target caps winners at a few bps while the VWAP stop takes the fat left tail.

**Improvement (disciplined):** three variants explored on DEV 2018–2021 only; B1 = drop the
HOD target, keep the trailing-VWAP stop, flat 15:57 — i.e. let the trend-day classification run.

| Split | B1 mean bps/trade | positive-sum years |
|---|---|---|
| DEV 2018–2021 (12 sym-yrs) | +0.7 | 7/12 |
| VAL 2022–2024 (9 sym-yrs) | **+3.8** | 7/9 |
| QQQ 2025-26 (untouched for B1) | **+3.7** | — |

Per-symbol VAL: QQQ +10.6/+8.1/+1.5 bps (2022/23/24), SPY +9.8/+3.3/+2.1 — **all six QQQ/SPY
validation years positive** — IWM ≈ 0 (skip small-caps). Profile is trend-following: ~35% win
rate, many small VWAP-stop losses, occasional +100–300 bps runners; best year was the 2022 bear.

Honesty box: B1 was one of only 3 variants (low selection debt) and was chosen on DEV before
VAL scoring, then re-confirmed on 2025-26 which it had never seen. But +2–7 bps/trade mean with
a 35% win rate is thin: the assumed 1-tick/side cost is optimistic for afternoon VWAP-stop fills,
and ~87 trades/yr × ~+4 bps ≈ +3.5%/yr unlevered. Real but modest.

## Addendum (2026-07-06): OR30 day-type filter battery — REFUTED

Per the user's request, 8 pre-registered day-type filters were tested on the frozen OR30 spec,
QQQ only (`or30_filters.py`; DEV 2018–21 → VAL 2022–24, single look):
gap-aligned-with-break / gap-opposed / no-big-gap / **day-after-gap-day** / **uptrend (SMA20)** /
downtrend / trend-aligned-sides / narrow-vs-wide OR.

- On DEV, only **gap_align** improved the system (mean −1.8 → +1.8 bps, 3/4 positive years), with
  a clean mechanical split (gap_opposed = −6.2). after_gap_day (−5.4) and uptrend (−1.3) were
  dead on arrival.
- On VAL, gap_align **failed**: mean −4.6 bps (worse than the unfiltered −1.2), 1/3 positive
  years. On the 2025-26 in-sample year it merely halves the in-sample profit (+11.0% → +5.5%).

Conclusion: the OR30 edge does not exist out-of-sample in any tested day-type regime. This closes
HANDOFF §6.3 (system hardening) with a refutation. Tables: `ORF_dev.csv`, `ORF_val.csv`.

## Recommendations

1. **Retire OR30** as a live system. Do not spend more OOS data trying to rescue it.
2. **Keep the noon-check as a classifier** (41%+ trend-day precision at 12:00 is durable
   information — useful as a filter/sizing input for any afternoon long book, including the
   gap playbook overlap flagged in HANDOFF_RESEARCH §8).
3. If trading it, use the **B1 exit engine on QQQ/SPY only**, and before capital:
   (a) model realistic slippage on VWAP-stop exits (limit vs market), (b) paper-trade it,
   (c) re-run the verdict after each new quarter of data.
4. Remaining pre-registered item not covered here: the gap-down playbook (C1–C5,
   `oos_validate.py`) can now be verdict-scored per year on these same files — natural next step.
