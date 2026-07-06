# Review — `runner_research` handoff package (received 2026-07-06)

Package: `runner_research_handoff.zip` (QQQ intraday study, Phase 1 + Phase 1.5; runner-precursor
research mission per `qqq_analysis/HANDOFF_RESEARCH.md`). Reviewed by unpacking, reading all
handoff docs and the core modules, and **re-running the shipped self-tests from scratch**.

## Verdict

The package is in very good shape and ready to use for the Phase-A mission, with **one real bug
that must be fixed before running `universe_study.py` on a stock universe** (the liquidity gate),
and a handful of lower-severity caveats to keep in mind. Documentation quality is exceptional:
every canonical number in `HANDOFF_RESEARCH.md` §9 that I checked reproduces exactly from the code.

## What was verified

1. **`oos_validate.py` self-test reproduces exactly.** Fresh environment (Python 3.11,
   pandas 3.0.3), `python ingest.py` then `python oos_validate.py ../QQQ_1min_1y_TH.csv X`
   reproduced every number in the shipped `output/OOS_SELFTEST_2025_26_verdicts.md` to the
   decimal: C1 36.4/27.2/15.9 (n=44/44), C2 8.9% (n=45), C3 36.4 vs 17.5 (n=11),
   C4 +20.2 bps / 60% / +16.8/+21.1 (n=47), C5 +47.1 (n=19) vs +7.6 (n=28). All CONFIRMED.
2. **`universe_study.py` self-test reproduces exactly.** Rerun output matches the shipped
   `UNIV_SELFTEST_summary.csv` row for row (both `Y_up_trail` and `Y_wide` batteries).
3. **Causality spot-checks pass.** Trailing thresholds use `.rolling(...).quantile(q).shift(1)`;
   prior-day features are `shift(1..3)` of same-day quantities; the playbook entry/stop/exit uses
   only bar-30-and-later prices; fills are pessimistic (entry +1 tick, exit −1 tick, intrabar stop
   touch counted, including the entry bar's own low). No look-ahead found in
   `runners.py`, `premarket.py`, `gapfade.py`, `gap_playbook.py`, `gap_backtest.py`,
   `oos_validate.py`, `universe_study.py`.
4. **Manifest is complete** against `HANDOFF_RESEARCH.md` §7: all listed code, reference tables
   (`S_*, T_*, U_*, V_*, W_*, UNIV_SELFTEST_*, OOS_SELFTEST_*`), decks, and the QQQ baseline CSV
   are present. (`FINDINGS.md`/xlsx from the Phase-1 manifest in `HANDOFF.md` §7 are not in this
   zip — by design; this is the research subset.)

## Findings

### F1 — BUG (fix before universe runs): liquidity gate in `universe_study.py` is index-misaligned

`study_symbol()` (`universe_study.py:85-88`) computes median daily dollar volume as:

```python
dv = (daily[daily.is_clean].rth_close * 0).add(
    rth[rth.is_clean].groupby("date").apply(
        lambda g: (g.close * g.volume).sum(), include_groups=False), fill_value=0)
```

The left series is indexed by **integer row position**, the right by **date string**. `.add(...,
fill_value=0)` therefore unions the two indexes instead of aligning them, producing N zeros plus
the N real values. `dv.median()` then returns ≈ half the *minimum* day's dollar volume, not the
median. Verified on the QQQ baseline: code yields **$6.85B** where the true median is **$27.3B**
(the shipped run's log line `med_$vol=6854M` shows the bug was live when the reference tables were
made — QQQ is so liquid it passed anyway, so no shipped result is affected).

Consequences on a real universe: the `MIN_DOLLAR_VOL = $50M` gate effectively becomes
"minimum-day dollar volume ≥ $100M" — far stricter than documented — so mid-caps that genuinely
pass the intended median test get **silently skipped**, and the skip-log dollar figures are wrong.
Fix is one line:

```python
dv = rth[rth.is_clean].groupby("date").apply(
    lambda g: (g.close * g.volume).sum(), include_groups=False)
```

### F2 — Caveat: t-1 features skip excluded days (`runners.py::build_frame`)

`build_frame` filters to clean days **first**, then applies `shift(1..3)`. So when the actual
prior calendar trading day was excluded, "t-1" features (bodies, `up3`, `prior_trend_up`, and the
`gap_over_prange` **denominator** `day_range.shift(1)`) come from the prior *clean* day, while
`gap`/`gap_pct` (computed in `ingest.derive_daily` before filtering) use the *actual* prior day's
close. Mixed-reference features on those days. On QQQ this touches only 4 of 247 days
(2025-07-01, 2025-07-07, 2025-12-01, 2025-12-26 — verified), so shipped numbers are essentially
unaffected. But single stocks will have more excluded days (bar-count hygiene), so either drop
days whose true prior day was excluded, or accept and document the noise. Worth a decision before
the universe run.

### F3 — Trap: `ingest.derive_daily` hardcodes the QQQ 2025-26 exclusion list

`prior_is_full` is computed against the hardcoded `EXCLUDE` set (`ingest.py:33-35`), which is
meaningless for any other dataset. `oos_validate.py` and `universe_study.py` don't use
`prior_is_full` downstream, so they are safe as shipped — but anyone reusing `derive_daily` for
level analyses on new data (Phase-2 item 4) will get a silently wrong flag. Should take the
exclusion set as a parameter.

### F4 — Minor: `oos_validate.py` conflates "insufficient n" with REFUTED for C2/C3

C5 correctly reports "insufficient n" when the split is too thin, but C2 (needs n≥10) and C3
(needs n≥8) fall through to **REFUTED** when under-sampled (the `strong`/`weak` booleans are just
False). On a short or quiet OOS file, "not enough up3 streaks" would print as a refutation of the
claim. Low-probability on 1y+ files, but the verdict semantics matter for this project.

### F5 — Minor: H1/H2 = sample halves, not regime years

`build_frame` defines `half` as the first/second half of the row count. On a multi-year OOS file
the harness's "both halves same-sign" check therefore spans regime boundaries, while
`HANDOFF_RESEARCH.md` §4.4 requires per-regime-year reporting. The harness alone won't produce
that; per-year runs (or splitting input CSVs by year) are needed to satisfy the methodology the
docs demand. Not a bug — a workflow note.

### F6 — Cosmetic

- `gap_playbook.py:110` dead placeholder line (immediately overwritten at 112).
- `gap_playbook.py:128` dead expression (overwritten at 129).
- `oos_validate.py` C2/C3 detail strings format `nan` when n is insufficient.

## Strengths worth calling out

- The Y_wide vol-control pairing is enforced in code, not just prose — every battery emits both
  targets, and the self-test demonstrates the NFP case (+30pp wide, −5pp directional).
- Frozen-spec verdicts with pre-set thresholds make re-tuning structurally impossible.
- Costs, pessimistic fills, n and both-halves splits appear on every economic number.
- The docs' "common wrong value" errata table (§9) and the two-branch letter-collision warning
  (§8) are exactly what prevents handoff drift.

## Recommended next steps

1. Apply the F1 one-line fix (and rerun the UNIV self-test to confirm identical output).
2. Decide the F2 policy for single names before the universe run.
3. When OOS data arrives, run `oos_validate.py` per year (F5) and read C2/C3 verdicts together
   with their reported n (F4).
