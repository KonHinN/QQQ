# HANDOFF — QQQ Intraday Study, Phase 1 complete (analyses A–R)

> **How to use this file:** open a new Claude Code session in the unpacked package directory and
> make this the first thing it reads. Everything a fresh session needs — context, hard-won
> gotchas, verified conclusions, refuted dead-ends, the trading system spec, and the Phase-2
> agenda — is in here. **Do not re-derive what is already settled.**

---

## 1. Project context

We mined **one year of QQQ 1-minute bars** (30 Jun 2025 → 30 Jun 2026, RTH 09:30–15:59 ET,
247 clean days) for time-of-day structure, then developed and backtested an **opening-range
break→pullback trading system** on top of it. Everything is data-driven, null-model tested,
split-year (H1/H2) verified, and audited (one full audit round reversed one finding — §5).
**Phase 2 = out-of-sample validation on more years/instruments. That is your likely mission.**

## 2. Data facts — verified, do not re-litigate

- File: `QQQ_1min_1y_TH.csv` (228,827 rows, extended-hours 04:00–19:59 ET).
- **`timestamp_et` is the clock.** Parse **day-first**: `%d/%m/%Y %H:%M`.
- RTH filter = 09:30:00–15:59:00 ET inclusive → exactly **390 bars/day**, `minute_index` 0–389.
- 252 raw days; **exclude 5 from aggregates**: `2025-06-30`, `2026-06-30` (boundary-partial),
  `2025-07-03`, `2025-11-28`, `2025-12-24` (holiday-thin) → **247 clean**.
- Vendor `vwap` column is **premarket-anchored — wrong**. `ingest.py` recomputes session VWAP.
- **Prior-day levels:** 4 clean days follow a partial day → `daily.prior_is_full` flags them;
  level analyses use 243 days. Replicate this on new data.
- Parquet gotcha: date join keys as **strings** (`YYYY-MM-DD`), never date objects.
- Mid-year **volatility regime shift** (daily range ~doubled H1→H2): never carry dollar
  magnitudes across periods; use ATR-normalized / OR-relative / timing statistics.
- pandas 3.x: `groupby.apply` needs `include_groups=False`; some args keyword-only.

## 3. Pipeline (fully reproducible)

```
python ingest.py            # CSV -> output/minute.parquet + daily.parquet
python report.py            # runs ALL analyses A-R -> Excel (18 sheets) + dashboard + FINDINGS.md
python present.py           # 21-slide analyst deck
python or_deck.py           # 11-slide OR-break study deck
python or_playbook_deck.py  # 9-slide long/short playbook deck
python onepage.py           # one-page in-house trader sheet
python system_backtest.py   # $10k equity-curve backtest + equity_curve.html
python capture_slides.py    # deck -> PNGs (needs playwright + chromium)
```

| Module | Analyses |
|--------|----------|
| `analytics.py` | A minute profile · B event timing · C opening range · D prior-day levels + race test · E ATR-ZigZag pivots · F robustness · G clustering |
| `binning.py` | H time resolution (adaptive grid, bootstrap CIs) |
| `persistence.py` | I reversal-clock persistence & regime tests |
| `patterns.py` | J day-type taxonomy, shapes, motifs, early recognition |
| `backtest.py` | K first cost-aware time-rule backtest |
| `weekday.py` | L day-of-week with Bonferroni control |
| `or_break.py` | M OR-break continuation: entry tournament + pullback geometry |
| `retrace.py` | N %-retracement scale: limit ladder + depth health meter |
| `timecut.py` | O time filters on the retest (cancel/abort tests) |
| `tradable.py` | P "worth trading" definition (R-frame) + causal predictors |
| `sides.py` | Q long vs short split of M/N/P |
| `system_backtest.py` | R $10k system backtest, causal short gate, risk sweep |
| `runners.py` | S runner-day precursors: t-1..t-3 candles, gap ladder, econ flags (target = max intraday up-leg; trailing-P80 def; 1.6% ≈ H2 P80) |
| `gapfade.py` | T gap-down bounce anatomy: bounce timing, time-rule economics, OR30-system overlap (deck: `output/runner_study.html`) |
| `gap_playbook.py` | U playbook parameters: exit ladder (13:30 best), MAE/stop sweep (−1.0%), checkpoints, subtypes |
| `premarket.py` | V premarket (04:00–09:29) features: pm ladders (VOL only — track Y_wide 1:1), event-day "PM bounced" split |
| `gap_playbook_page.py` / `gap_onepage.py` | playbook deliverables: `output/gap_playbook.html` + `output/gap_onepage.html` (1-page visual) |
| `gap_backtest.py` | W $100k equity-curve backtest of the gap playbook (risk sweep 0.5/1/2%; PM-checked @1%: +5.9%/yr, DD −1.4%, avg 0.31R, n=19) → `output/gap_equity_curve.html` |
| `oos_validate.py` | **OOS harness**: `python oos_validate.py <csv> <label>` → auto day-hygiene + frozen-spec verdicts (C1 gap ladder, C2 up3, C3 thrust-pause, C4 playbook, C5 PM check). Self-test on 2025-26 reproduces all in-sample numbers exactly. ⚠ New data must be UNADJUSTED (or split-adjusted only) — dividend adjustment fabricates ~0.5% quarterly gaps and poisons the gap feature. |
| `universe_study.py` | **Cross-sectional framework**: per-symbol S battery + Y_wide vol-control pairing + sign-test aggregation across US stocks. `python universe_study.py <data_dir> [label]`. |

**Research handoff (2026-07-06):** the runner-precursor mission (t-1..t-3 → t0, extended to
single US stocks) was handed to the research team: `HANDOFF_RESEARCH.md` (mission, priors,
methodology, deliverables) + `runner_research_handoff.zip` (5.9 MB: full code, reference
tables/decks, QQQ CSV as self-test baseline) — both in the QQQ folder / qqq_analysis dir.

Deps: python 3.12, pandas 3.x, numpy, scipy, scikit-learn, pyarrow, plotly, openpyxl, tabulate;
playwright+chromium only for slide capture.

## 4. Settled conclusions — do NOT re-derive on this data

### 4a. Market structure (A–L)
1. **Volatility smile** $1.12→$0.25→$0.50/min and **volume U** 675k→65k→998k (corr ≥0.98 H1↔H2).
2. Reversal pivots cluster 09:30–09:44 at 2.17× uniform (z=12.2).
3. **The structural clock**: the day's biggest leg starts 09:30–10:30 (67%), extends the opening
   drive (82% same direction, z=6.5), terminates 10:00–11:00 on **52.0%/52.4%** (H1/H2) of days.
   Holds on every weekday (KW p=0.36).
4. HOD/LOD bimodal (session edges). Volatility clusters (0.44, z=7.3); direction does not (~0).
5. OR5 first breaks: 74% fakeout. Close micro-script: 15:47–15:57 up, 15:59 down (small).
6. Day census: reversal days 37% > trend 29% > chop 16%; five soft k-means shapes; morning does
   NOT predict afternoon (50.2%, corr −0.006) — taxonomy is hindsight only.
7. 5-min bins maximize signed-return repeatability; uniform ≥15-min destroys it.

### 4b. Refuted — dead ends (each was tested properly; don't re-open on this data)
1. **PDH/PDL are NOT reversal magnets** — race test 49%/39% vs control 51%. ⚠️ The trap: any
   "reverted within N minutes" criterion has a 78–83% base rate from ANY minute; level claims
   must beat a random-point control.
2. Minute-level signed drift = noise (H1↔H2 corr 0.11).
3. Morning sign motifs = independence (all |z|≤1.1).
4. Reversal-block recurrence on later days (incl. weekly, weekday-matched) = flat nulls.
5. Weekday effects: nothing survives Bonferroni. Sole both-halves lead: **Monday positive**
   (+11/+36 bps median) — OOS item only.
6. First-retest lateness does NOT predict failure (flat 48–56%); exit-on-late-touch **destroys**
   value (sells the pullback low: OR30 +3.4→−1.6 bps).
7. R-frame trap: R-based "tradability" mechanically favours narrow ORs; judge economics in bps.

### 4c. The trading system (M→R, the deliverable)
**Spec (as backtested):** OR30 break = first 1-min CLOSE beyond the extreme by 10:30 → limit at
25% retracement of the OR (frozen at break) → cancel unfilled at 10:30 → stop at the far side →
exit 10:59. **Longs ungated; shorts only if |open→break| drive ≥ trailing 66.7th percentile**
(causal, 30-break warm-up; ≈0.5% of price in this year).
- Geometry (side-symmetric): trend-to-11 ≈ 50–56%; trend days retrace median ~19–26% of the OR
  and almost never traverse fully; **depth health meter** P(trend|max retrace) decays 93→3%
  (long) / 84→10% (short); pullback bottoms cluster 09:54–10:17.
- Entry evidence: chasing/confirm entries flip halves (dead); 25–50% retracement rungs and
  VWAP-pullback are the only both-halves-positive families; cancel-by-10:30 adds ~+2 bps.
- **$10k backtest (R):** 61 trades (50L/11S), **+11.0%/yr at 1% fixed-fractional risk, max DD
  −3.8%**, 62% win, avg +0.19R, 21% stop-outs, both halves profitable; 2% risk → +20.9%/−5.7%.
  Buy&hold made +32.4% (drift year) with −12.2% DD. Per-trade Sharpe (~3.5) is flattered (idle
  days add no variance).
- **Strongest cell / weakest sample:** OR30 strong-drive shorts +23.9 bps, 67% hit, t=2.03,
  both halves positive — **n=12**.
- **Status: ALL of it is in-sample-selected. Nothing here is a proven edge. t<2.1 everywhere.**

## 5. Audit history

One full audit round found and fixed: (i) prior-day levels sourced from partial days;
(ii) 68/145 "PDH touches" were gap-overs; (iii) dominant-swing start/end mislabelled (starts
09:30–10:30, ENDS 10:00–11:00); (iv) the level-reversal base-rate artifact → conclusion reversed
to "refuted". Any old "PDH/PDL reversal rate 61–83%" numbers are superseded by the race test.

## 6. Phase-2 agenda (your work), priority order

1. **OOS validation** — rerun the pipeline unchanged on ≥2 more years of QQQ and on SPY/IWM
   (ideal: 2022–2024 = bear/chop/bull). Only `ingest.py` needs the CSV path + a new exclusion
   list (find partial days by bar count ≠ 390). Verdict per item: the 52% clock · the system's
   +11%/−3.8% profile · the strong-drive short gate (n=12!) · the 25–50% rung sweet spot ·
   the Monday lead · smile/U shapes.
2. **Mechanism of the 10:00–11:00 turn** — (a) econ-calendar overlay (10:00 ET releases);
   (b) volume-clock test (turn at X% of typical volume?); (c) cross-asset sync (SPY/IWM same
   days?). Doubles as OOS.
3. **System hardening (only on new data)** — pre-registered filters (gap alignment, overnight
   range); OR15 vs OR30 portfolio; stop variants tighter than far-side for OR30.
4. **Race-test more levels** — session VWAP, round numbers, premarket H/L, prior-week H/L.
   Framework in `analytics.py::analysis_D`.
5. **Analysis S/T leads (2026-07-06, in-sample — pre-registered for OOS):**
   (a) big gap-DOWN (≤ −0.35× prior range on `gap_over_prange`) → runner rate ~36% vs 27% base;
   the gap ladder is a gap-down-vs-gap-up SPLIT (down/flat quintiles ~33–36%, up quintiles ~16%),
   NOT strictly monotone; both halves same-sign; bounce low set by 10:30 on 74% of event days,
   leg tops ~13:20; 10:00→close long +12.3 bps median net, both halves. ⚠ drift-year-shaped — 2022 is the test.
   (b) 3 consecutive up closes → big-leg rate 8.9% vs 27.2% (Bonferroni-sig, both halves) —
   contraction filter, echoes "vol clusters, direction doesn't".
   (c) thrust→pause (big up t-2, small t-1) → trend-day lift 2.08, n=11 — underpowered.
   REFUTED on this data: big-up-candle continuation (inverted); gap-up momentum (inverted);
   econ-day direction (vol only; econ flags approximate — verify calendar).
6. **Gap-down playbook (U/V, 2026-07-06 — the pre-registered OOS candidate system):**
   gap ≤ −0.35× prior range AND open ≥0.3% above premarket low → buy 10:00 close, stop −1.0%,
   sell 13:30. With PM check: +47 bps med, 68% hit, n=19 (H1/H2 +77/+45); without: +20 bps,
   60%, n=47 (H1/H2 +17/+21). Open ON the PM low = skip (−11 bps med, n=26). Premarket
   range/volume ladders predict VOL only (track Y_wide 1:1) — not direction. ⚠ Three rounds of
   in-sample refinement (event→params→PM split) — selection debt is deep; OOS is the gate.

**Methodological requirements (non-negotiable — they killed many false leads here):**
medians+IQR; H1/H2 same-sign; matched null per claim (shuffle / independence / base-rate /
random-point control); Bonferroni for test batteries; strictly causal features (see the drive
gate and `atr_pre` patterns); report n and effect size with every number; costs and pessimistic
fills in any backtest.

## 7. Package manifest (this zip)

**Code (reproduces everything):** `ingest.py analytics.py binning.py persistence.py patterns.py
backtest.py weekday.py or_break.py retrace.py timecut.py tradable.py sides.py system_backtest.py
report.py present.py or_deck.py or_playbook_deck.py onepage.py capture_slides.py HANDOFF.md`
+ `QQQ_1min_1y_TH.csv` (raw data, one level above the code dir; edit `CSV_PATH` in ingest.py if moved).

**Deliverables in `output/` (all regenerable):**
- `FINDINGS.md` — full technical findings A–R (the reference document)
- `QQQ_intraday_tables.xlsx` — 18 sheets, every aggregate table
- `CEO_REPORT_FULL.md` / `CEO_REPORT_BRIEF.md` · `TRADER_REPORT_TH.md` (Thai)
- `dashboard.html` (17-chart analyst dashboard) · `presentation.html` (21 slides)
- `playbook.html` (13-slide time-of-day playbook) · `or_break_deck.html` (11 slides) ·
  `or_playbook.html` (9-slide long/short system deck)
- `playbook_onepage.html` — the one-page in-house trader sheet (chart with timing+levels)
- `equity_curve.html` — $10k backtest curve vs buy&hold
- `slides/`, `slides_or/`, `slides_pb/` — all decks captured as PNGs
- `tables/*.csv` — every table (A–R) · `minute.parquet` / `daily.parquet`

**Reproduce:** `cd qqq_analysis && python ingest.py && python report.py`

## 8. Suggested opening instruction for the new session

> "Read HANDOFF.md fully. Phase 1 (analyses A–R) is settled — do not re-derive or re-test its
> conclusions on the 2025–26 data. Our task is Phase-2 item ⟨N⟩. New data files: ⟨paths⟩,
> same column format. Apply §6's methodological requirements to everything new, and report
> each Phase-1 headline as CONFIRMED / WEAKENED / REFUTED on the new data."
