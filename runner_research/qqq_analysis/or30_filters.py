"""
or30_filters.py — Pre-registered filter battery for the OR30 system, QQQ only.

The frozen OR30 spec failed OOS (see OOS_PLAYBOOK_REPORT.md). This tests whether a DAY-TYPE
filter rescues it. Protocol as before: filters explored on DEV = QQQ 2018-2021; only the
DEV winner(s) get scored on VAL = QQQ 2022-2024 (single look). 2025-26 reported as reference
(the spec's own in-sample year). 8 filters — Bonferroni-level skepticism applies.

Filters (all knowable before/at entry; trailing stats reset each year file, ~20-60d warm-up):
  gap_align      take the trade only if overnight gap sign == break side (0 gap counts as align)
  gap_opposed    only if gap sign != break side (the complement — fade-the-gap breaks)
  no_big_gap     skip |gap/prior range| >= 0.35 days (gap-event days belong to the bounce book)
  after_gap_day  only if YESTERDAY was a big-gap day (|gap/prange| >= 0.35)      [user idea]
  uptrend        only if prior close > prior SMA20                               [user idea]
  downtrend      complement (bear-regime breaks)
  trend_side     longs only in uptrend, shorts only in downtrend
  narrow_or      OR30 width <= trailing 60d median (shift 1); wide_or = complement

    python or30_filters.py
Outputs -> tables/ORF_dev.csv, ORF_val.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

from oos_playbooks import load_file
from oos_improve import or30_trades, or30_year_return

TBL = Path(__file__).resolve().parent / "output" / "tables"
DEV = [f"../oos_data/QQQ_1min_{y}.csv" for y in (2018, 2019, 2020, 2021)]
VAL = [f"../oos_data/QQQ_1min_{y}.csv" for y in (2022, 2023, 2024)]
REF = ["../QQQ_1min_1y_TH.csv"]


def day_features(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.sort_values("date").reset_index(drop=True)
    d["gap_over_prange"] = d.gap / d.day_range.shift(1)
    d["big_gap"] = d.gap_over_prange.abs() >= 0.35
    d["after_gap_day"] = d.big_gap.shift(1).astype("boolean").fillna(False)
    sma20 = d.rth_close.rolling(20, min_periods=20).mean()
    d["uptrend"] = (d.rth_close > sma20).shift(1).astype("boolean")   # known at today's open
    orw = d.or30_high - d.or30_low
    d["narrow_or"] = (orw <= orw.rolling(60, min_periods=20).median().shift(1))
    return d[["date", "gap", "gap_over_prange", "big_gap", "after_gap_day", "uptrend", "narrow_or"]]


FILTERS = {
    "baseline_all":  lambda t: pd.Series(True, index=t.index),
    "gap_align":     lambda t: np.sign(t.gap).fillna(0) * t.side >= 0,
    "gap_opposed":   lambda t: np.sign(t.gap).fillna(0) * t.side < 0,
    "no_big_gap":    lambda t: ~t.big_gap.astype(bool),
    "after_gap_day": lambda t: t.after_gap_day.astype(bool),
    "uptrend":       lambda t: t.uptrend.astype("boolean").fillna(False).astype(bool),
    "downtrend":     lambda t: (~t.uptrend.astype("boolean").fillna(True)).astype(bool),
    "trend_side":    lambda t: np.where(t.side == 1, t.uptrend.astype("boolean").fillna(False),
                                        ~t.uptrend.astype("boolean").fillna(True)).astype(bool),
    "narrow_or":     lambda t: t.narrow_or.astype("boolean").fillna(False).astype(bool),
    "wide_or":       lambda t: (~t.narrow_or.astype("boolean").fillna(True)).astype(bool),
}


def collect(files) -> dict[str, pd.DataFrame]:
    out = {}
    for f in files:
        p = Path(f)
        minute, daily = load_file(p)
        tr = or30_trades(minute)                      # frozen spec incl. short gate
        tr = tr.merge(day_features(daily), on="date", how="left")
        out[p.stem.replace("QQQ_1min_", "").replace("_1y_TH", "2025IS")] = tr
        print(f"[{p.stem}] {len(tr)} trades")
    return out


def score(trades_by_year: dict, mask_fn, name: str) -> dict:
    kept = {y: t[mask_fn(t)] for y, t in trades_by_year.items()}
    bps = pd.concat([k.net_bps for k in kept.values() if len(k)])
    yr = {y: or30_year_return(k) for y, k in kept.items() if len(k)}
    r = pd.Series(yr)
    return dict(filter=name, n_trades=len(bps),
                n_long=int(sum((k.side == 1).sum() for k in kept.values())),
                n_short=int(sum((k.side == -1).sum() for k in kept.values())),
                med_bps=round(bps.median(), 1), mean_bps=round(bps.mean(), 1),
                win_pct=round((bps > 0).mean() * 100, 1),
                avg_yr_ret_pct=round(r.mean(), 1), pos_years=f"{int((r>0).sum())}/{len(r)}",
                yearly=" ".join(f"{y[-2:]}:{v:+.1f}" for y, v in yr.items()))


def run():
    print("== DEV 2018-2021 ==")
    dev = collect(DEV)
    dev_tab = pd.DataFrame([score(dev, fn, nm) for nm, fn in FILTERS.items()])
    TBL.mkdir(parents=True, exist_ok=True)
    dev_tab.to_csv(TBL / "ORF_dev.csv", index=False)
    from tabulate import tabulate as tb
    print("\n=== DEV battery (QQQ 2018-2021, frozen OR30 spec + filter) ===")
    print(tb(dev_tab, headers="keys", showindex=False))
    return dev, dev_tab


if __name__ == "__main__":
    run()
