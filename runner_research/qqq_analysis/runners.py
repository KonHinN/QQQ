"""
runners.py — Analysis S: prior-day (t-1..t-3) + overnight precursors of "runner" days.

Question: which features known BEFORE today's open (or at the open, for the gap) raise
the probability that today is an up-runner / trend-up day?

Targets (per clean day t0):
  up_leg_pct   = max intraday up-LEG: max over t of (high_t - min(low_0..t)) / min(low_0..t)
                 i.e. the biggest low->subsequent-high swing anywhere in the day (minute data)
  Y_up_trail   : up_leg_pct >= trailing 60-day 80th pctl of up_leg_pct (causal, shift 1)
  Y_up_fixed   : up_leg_pct >= 1.6  (user's fixed threshold — regime-sensitive, robustness only)
  (up_run_pct = open->high kept as a reference column)
  Y_trend_up   : oc_over_range >= 0.65 and close > open   (J1 rule taxonomy)
  Y_wide       : day_range_pct >= trailing 60-day 80th pctl (VOL control — a feature that
                 "predicts" Y_up but predicts Y_wide equally is just vol clustering)

Features (ALL causal at 09:30 of t0 — prior-day bodies use trailing-quantile thresholds
with shift(1); the gap is known at the open):
  big_up1        t-1 body (o->c) >= trailing P80 of |body| and up
  big_up2        t-2 same
  two_big_up     big_up1 & big_up2 (continuation hypothesis)
  thrust_pause   t-2 big up, t-1 small body (|body| <= trailing P40)  (pause hypothesis)
  up3            three consecutive up closes (t-3,t-2,t-1)
  prior_trend_up t-1 was a J1 trend_up day
  gap_up         gap_pct > 0
  gap buckets    gap_pct quintiles + gap/prior-range quintiles (tests "too much gap is bad")
  fomc / nfp     approximate econ flags (FOMC decision days hardcoded; NFP = first trading
                 Friday rule). NOTE: Oct-Nov 2025 shutdown delayed releases — flags there
                 are unreliable; treat econ rows as indicative only until verified calendar.

Stats per binary feature: n, P(Y|f) vs base rate, lift, bootstrap 95% CI on the difference,
binomial p vs base rate, H1/H2 same-sign check, Bonferroni across the battery.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

OUT_DIR = Path(__file__).resolve().parent / "output"
TAB_DIR = OUT_DIR / "tables"
TAB_DIR.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(7)
TRAIL_W, TRAIL_MIN = 60, 30          # trailing window for causal quantiles
NORM_W, NORM_MIN = 20, 10            # trailing window for body normalization

# FOMC decision days inside 2025-06-30 .. 2026-06-30 (scheduled; decision = day 2)
FOMC = {"2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17"}


# ---------------------------------------------------------------- max intraday up-leg
def max_upleg(m: pd.DataFrame) -> pd.DataFrame:
    """Per day: biggest low->subsequent-high swing (%), plus the minutes at which the
    leg's low was set and its high was reached (for timing analysis)."""
    m = m[m.is_clean].sort_values(["date", "minute_index"])
    rows = []
    for dte, g in m.groupby("date", sort=True):
        lo = g.low.cummin().to_numpy()
        hi = g.high.to_numpy()
        leg = (hi - lo) / lo * 100
        i = int(np.argmax(leg))
        # minute where the leg's low was set = last cummin update at or before i
        j = int(np.max(np.where(g.low.to_numpy()[:i + 1] <= lo[i] + 1e-9)))
        mi = g.minute_index.to_numpy()
        rows.append(dict(date=dte, up_leg_pct=float(leg[i]),
                         leg_low_min=int(mi[j]), leg_high_min=int(mi[i])))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- frame
def build_frame(d: pd.DataFrame, m: pd.DataFrame | None = None) -> pd.DataFrame:
    d = d[d.is_clean].copy().sort_values("date").reset_index(drop=True)
    if m is None:
        m = pd.read_parquet(OUT_DIR / "minute.parquet")
    d = d.merge(max_upleg(m), on="date", how="left")
    d["up_run_pct"] = (d.rth_high - d.rth_open) / d.rth_open * 100
    d["dn_run_pct"] = (d.rth_open - d.rth_low) / d.rth_open * 100
    d["range_pct"] = d.day_range / d.rth_open * 100
    d["body"] = d.rth_close - d.rth_open
    d["body_pct"] = d.body / d.rth_open * 100
    d["oc_over_range"] = d.body.abs() / d.day_range
    d["ret_cc"] = d.rth_close.pct_change() * 100
    half = len(d) // 2
    d["half"] = ["H1"] * half + ["H2"] * (len(d) - half)

    # ---- causal trailing quantiles (shift(1): today never sees itself)
    trail_q = lambda s, q: s.rolling(TRAIL_W, min_periods=TRAIL_MIN).quantile(q).shift(1)
    d["thr_up_run"] = trail_q(d.up_leg_pct, 0.8)
    d["thr_range"] = trail_q(d.range_pct, 0.8)
    abs_body = d.body_pct.abs()
    d["thr_body_big"] = abs_body.rolling(NORM_W, min_periods=NORM_MIN).quantile(0.8).shift(1)
    d["thr_body_small"] = abs_body.rolling(NORM_W, min_periods=NORM_MIN).quantile(0.4).shift(1)

    # ---- targets
    d["Y_up_trail"] = (d.up_leg_pct >= d.thr_up_run)
    d["Y_up_fixed"] = (d.up_leg_pct >= 1.6)
    d["Y_trend_up"] = (d.oc_over_range >= 0.65) & (d.body > 0)
    d["Y_wide"] = (d.range_pct >= d.thr_range)

    # ---- prior-day features (thresholds evaluated at the PRIOR day's own date, then shifted)
    big_up = (d.body_pct >= d.thr_body_big) & (d.body > 0)
    small = abs_body <= d.thr_body_small
    up_close = d.ret_cc > 0
    d["big_up1"] = big_up.shift(1)
    d["big_up2"] = big_up.shift(2)
    d["two_big_up"] = d.big_up1.astype("boolean") & d.big_up2.astype("boolean")
    d["pause1"] = small.shift(1)
    d["thrust_pause"] = d.big_up2.astype("boolean") & d.pause1.astype("boolean")
    d["up3"] = (up_close.shift(1).astype("boolean") & up_close.shift(2).astype("boolean")
                & up_close.shift(3).astype("boolean"))
    trend_up_day = (d.oc_over_range >= 0.65) & (d.body > 0)
    d["prior_trend_up"] = trend_up_day.shift(1)

    # ---- overnight gap (known at 09:30). prior range for scaling must be t-1's range.
    d["gap_over_prange"] = d.gap / d.day_range.shift(1)
    d["gap_up"] = d.gap_pct > 0

    # ---- econ flags (approximate — see module docstring)
    d["fomc"] = d.date.isin(FOMC)
    et = pd.to_datetime(d.date)
    is_fri = et.dt.weekday == 4
    first_fri = is_fri & (et.dt.day <= 7)
    d["nfp_rule"] = first_fri

    return d


# ---------------------------------------------------------------- stats
def _boot_ci(y_f: np.ndarray, y_all: np.ndarray, n_boot: int = 4000) -> tuple[float, float]:
    """Bootstrap 95% CI on P(Y|f) - P(Y) (resample both groups)."""
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        a = RNG.choice(y_f, len(y_f), replace=True).mean()
        b = RNG.choice(y_all, len(y_all), replace=True).mean()
        diffs[i] = a - b
    return tuple(np.percentile(diffs, [2.5, 97.5]))


def _binom_p(k: int, n: int, p0: float) -> float:
    from scipy.stats import binomtest
    return binomtest(k, n, p0).pvalue if n > 0 else np.nan


def eval_binary(d: pd.DataFrame, feat: str, target: str) -> dict:
    sub = d.dropna(subset=[feat, target, "thr_up_run"])   # common warm-up mask
    f = sub[feat].astype(bool)
    y = sub[target].astype(bool).to_numpy()
    yf = y[f.to_numpy()]
    n_f = len(yf)
    base = y.mean()
    rate = yf.mean() if n_f else np.nan
    lo, hi = _boot_ci(yf.astype(float), y.astype(float)) if n_f >= 5 else (np.nan, np.nan)
    pval = _binom_p(int(yf.sum()), n_f, base) if n_f else np.nan
    # H1/H2 same-sign of the lift
    signs = []
    for h in ("H1", "H2"):
        s = sub[sub.half == h]
        fh = s[feat].astype(bool)
        if fh.sum() >= 5:
            signs.append(np.sign(s.loc[fh, target].astype(bool).mean()
                                 - s[target].astype(bool).mean()))
    same_sign = (len(signs) == 2 and signs[0] == signs[1] and signs[0] != 0)
    return dict(feature=feat, target=target, n_f=n_f, n_all=len(y),
                base_pct=round(base * 100, 1), rate_pct=round(rate * 100, 1) if n_f else np.nan,
                lift=round(rate / base, 2) if n_f and base > 0 else np.nan,
                diff_pp=round((rate - base) * 100, 1) if n_f else np.nan,
                ci_lo_pp=round(lo * 100, 1), ci_hi_pp=round(hi * 100, 1),
                p_binom=round(pval, 4) if n_f else np.nan, h1h2_same_sign=same_sign)


def eval_buckets(d: pd.DataFrame, col: str, target: str, q: int = 5) -> pd.DataFrame:
    sub = d.dropna(subset=[col, target, "thr_up_run"]).copy()
    sub["bucket"] = pd.qcut(sub[col], q, duplicates="drop")
    base = sub[target].astype(bool).mean()
    rows = []
    for b, g in sub.groupby("bucket", observed=True):
        rows.append(dict(col=col, target=target, bucket=str(b), n=len(g),
                         rate_pct=round(g[target].astype(bool).mean() * 100, 1),
                         base_pct=round(base * 100, 1),
                         med_val=round(g[col].median(), 3)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- run
BINARY_FEATS = ["big_up1", "big_up2", "two_big_up", "pause1", "thrust_pause",
                "up3", "prior_trend_up", "gap_up", "fomc", "nfp_rule"]
TARGETS = ["Y_up_trail", "Y_up_fixed", "Y_trend_up", "Y_wide"]


def run(d: pd.DataFrame) -> dict:
    d = build_frame(d)

    rows = [eval_binary(d, f, t) for f in BINARY_FEATS for t in TARGETS]
    tab = pd.DataFrame(rows)
    # Bonferroni over the primary battery: binary feats x Y_up_trail only
    m = len(BINARY_FEATS)
    tab["bonf_sig"] = (tab.target == "Y_up_trail") & (tab.p_binom < 0.05 / m)

    buck = pd.concat([eval_buckets(d, c, t)
                      for c in ("gap_pct", "gap_over_prange")
                      for t in ("Y_up_trail", "Y_trend_up", "Y_wide")],
                     ignore_index=True)

    # empirical percentile check for the user's 1.6% anchor (on max intraday up-leg)
    ur = d.up_leg_pct.dropna()
    pctl_info = pd.DataFrame([dict(
        n_days=len(ur), P80_full=round(ur.quantile(0.8), 2),
        P80_H1=round(d[d.half == "H1"].up_leg_pct.quantile(0.8), 2),
        P80_H2=round(d[d.half == "H2"].up_leg_pct.quantile(0.8), 2),
        fixed_1p6_hit_pct=round((ur >= 1.6).mean() * 100, 1))])

    tab.to_csv(TAB_DIR / "S_runner_precursors.csv", index=False)
    buck.to_csv(TAB_DIR / "S_runner_gap_buckets.csv", index=False)
    pctl_info.to_csv(TAB_DIR / "S_runner_target_pctls.csv", index=False)
    return {"S_binary": tab, "S_buckets": buck, "S_pctls": pctl_info, "frame": d}


if __name__ == "__main__":
    daily = pd.read_parquet(OUT_DIR / "daily.parquet")
    res = run(daily)
    from tabulate import tabulate as tb
    print("\n=== S0 target percentile check (is 1.6% the P80 of up-run?) ===")
    print(tb(res["S_pctls"], headers="keys", showindex=False))
    print("\n=== S1 binary precursors x targets ===")
    print(tb(res["S_binary"], headers="keys", showindex=False))
    print("\n=== S2 gap buckets (monotone or inverted-U?) ===")
    print(tb(res["S_buckets"], headers="keys", showindex=False))
