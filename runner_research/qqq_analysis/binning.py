"""
binning.py — Time-resolution enhancements (answer to "15-min blocks vs per-minute?").

Empirical finding (see resolution_stability): uniform coarsening HURTS the signed-return
profile (H1/H2 corr 0.11 @1min -> 0.34 @5min -> NEGATIVE @15min+), while range/volume are
already stable at any resolution. The signal lives at the OPEN, so the right design is an
ADAPTIVE grid (fine at open, coarse midday, medium into close) + ATR-normalisation to
neutralise the mid-year volatility-regime shift.

Adds:
  * time_grid(kind)          — uniform(k) or 'adaptive' bucket edges
  * resolution_stability()   — H1/H2 correlation of the profile vs bin width (the evidence)
  * profile_binned(grid)     — median+IQR+bootstrap-CI per bucket, incl. ATR-normalised moves
Outputs go to output/tables/ and are wired into the Excel workbook + a markdown addendum.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, _clk, N_MIN

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
RNG = np.random.default_rng(42)


# ---------------------------------------------------------------- grids
def time_grid(kind="adaptive"):
    """Return sorted bucket edges (minute_index) covering 0..390.
    'adaptive' = 1-min at the open & close, 5-min in the ramps, 15-min midday."""
    if isinstance(kind, int):                       # uniform k-min
        edges = list(range(0, N_MIN, kind)) + [N_MIN]
        return sorted(set(edges))
    if kind == "adaptive":
        edges = (list(range(0, 15, 1))              # 09:30-09:44  1-min  (opening reversal window)
                 + list(range(15, 60, 5))           # 09:45-10:29  5-min  (morning ramp)
                 + list(range(60, 300, 15))         # 10:30-14:29 15-min  (midday lull, coarse)
                 + list(range(300, 375, 5))         # 14:30-15:44  5-min  (power-hour ramp)
                 + list(range(375, 390, 1)) + [390])# 15:45-15:59  1-min  (closing auction)
        return sorted(set(edges))
    raise ValueError(kind)


def _assign(minute_index: pd.Series, edges) -> pd.Series:
    """Map each minute to its bucket START minute (label = clock of bucket start)."""
    edges = np.asarray(edges)
    idx = np.searchsorted(edges, minute_index.to_numpy(), side="right") - 1
    idx = np.clip(idx, 0, len(edges) - 2)
    return pd.Series(edges[idx], index=minute_index.index)


# ---------------------------------------------------------------- evidence: stability vs bin width
def resolution_stability(m: pd.DataFrame) -> pd.DataFrame:
    c = m[m.is_clean].copy()
    days = sorted(c.date.unique()); h = len(days) // 2
    h1, h2 = set(days[:h]), set(days[h:])
    c["half"] = np.where(c.date.isin(h1), "H1", "H2")
    rows = []
    for b in [1, 3, 5, 10, 15, 30, 60]:
        c["blk"] = c["minute_index"] // b
        rec = {"bin_min": b, "n_buckets": int(np.ceil(N_MIN / b))}
        for field, lbl in [("ret_bps", "ret"), ("ret_atr", "ret_atr_norm"),
                           ("range", "range"), ("volume", "volume")]:
            g = c.groupby(["half", "blk"])[field].median().unstack(0).dropna()
            rec[f"{lbl}_H1H2_corr"] = round(g["H1"].corr(g["H2"]), 3)
        rows.append(rec)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- adaptive/binned profile
def _boot_median_ci(x: np.ndarray, n=500, lo=2.5, hi=97.5):
    x = x[~np.isnan(x)]
    if len(x) < 5:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    meds = np.median(x[idx], axis=1)
    return (np.percentile(meds, lo), np.percentile(meds, hi))


def profile_binned(m: pd.DataFrame, kind="adaptive") -> pd.DataFrame:
    c = m[m.is_clean].copy()
    edges = time_grid(kind)
    c["bucket"] = _assign(c["minute_index"], edges)
    c["up"] = (c["close"] > c["open"]).astype(float)
    rows = []
    for bstart, g in c.groupby("bucket"):
        width = int(edges[edges.index(bstart) + 1] - bstart) if bstart in edges else 1
        rec = {"bucket_start": int(bstart), "clock": _clk(int(bstart)),
               "width_min": width, "n_obs": len(g), "n_days": g.date.nunique()}
        for col, pre in [("ret_bps", "ret_bps"), ("ret_atr", "ret_atr"),
                         ("range", "range"), ("volume", "vol")]:
            rec[f"{pre}_med"] = round(g[col].median(), 4)
            rec[f"{pre}_q25"] = round(g[col].quantile(.25), 4)
            rec[f"{pre}_q75"] = round(g[col].quantile(.75), 4)
        lo, hi = _boot_median_ci(g["ret_bps"].to_numpy())
        rec["ret_bps_ci_lo"] = round(lo, 3); rec["ret_bps_ci_hi"] = round(hi, 3)
        # is the bucket's median return distinguishable from 0? (bootstrap CI excludes 0)
        rec["ret_sig"] = bool((lo > 0) or (hi < 0)) if np.isfinite(lo) else False
        rec["pct_up"] = round(g["up"].mean() * 100, 1)
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("bucket_start").reset_index(drop=True)


# ---------------------------------------------------------------- run + persist
def run(write=True):
    m, d = load()
    res = {
        "H_resolution_stability": resolution_stability(m),
        "H_profile_adaptive": profile_binned(m, "adaptive"),
        "H_profile_5min": profile_binned(m, 5),
        "H_profile_15min": profile_binned(m, 15),
    }
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[binning] wrote", ", ".join(res))
        for k, v in res.items():
            print(f"  {k:26s} {tuple(v.shape)}")
    return res


if __name__ == "__main__":
    r = run()
    print("\n=== resolution stability (H1/H2 corr) ===")
    print(r["H_resolution_stability"].to_string(index=False))
    print("\n=== adaptive profile: buckets whose median return is bootstrap-significant ===")
    ad = r["H_profile_adaptive"]
    print(ad[ad.ret_sig][["clock", "width_min", "n_obs", "ret_bps_med", "ret_bps_ci_lo", "ret_bps_ci_hi", "pct_up"]].to_string(index=False))
