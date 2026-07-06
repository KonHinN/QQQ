"""
premarket.py — Analysis V: premarket (04:00-09:29 ET) features, causal at the open.

The raw CSV carries extended hours that every prior analysis dropped. Features per day t0
(all known by 09:30):
  pm_low / pm_high / pm_range_pct     premarket extremes
  open_pos_pm                          where the RTH open sits in the premarket range
                                       (0 = opening ON the premarket low, 1 = on the high)
  pm_ret_pct                           premarket drift: last premarket price vs yesterday's RTH close
  pm_vol_ratio                         premarket volume vs trailing 20-day median (causal)
  open_above_pm_low                    RTH open >= 0.3% off the premarket low ("already bounced")

V1. All days: quintiles of each feature -> P(runner day)  [same framework as the S2 gap ladder]
V2. Event days (gap <= -0.35x prior range): PLAYBOOK trade outcome (buy 10:00, stop -1%,
    sell 13:30, 1 tick/side) split by premarket state -> does premarket refine the playbook?

Methodology as always: n everywhere, H1/H2 same-sign, base rates shown. In-sample year.
"""
from __future__ import annotations
from pathlib import Path
import datetime as dt
import numpy as np
import pandas as pd

from ingest import load_raw
from runners import build_frame, TAB_DIR, OUT_DIR

TICK = 0.01
EVENT_THR = -0.35
ENTRY_T, EXIT_T, STOP = 30, 240, 1.0
PM_START, PM_END = dt.time(4, 0), dt.time(9, 29)


def premarket_daily(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    if raw is None:
        raw = load_raw()
    pm = raw[(raw["time"] >= PM_START) & (raw["time"] <= PM_END)]
    g = pm.groupby("date")
    out = pd.DataFrame({
        "pm_low": g["low"].min(), "pm_high": g["high"].max(),
        "pm_vol": g["volume"].sum(), "pm_last": g["close"].last(),
        "pm_bars": g.size()})
    return out.reset_index()


def playbook_bps(m: pd.DataFrame, dates: pd.Index) -> pd.Series:
    pc = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
    pl = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="low")
    dates = [d for d in dates if d in pc.index]
    entry = pc.loc[dates, ENTRY_T]
    mae = (entry - pl.loc[dates, ENTRY_T:EXIT_T].min(axis=1)) / entry * 100
    stopped = mae >= STOP
    px = np.where(stopped, entry * (1 - STOP / 100), pc.loc[dates, EXIT_T])
    return ((pd.Series(px, index=entry.index) - TICK) / (entry + TICK) - 1) * 1e4


def run():
    m = pd.read_parquet(OUT_DIR / "minute.parquet")
    daily = pd.read_parquet(OUT_DIR / "daily.parquet")
    d = build_frame(daily, m)
    d["event"] = d.gap_over_prange <= EVENT_THR

    pmd = premarket_daily()
    d = d.merge(pmd, on="date", how="left")
    d = d[d.pm_bars >= 60]                                   # need a real premarket session
    d["pm_range_pct"] = (d.pm_high - d.pm_low) / d.pdc * 100
    rng = (d.pm_high - d.pm_low).replace(0, np.nan)
    d["open_pos_pm"] = (d.rth_open - d.pm_low) / rng
    d["pm_ret_pct"] = (d.pm_last / d.pdc - 1) * 100
    d["pm_vol_ratio"] = d.pm_vol / d.pm_vol.rolling(20, min_periods=10).median().shift(1)
    d["open_above_pm_low"] = (d.rth_open / d.pm_low - 1) * 100 >= 0.30

    # ---------------- V1: all-days quintile ladders vs Y_up_trail
    rows = []
    sub = d.dropna(subset=["thr_up_run"])
    for col in ("open_pos_pm", "pm_ret_pct", "pm_range_pct", "pm_vol_ratio"):
        s = sub.dropna(subset=[col]).copy()
        s["q"] = pd.qcut(s[col], 5, labels=False, duplicates="drop")
        base = s.Y_up_trail.mean() * 100
        for q, g in s.groupby("q"):
            h1 = g[g.half == "H1"]; h2 = g[g.half == "H2"]
            rows.append(dict(feature=col, quintile=int(q) + 1, n=len(g),
                             med_val=round(g[col].median(), 3),
                             runner_pct=round(g.Y_up_trail.mean() * 100, 1),
                             base_pct=round(base, 1),
                             H1_pct=round(h1.Y_up_trail.mean() * 100, 1) if len(h1) >= 5 else np.nan,
                             H2_pct=round(h2.Y_up_trail.mean() * 100, 1) if len(h2) >= 5 else np.nan))
    v1 = pd.DataFrame(rows)

    # ---------------- V2: event-day playbook refinement
    ev = d[d.event].set_index("date")
    bps = playbook_bps(m, ev.index)
    ev = ev.loc[bps.index]
    splits = {
        "open_on_pm_low (pos<=0.25)": ev.open_pos_pm <= 0.25,
        "open_mid_pm (0.25-0.6)": (ev.open_pos_pm > 0.25) & (ev.open_pos_pm <= 0.6),
        "open_high_pm (pos>0.6)": ev.open_pos_pm > 0.6,
        "already_bounced_0.3pct": ev.open_above_pm_low,
        "NOT_bounced": ~ev.open_above_pm_low,
        "pm_vol_high (ratio>1.5)": ev.pm_vol_ratio > 1.5,
        "pm_vol_normal": ev.pm_vol_ratio <= 1.5,
    }
    rows = []
    base_med = bps.median(); base_hit = (bps > 0).mean() * 100
    for lab, mask in splits.items():
        mask = mask.fillna(False)
        b = bps[mask]
        if len(b) < 5:
            rows.append(dict(split=lab, n=len(b), med_bps=np.nan, mean_bps=np.nan,
                             hit_pct=np.nan, base_med=round(base_med, 1)))
            continue
        rows.append(dict(split=lab, n=len(b), med_bps=round(b.median(), 1),
                         mean_bps=round(b.mean(), 1), hit_pct=round((b > 0).mean() * 100, 1),
                         base_med=round(base_med, 1)))
    v2 = pd.DataFrame(rows)

    # continuous check: rank-corr of open_pos_pm / pm_vol_ratio vs playbook bps on event days
    from scipy.stats import spearmanr
    corr_rows = []
    for col in ("open_pos_pm", "pm_ret_pct", "pm_vol_ratio", "pm_range_pct"):
        ok = ev[col].notna()
        r, p = spearmanr(ev.loc[ok, col], bps[ok])
        corr_rows.append(dict(feature=col, spearman_r=round(r, 3), p=round(p, 4), n=int(ok.sum())))
    v3 = pd.DataFrame(corr_rows)

    v1.to_csv(TAB_DIR / "V_pm_ladders.csv", index=False)
    v2.to_csv(TAB_DIR / "V_pm_event_splits.csv", index=False)
    v3.to_csv(TAB_DIR / "V_pm_event_corr.csv", index=False)
    return {"V1": v1, "V2": v2, "V3": v3}


if __name__ == "__main__":
    r = run()
    from tabulate import tabulate as tb
    print("=== V1 all-days premarket ladders vs P(runner) ===")
    print(tb(r["V1"], headers="keys", showindex=False))
    print("\n=== V2 event-day playbook splits (buy 10:00 / stop 1% / sell 13:30, net bps) ===")
    print(tb(r["V2"], headers="keys", showindex=False))
    print("\n=== V3 event-day continuous correlations vs playbook bps ===")
    print(tb(r["V3"], headers="keys", showindex=False))
