# Data Manifest — canonical datasets for this project

Last updated 2026-07-07 after ingesting the full extended-hours QQQ history.

## CANONICAL: `qqq_full/` — QQQ 1-min, 2018-01-02 → 2026-07-07

The primary dataset going forward. Nine calendar-year CSVs (`QQQ_1min_YYYY.csv`, 2018..2026;
2026 partial through 07/07). Source: **Alpaca SIP feed, RAW/unadjusted, extended hours
04:00–19:59 ET**, day-first `DD/MM/YYYY HH:MM`, cols `timestamp_et,open,high,low,close,volume,trade_count`.

Verified 2026-07-07:
- **2,113 clean 390-bar RTH days** total; loads through `ingest` / `oos_playbooks.load_file`
  and `premarket.premarket_daily` with no errors (incl. the partial 2026 file).
- **Bit-consistent** with the older `oos_data/QQQ_*` extract for every overlapping year
  (identical row counts and price sums, 2019/2022/2024 checked).
- **Continuous** across every year boundary (no missing sessions between files).
- Spot prices match actual unadjusted traded prices (2018-12-24 low 142.52; 2025-04-07 low 402.39).
- Trade-only bars: zero-trade minutes are absent by design; the pipeline's grid-reindex/ffill
  hygiene handles this (RTH days below 390 bars are auto-excluded from aggregates).

**What this unlocks vs. the data we had before:**
- Fills the **Jan–Jun 2025 gap** that forced a flat patch in the earlier $100k backtest — the
  full-history equity curve can now be rebuilt gap-free.
- Replaces the odd July–June `QQQ_1min_1y_TH.csv` "TH" year with clean **calendar 2025 + 2026**,
  so every study can report true per-calendar-year verdicts (2025 is now a proper 9th OOS sample).

## Cross-asset: `oos_data/` — SPY & IWM 1-min, 2018–2024

Keep for the cross-sectional question (index-arb vs single-stock). Same format. The `QQQ_*`
files here are now **superseded by `qqq_full/`** (identical but only through 2024) — prefer
`qqq_full/` for any QQQ work.

## Self-test baseline: `QQQ_1min_1y_TH.csv` (2025-06-30 → 2026-06-30)

The original Phase-1 handoff's self-test file. **Do not use for new studies** — it is a July–June
window that overlaps 2025+2026 and will double-count if pooled with `qqq_full/`. Retained only to
reproduce the frozen `oos_validate.py` self-test numbers.

## Path quick-reference for scripts

```python
FILES = [Path(f"../qqq_full/QQQ_1min_{y}.csv") for y in range(2018, 2027)]  # 2026 = partial
DEV, VAL = range(2018, 2022), range(2022, 2027)   # suggested split; 2025+2026 now real OOS
```

## REAL TQQQ: `tqqq_full/` — TQQQ 1-min, 2018-01-02 → 2026-07-07 (added 2026-07-08)

Same Alpaca SIP / raw / extended-hours format, one CSV per year. Verified: full year coverage,
~248 complete RTH days/yr. **Four splits detected empirically (raw prices): 2018-05-24 3:1,
2021-01-21 2:1, 2022-01-13 2:1, 2025-11-20 2:1** (README listed only one — trust the scan).
Splits are overnight events: intraday trades unaffected; split-adjust only for B&H benchmarks.
Synthetic-3x validation vs real fills: corr 0.9994, real +3.2 bps/trade better, TE ±6.1 bps —
the synthetic model in tqqq_backtest.py was honest; tqqq_real_backtest.py is now canonical.
