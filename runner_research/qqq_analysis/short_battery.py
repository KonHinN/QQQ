"""
short_battery.py — Is there ANY legit intraday short setup on QQQ? DEV 2018-21 -> VAL 2022-24.

Already refuted elsewhere (not retested): early-HOD-hold mirror at any check time 10:30-13:00
(check_ladder.py, negative every rung); OR30 shorts (system refuted wholesale); time-of-day
drift shorts (0/26 buckets).

This battery (all causal, mirrors of the frozen long specs, 1 tick/side):
  S2 gap-up fade      gap/prior-range >= +0.35 -> SELL 10:00 close, stop +1.0% (intrabar high,
                      pessimistic), cover 13:30 close.   [mirror of the gap-down bounce playbook;
                      motivated by in-sample 'gap-up momentum inverted']
  S5 failed bounce    gap/prior-range <= -0.35 AND open < 0.3% above premarket low ('NOT bounced')
                      -> SELL 10:00 close, stop +1.0%, cover 13:30.  [the excluded half of the
                      gap playbook, which was mildly negative for longs in-sample]
  S3 up3 exhaustion   3 consecutive up closes -> SELL next open, cover at close (no stop; the
                      contraction lead — expect vol shrink, testing if there's any downside drift)
Context row: the structural headwind — mean QQQ open->close drift per year.

    python short_battery.py
Outputs -> tables/SHORT_dev.csv (+ printed VAL only if something survives DEV)
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from oos_playbooks import load_file
from premarket import premarket_daily

TBL = Path(__file__).resolve().parent / "output" / "tables"
TICK = 0.01
ENTRY_T, COVER_T, STOP_PCT = 30, 240, 1.0
DEV = [f"../oos_data/QQQ_1min_{y}.csv" for y in (2018, 2019, 2020, 2021)]
VAL = [f"../oos_data/QQQ_1min_{y}.csv" for y in (2022, 2023, 2024)]

_cache = {}


def prep(f):
    if f not in _cache:
        raw = ingest.load_raw(Path(f))
        minute, daily = load_file(Path(f))
        m = minute[minute.is_clean]
        ok = m.groupby("date")["minute_index"].size() == 390
        m = m[m.date.isin(ok[ok].index)]
        d = daily[daily.is_clean].sort_values("date").reset_index(drop=True)
        d["gop"] = d.gap / d.day_range.shift(1)
        d = d.merge(premarket_daily(raw), on="date", how="left")
        d["pm_bounced"] = (d.rth_open / d.pm_low - 1) * 100 >= 0.30
        d["ret_cc"] = d.rth_close.pct_change()
        up = (d.ret_cc > 0)
        d["up3"] = (up.shift(1) & up.shift(2) & up.shift(3)).fillna(False)
        _cache[f] = dict(
            pc=m.pivot_table(index="date", columns="minute_index", values="close"),
            ph=m.pivot_table(index="date", columns="minute_index", values="high"),
            po=m.pivot_table(index="date", columns="minute_index", values="open"),
            d=d.set_index("date"))
    return _cache[f]


def short_1000_1330(P, dates) -> pd.Series:
    out = {}
    for dt in dates:
        if dt not in P["pc"].index:
            continue
        entry = float(P["pc"].loc[dt, ENTRY_T])
        stop_px = entry * (1 + STOP_PCT / 100)
        highs = P["ph"].loc[dt, ENTRY_T:COVER_T]
        exit_px = stop_px if (highs >= stop_px).any() else float(P["pc"].loc[dt, COVER_T])
        out[dt] = ((entry - TICK) / (exit_px + TICK) - 1) * 1e4
    return pd.Series(out, dtype=float)


def setups(P):
    d = P["d"]
    return {
        "S2_gapup_fade": short_1000_1330(P, d[d.gop >= 0.35].index),
        "S5_failed_bounce": short_1000_1330(P, d[(d.gop <= -0.35) & (~d.pm_bounced.fillna(False))].index),
        "S3_up3_short_oc": pd.Series({dt: ((r.rth_open - TICK) / (r.rth_close + TICK) - 1) * 1e4
                                      for dt, r in d[d.up3].iterrows()}, dtype=float),
        "CTX_oc_drift_all": pd.Series({dt: (r.rth_close / r.rth_open - 1) * 1e4
                                       for dt, r in d.iterrows()}, dtype=float),
    }


def score(files, name) -> dict:
    per = {f[-8:-4]: setups(prep(f))[name] for f in files}
    bps = pd.concat(per.values())
    yr = {y: s.sum() for y, s in per.items() if len(s)}
    return dict(setup=name, n=len(bps), n_yr=round(len(bps) / len(files), 0),
                med_bps=round(bps.median(), 1), mean_bps=round(bps.mean(), 1),
                win_pct=round((bps > 0).mean() * 100, 1),
                pos_years=f"{sum(v>0 for v in yr.values())}/{len(yr)}",
                yearly=" ".join(f"{y}:{v/100:+.1f}" for y, v in sorted(yr.items())))


def run():
    from tabulate import tabulate as tb
    names = ["S2_gapup_fade", "S5_failed_bounce", "S3_up3_short_oc", "CTX_oc_drift_all"]
    dev = pd.DataFrame([score(DEV, n) for n in names])
    TBL.mkdir(parents=True, exist_ok=True)
    dev.to_csv(TBL / "SHORT_dev.csv", index=False)
    print("=== DEV 2018-2021, QQQ (shorts in bps for the setups; CTX row = market's own o->c drift) ===")
    print(tb(dev, headers="keys", showindex=False))
    return dev


if __name__ == "__main__":
    run()
