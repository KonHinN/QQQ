# HANDOFF — Runner-Precursor Research (t-1..t-3 → t0), extend to the US stock universe

> **To the research team / new Claude session: read this file fully before touching data.**
> Mission, everything already established on one year of QQQ (do NOT re-derive it), the
> framework code, the methodology rules that killed a dozen false leads, the CANONICAL numbers
> (§9 — use these, never transplant), and the exact deliverables expected back.
>
> Rewritten 2026-07-06 after a full recheck: every number below was recomputed fresh from
> `QQQ_1min_1y_TH.csv` on this date and matches the code output to the decimal.

---

## 1. Mission

**What features known BEFORE today's open make today (t0) a "runner"?**
Runner = the day's maximum intraday up-leg (any low → any later high, 1-min bars) clears the
trailing 60-day 80th percentile of that same statistic (causal, regime-adaptive). On QQQ
2025-26 the P80 was **1.41%** full-year (H1 1.14% / H2 1.60% — the mid-year vol regime split;
a fixed 1.6% bar ≈ H2's P80, which is why "hit 1.6%" felt right to the desk but is regime-loaded).

Feature families to test (all causal at 09:30 ET):
- **t-1..t-3 candles**: big bodies, pauses, streaks, thrust→pause sequences, prior day type
- **Overnight gap**: sign, magnitude, and gap scaled by prior-day range (`gap_over_prange`)
- **Premarket (04:00–09:29)**: range, volume vs typical, where the open sits in the PM range
- **Calendar**: FOMC/CPI/NFP days — needs a VERIFIED release calendar (see §5)
- **Your own ideas** — but every new feature enters the same battery with the same controls.

Phase-A scope: single-name US stocks (large/mid cap), ≥2 years of 1-min extended-hours data
each, ideally spanning 2022 (bear) / 2023 (chop→bull) / 2024 (bull). The QQQ findings in §2
are the priors to confirm/refute cross-sectionally. **A refutation is the most valuable output.**

## 2. What one year of QQQ already showed (247 clean days, 2025-06-30 → 2026-06-30 — IN-SAMPLE)

**Alive (pre-registered, awaiting your data for a verdict):**
1. **Big gap-DOWN → runner.** Event = `gap_over_prange` ≤ −0.35 (open minus prior RTH close,
   scaled by prior-day high−low). Runner rate ~36% vs 27.2% base. The quintile ladder is a
   **gap-down-vs-gap-up SPLIT, not strictly monotone**: down/flat quintiles run ~33–36%, the two
   gap-up quintiles drop to ~16%. Same sign in both half-years. 47 event days. Bounce low forms
   by 10:00 on 64% and by 10:30 on 74% of event days; the up-leg tops out ~13:20.
2. **Premarket-bounced refinement.** On event days, RTH open ≥0.3% above the premarket low →
   playbook long (buy 10:00 close, stop −1%, sell 13:30) = **+47.1 bps median, 68% hit, n=19**
   (H1/H2 +77/+45). Open ON the premarket low (still falling) → +7.6 bps, n=28 (and the sub-slice
   sitting right on the low is negative). Spearman(open-position-in-PM-range, pnl) = 0.31, p=0.03.
3. **Streak contraction.** After 3 consecutive up closes: runner rate **8.9% vs 27.2%**
   (p=0.004, the only Bonferroni survivor across the S battery, both halves). A NEGATIVE/filter
   signal, and it tracks the wide-day target too (8.9% vs 25.3%) → contraction, not direction.
4. **Thrust→pause.** Big up candle t-2 + small body t-1 → trend-day rate 36.4% vs 17.5% base
   (lift ~2.1×, both halves) — but **n=11 only**. Promising shape, underpowered.

**Dead on QQQ (do NOT resurrect without cross-sectional evidence):**
- Big up candle t-1 → continuation: INVERTED (trend-day rate 4.5% vs 17.5%); big-up days almost
  never chain (two-in-a-row happened ONCE in the year).
- Gap-UP momentum: INVERTED (the big gap-up quintile has the LOWEST runner rate, ~16%).
- Econ-release direction: FOMC/NFP days are WIDE, not directional (NFP-rule wide-rate 55.6% vs
  25.3%; FOMC 0/7 up-runners). Flags were approximate — see §5.
- Premarket range/volume as DIRECTIONAL signals: their runner ladders track the wide-day
  (Y_wide) ladders almost 1:1 — they forecast VOLATILITY only.

## 3. The framework (code in this package)

```
python universe_study.py <data_dir> [label]     # THE MAIN TOOL — per-symbol S battery
                                                #   + cross-sectional sign-test aggregation
python oos_validate.py   <csv> <label>          # frozen QQQ-claim verdicts on one new file
python runners.py / premarket.py / gapfade.py   # single-symbol batteries (QQQ parquet paths)
```

`universe_study.py` per symbol: auto day-hygiene (≥350/390 RTH bars, grid reindex + ffill),
liquidity gate (median daily $vol ≥ $50M, ≥120 clean days), the S battery
(features × {Y_up_trail, **Y_wide**}), gap-ladder extremes, PM-bounced split. Aggregation:
median lift across symbols, % positive, **two-sided sign test**. A claim is real only if it
holds across MANY symbols — one ticker's history is not evidence.

**The Y_wide pairing is the core discipline**: every feature is scored against the runner target
AND the wide-day target. A claim is DIRECTIONAL only if its Y_up_trail effect exceeds its own
Y_wide effect. QQQ Phase 1's central lesson — *volatility clusters (0.44, z=7.3), direction does
not (~0)* — means most "predictors" are volatility forecasts in disguise. The self-test makes
this visible: NFP-rule days score +30pp on Y_wide but −5pp on Y_up_trail.

`oos_validate.py` runs the FROZEN claims C1–C5 (gap ladder / up3 / thrust-pause / playbook /
PM-check) and prints CONFIRMED / WEAKENED / REFUTED with pre-set thresholds — no re-tuning
possible by construction. Self-test on the 2025-26 file reproduces every §2 number and returns
all-CONFIRMED (that is the baseline, NOT a result on new data).

Data format (per symbol, one CSV, `SYMBOL[_anything].csv`):
`timestamp_et` (day-first `%d/%m/%Y %H:%M`), `open, high, low, close, volume[, trade_count]`,
extended hours 04:00–19:59 ET included, **UNADJUSTED prices** (see §5).

Deps: python 3.12, pandas, numpy, scipy, pyarrow, tabulate (openpyxl/plotly optional).

## 4. Methodological requirements (non-negotiable — each exists because it killed a false lead)

1. **Causality**: every threshold trailing + `shift(1)`; features computable at 09:30:00 sharp.
2. **Vol control**: report the Y_wide twin for every claim (§3). No exceptions.
3. **Matched nulls**: base rate beside every conditional rate; level / mean-reversion claims need
   a random-point control (the Phase-1 PDH/PDL trap: ANY minute "reverts" 78–83% of the time, so
   a level must beat a random-anchor control, not an absolute threshold).
4. **Splits**: H1/H2 same-sign within each symbol; cross-sectional sign test across symbols;
   report per regime year (2022 vs 2023 vs 2024). A bounce edge that lives only in bull years is
   a drift artifact — which is exactly the open question for the gap-down finding.
5. **Multiplicity**: Bonferroni within each feature battery; the sign test handles the
   cross-symbol dimension. Report n and effect size with EVERY number.
6. **Economics in bps net of costs** (≥1 tick/side, pessimistic same-bar stop fills), never in
   R-multiples of narrow stops (the R-frame mechanically favours narrow ORs — Phase-1 §4b.7).
7. **Adjustment**: dividend-adjusted data fabricates ~0.5% quarterly gaps → poisons every gap
   feature. Sanity check: |overnight gap| on ex-div dates should not stand out from other dates.

## 5. Known gotchas (learned the hard way)

- Parse `timestamp_et` **day-first**. Date join keys as **strings** (`YYYY-MM-DD`), never dates.
- Vendor VWAP columns are often premarket-anchored — recompute session VWAP from 09:30 if used.
- Missing minute bars are NORMAL in single stocks (unlike QQQ): the framework reindexes and
  ffills close (volume 0). For thin names, verify up-leg stats aren't ffill artifacts before
  trusting them — the $50M liquidity gate is the first defense; tighten it if needed.
- pandas 3.x: `groupby.apply` needs `include_groups=False`.
- Econ calendar: the Oct–Nov 2025 US government shutdown shifted real release dates; use a
  verified dates file, not day-of-month rules (NFP-first-Friday was an approximation only).
- Half-day sessions (day after Thanksgiving, Christmas Eve) auto-drop via the bar-count gate.

## 6. Deliverables expected back

1. **UNIV summary tables** per regime year and pooled, with the Y_up_trail vs Y_wide pairing.
2. **Verdict per §2 prior** (CONFIRMED / WEAKENED / REFUTED cross-sectionally), especially:
   does gap-down→runner survive 2022?
3. **Interaction cuts**: effect vs market cap / beta / sector; single names vs the QQQ/SPY index
   ETFs (is the bounce an index-arb phenomenon or a single-stock phenomenon?).
4. **New features** you tested, in the same battery format, with multiplicity accounting.
5. If gap-down→bounce survives: per-symbol playbook economics (the frozen spec, §9) and a
   PORTFOLIO simulation across names — gap-down events are CORRELATED across symbols (many names
   gap down together), so size for the day's aggregate exposure, not per symbol.

## 7. Package manifest

Code: full Phase-1 + Phase-1.5 stack (`ingest, runners, premarket, gapfade, gap_playbook,
gap_backtest, universe_study, oos_validate, analytics, or_break, system_backtest, ...`).
Docs: this file + `HANDOFF.md` (full Phase-1 context, analyses A–R + S/T/U/V/W).
Reference results (in-sample baselines, NOT new-data results): `output/tables/S_*, T_*, U_*, V_*,
W_*, UNIV_SELFTEST_*, OOS_SELFTEST_*`; decks `output/runner_study.html`, `gap_onepage.html`,
`gap_equity_curve.html`. Data: `QQQ_1min_1y_TH.csv` (self-test baseline).

## 8. Analysis-letter map — READ THIS TO AVOID COLLISIONS

Two Claude sessions worked this project in parallel and their FINDINGS letters DIVERGED. When
you read any deck or note, confirm which branch it came from:

- **This (data-mining) branch** — analyses A–R (market structure + the OR-break R-system,
  HANDOFF.md), then **S** = runner precursors, **T** = gap-down bounce anatomy, **U** = playbook
  parameters, **V** = premarket features, **W** = $100k gap-playbook backtest.
- **The desk/implementation branch** — packaged the SAME R-system as "Trade 1" and added a NEW
  **afternoon "noon-check" long** as "Trade 2" (12:00: today's LOW set before 10:00 AND still the
  low AND price > session VWAP → buy at market, target = standing HOD, stop = trailing session
  VWAP, flat 15:57). Their docs label things "A–T" differently and reference `late_onepage.html`.
  Reproduced from our data: the noon-check fires **87/247 days (7.2/mo)**, and those days are 41%
  trend-up vs 17% base — a real Phase-1-lineage signal, still in-sample.

**Overlap warning if the desk runs both books**: 53% of PM-checked gap-playbook days (10/19) and
47% of gap-down event days (22/47) ALSO fire the noon-check → doubled same-day long exposure with
conflicting exits (playbook sells 13:30; noon-check trails VWAP to 15:57). Treat gap-down as a
size/priority INPUT to one afternoon book, not a third standalone system. Do NOT merge the two
letter schemes without a reconciliation pass.

## 9. CANONICAL numbers (use these verbatim — errata from the recheck)

Recomputed fresh 2026-07-06. If any deck disagrees, the deck is wrong:

| Fact | Canonical value | Common wrong value seen |
|---|---|---|
| OR30 break by 10:30 | **75%** of days (185/247) | — |
| OR30 first break returns inside by 11:00 (fakeout) | **91%** (169/185) | "74% / ~3 in 4" (that is the OR5 number) |
| R-system, $10k @1% | +11.0%/yr, −3.8% DD, 62% win, 21% stop-outs, 61 trades | — |
| Late first-retest → failure? | **NO** — flat 48–56%, tested & refuted (§4b.6) | "late fills disproportionately fail" |
| Runner up-leg P80 | 1.41% full / 1.14% H1 / 1.60% H2 | "1.6%" stated as a full-year threshold |
| Gap ladder shape | gap-down-vs-gap-up SPLIT (~33–36% vs ~16%) | "monotone" |
| Gap-down event base | `gap_over_prange` ≤ −0.35, n=47, runner ~36% vs 27.2% | mixing in the 43% from raw `gap_pct` |
| Gap playbook (frozen spec) | gap≤−0.35×prange & open≥0.3% above PM low → BUY 10:00 close, STOP −1.0%, SELL 13:30, 1 tick/side | — |
| Gap playbook, PM-checked | +47.1 bps med, 68% hit, n=19 (H1/H2 +77/+45) | — |
| Gap playbook $100k @1% | +5.9%/yr, −1.4% DD, 0.31 avg R, n=19 | — |
| Noon-check (other branch) | fires 87/247 (7.2/mo), 41% trend-up vs 17% base | — |

**Status of everything above: IN-SAMPLE on one +32% drift year. Nothing is a proven edge.
The OOS gate (2022–24, §4 + §6.2) is the only thing that promotes any of it to real.**

## 10. Suggested opening instruction for the research session

> "Read HANDOFF_RESEARCH.md fully, then HANDOFF.md §2/§4b for deep background. The QQQ priors in
> §2 are settled IN-SAMPLE — do not re-derive them on the included QQQ file (it is the self-test
> baseline only). Use §9's canonical numbers, never numbers copied from a deck. Our data: ⟨N⟩
> symbols, ⟨years⟩, at ⟨path⟩, format per §3. Run universe_study.py per regime year, apply §4 to
> anything new, report deliverables §6.1–6.5. Flag anything that contradicts a §2 prior LOUDLY —
> that is the most valuable output, not a failure."
