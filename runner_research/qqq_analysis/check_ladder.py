"""
check_ladder.py — Can the clock-study findings upgrade the noon-check into an earlier/two-sided
playbook? QQQ only. DEV 2018-2021 (selection) -> VAL 2022-2024 (single look) -> 2025-26 ref.

Candidates (motivated by the fresh time-of-day study: the day's best up-leg is born at/near the
open on ~46% of days and runs to ~14:30; LOD/HOD are edge-loaded; drift by clock alone = 0):
  LONG ladder : at check time T in {10:30, 11:00, 11:30, 12:00, 13:00}:
                LOD set before 10:00 AND still the LOD AND close > session VWAP
                -> buy T close; stop = 1-min close < VWAP (exit at that close, pessimistic);
                flat 15:57; 1 tick/side.  T=12:00 = the validated noon-check (baseline).
  SHORT mirror: HOD set before 10:00 AND still the HOD AND close < session VWAP
                -> sell T close; stop = 1-min close > VWAP; flat 15:57. Same T ladder.

    python check_ladder.py
Outputs -> tables/LADDER_dev.csv (+ printed VAL for the DEV pick, single look)
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

from oos_playbooks import load_file

TBL = Path(__file__).resolve().parent / "output" / "tables"
TICK = 0.01
FLAT_T = 387
TEN_AM = 30
CHECKS = {"10:30": 60, "11:00": 90, "11:30": 120, "12:00": 150, "13:00": 210}
DEV = [f"../oos_data/QQQ_1min_{y}.csv" for y in (2018, 2019, 2020, 2021)]
VAL = [f"../oos_data/QQQ_1min_{y}.csv" for y in (2022, 2023, 2024)]
REF = ["../QQQ_1min_1y_TH.csv"]

_cache: dict[str, dict] = {}


def pivots(f: str) -> dict:
    if f not in _cache:
        minute, _ = load_file(Path(f))
        m = minute[minute.is_clean]
        ok = m.groupby("date")["minute_index"].size() == 390
        m = m[m.date.isin(ok[ok].index)].sort_values(["date", "minute_index"])
        _cache[f] = dict(
            c=m.pivot_table(index="date", columns="minute_index", values="close"),
            v=m.pivot_table(index="date", columns="minute_index", values="vwap_rth"),
            lm=m.pivot_table(index="date", columns="minute_index", values="lod_minute_sofar"),
            hm=m.pivot_table(index="date", columns="minute_index", values="hod_minute_sofar"))
    return _cache[f]


def trades(f: str, T: int, side: int) -> pd.Series:
    P = pivots(f)
    c, v = P["c"], P["v"]
    if side == 1:
        fires = (P["lm"][T] < TEN_AM) & (c[T] > v[T])
    else:
        fires = (P["hm"][T] < TEN_AM) & (c[T] < v[T])
    out = {}
    for dt in fires[fires].index:
        cc, vv = c.loc[dt], v.loc[dt]
        entry = float(cc[T]); exit_px = None
        for t in range(T + 1, FLAT_T + 1):
            if (cc[t] < vv[t]) if side == 1 else (cc[t] > vv[t]):
                exit_px = float(cc[t]); break
        if exit_px is None:
            exit_px = float(cc[FLAT_T])
        out[dt] = (((exit_px - TICK * side) / (entry + TICK * side)) - 1) * side * 1e4
    return pd.Series(out, dtype=float)


def score(files, T, side, label):
    per_year = {Path(f).stem[-4:] if "TH" not in f else "25+": trades(f, T, side) for f in files}
    bps = pd.concat(per_year.values())
    yr_sum = {y: s.sum() for y, s in per_year.items() if len(s)}
    return dict(config=label, n=len(bps), n_per_yr=round(len(bps) / len(files), 0),
                med_bps=round(bps.median(), 1), mean_bps=round(bps.mean(), 1),
                win_pct=round((bps > 0).mean() * 100, 1),
                pos_years=f"{sum(v>0 for v in yr_sum.values())}/{len(yr_sum)}",
                yearly=" ".join(f"{y}:{v/100:+.1f}" for y, v in yr_sum.items()) + " (%/yr @1x)")


def run():
    from tabulate import tabulate as tb
    rows = []
    for lab, T in CHECKS.items():
        rows.append(score(DEV, T, 1, f"LONG @{lab}"))
    for lab, T in CHECKS.items():
        rows.append(score(DEV, T, -1, f"SHORT @{lab}"))
    dev = pd.DataFrame(rows)
    TBL.mkdir(parents=True, exist_ok=True)
    dev.to_csv(TBL / "LADDER_dev.csv", index=False)
    print("=== DEV 2018-2021, QQQ (selection set) ===")
    print(tb(dev, headers="keys", showindex=False))
    return dev


if __name__ == "__main__":
    run()
