"""
or30_recheck.py — Can the refuted OR30 break system be salvaged with recent findings? QQQ.

The frozen OR30 (break by 10:30 -> 25% pullback limit -> stop far side -> EXIT 10:59) failed OOS.
Recent findings suggest three fixes, all pre-registered here:
  (a) LONGS ONLY            — shorts fail in every study
  (b) MODERN EXIT           — the dominant leg runs to ~14:30; replace the 10:59 exit with the
                              validated engine: stop = 1-min close < session VWAP, else flat 15:57
  (c) STRUCTURAL FILTER     — only take the long if the early-low-hold condition is also true
                              (day's low set before 10:00 and still holding at the break)

Variants (DEV 2018-21 -> frozen -> VAL 2022-26), scored in net bps/trade and compared to the
already-validated early-low-hold playbook (ELH) run on the same days:
  V0 frozen-long   long OR30, 25% pullback entry, stop far side, exit 10:59
  V1 modern-exit   V0 entry, but VWAP-stop + flat 15:57
  V2 +structural   V1 with the early-low-hold gate
  ELH_ref          the early-low-hold long @11:00 (both filters) — the incumbent

Question answered: does OR30 add anything the early-low-hold doesn't already capture, or is it
the same edge with a noisier entry?  Output -> tables/ORR_dev.csv / ORR_val.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from oos_playbooks import load_file
from premarket import premarket_daily
from check_ladder import trades as elh_trades

TBL = Path(__file__).resolve().parent / "output" / "tables"
TICK = 0.01
OR_W, BREAK_BY, RUNG = 30, 60, 0.25
FROZEN_EXIT, FLAT_T = 89, 387
DEV = [f"../qqq_full/QQQ_1min_{y}.csv" for y in (2018, 2019, 2020, 2021)]
VAL = [f"../qqq_full/QQQ_1min_{y}.csv" for y in (2022, 2023, 2024, 2025, 2026)]


def or30_long_variants(f: str) -> pd.DataFrame:
    minute, daily = load_file(Path(f))
    m = minute[minute.is_clean]
    ok = m.groupby("date")["minute_index"].size() == 390
    m = m[m.date.isin(ok[ok].index)].sort_values(["date", "minute_index"])
    g = {dt: d.reset_index(drop=True) for dt, d in m.groupby("date")}
    rows = []
    for dt, day in g.items():
        hi = day.high.values; lo = day.low.values; cl = day.close.values
        vw = day.vwap_rth.values
        orh = hi[:OR_W].max(); orl = lo[:OR_W].min(); orr = orh - orl
        if orr <= 0:
            continue
        # first close above OR high by 10:30 = long break
        brk = None
        for t in range(OR_W, BREAK_BY + 1):
            if cl[t] > orh:
                brk = t; break
        if brk is None:
            continue
        limit = orh - RUNG * orr
        fill = None
        for t in range(brk + 1, BREAK_BY + 1):        # pullback fill by 10:30
            if lo[t] <= limit:
                fill = t; break
        if fill is None:
            continue
        # structural gate: low set before 10:00 (min 30) and still the low at the fill
        low_min = int(np.argmin(lo[:fill + 1]))
        structural = low_min < 30
        # V0 frozen: stop far side (orl), exit 10:59
        def run_exit(stop_mode):
            for t in range(fill + 1, (FROZEN_EXIT if stop_mode == "frozen" else FLAT_T) + 1):
                if stop_mode == "frozen" and lo[t] <= orl:
                    return orl, "stop"
                if stop_mode == "vwap" and cl[t] < vw[t]:
                    return cl[t], "stop"
            end = FROZEN_EXIT if stop_mode == "frozen" else FLAT_T
            return cl[end], "time"
        px0, _ = run_exit("frozen"); px1, _ = run_exit("vwap")
        bps = lambda px: ((px - TICK) / (limit + TICK) - 1) * 1e4
        rows.append(dict(date=dt, year=Path(f).stem[-4:], structural=structural,
                         v0=bps(px0), v1=bps(px1)))
    return pd.DataFrame(rows)


def score(files, label):
    dfs = [or30_long_variants(f) for f in files]
    T = pd.concat(dfs, ignore_index=True)
    # ELH incumbent on the same files
    elh = pd.concat([elh_trades(f, 90, 1).rename("bps").to_frame().assign(year=Path(f).stem[-4:])
                     for f in files]).reset_index()
    rows = []
    def yrs_pos(series_by):
        return f"{sum(v>0 for v in series_by.values())}/{len(series_by)}"
    for nm, sub, col in (("V0 frozen-long", T, "v0"), ("V1 modern-exit", T, "v1"),
                         ("V2 +structural", T[T.structural], "v1")):
        by = {y: sub[sub.year == y][col].mean() for y in sorted(sub.year.unique())
              if len(sub[sub.year == y]) >= 6}
        rows.append(dict(variant=nm, n=len(sub), mean_bps=round(sub[col].mean(), 1),
                         win_pct=round((sub[col] > 0).mean() * 100, 1), pos_years=yrs_pos(by)))
    by = {y: elh[elh.year == y].bps.mean() for y in sorted(elh.year.unique()) if len(elh[elh.year == y]) >= 6}
    rows.append(dict(variant="ELH_ref (incumbent)", n=len(elh), mean_bps=round(elh.bps.mean(), 1),
                     win_pct=round((elh.bps > 0).mean() * 100, 1), pos_years=yrs_pos(by)))
    out = pd.DataFrame(rows)
    from tabulate import tabulate as tb
    print(f"\n=== {label} ===")
    print(tb(out, headers="keys", showindex=False))
    return out


if __name__ == "__main__":
    TBL.mkdir(parents=True, exist_ok=True)
    score(DEV, "DEV 2018-2021").to_csv(TBL / "ORR_dev.csv", index=False)
    score(VAL, "VAL 2022-2026").to_csv(TBL / "ORR_val.csv", index=False)
