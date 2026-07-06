"""
noon_check.py — Reproduce the desk-branch "noon-check" long (HANDOFF_RESEARCH.md §8) on QQQ.

Rule (Trade 2, from the desk/implementation branch, verbatim from §8):
  At 12:00 ET: today's LOW was set BEFORE 10:00 AND is still the low AND price > session VWAP
    -> BUY at market (12:00 close), target = standing HOD, stop = trailing session VWAP,
       flat 15:57.

This branch previously reproduced: FIRES 87/247 days (7.2/mo), 41% trend-up vs 17% base.
This script re-derives that firing rate + trend-up split from the shipped minute/daily parquets,
then measures the trade economics (net of 1 tick/side) as a cross-check. IN-SAMPLE — a lift on
the trend-day LABEL, not a proven edge (same caveats as every §2/§9 number).

    python noon_check.py
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

from runners import build_frame

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TICK = 0.01
CHECK_T = 150        # 12:00 ET  (09:30 = minute_index 0)
TEN_AM = 30          # 10:00 ET  ("before 10:00" => lod set at minute_index < 30)
FLAT_T = 387         # 15:57 ET


def run(write: bool = True):
    m = pd.read_parquet(OUT / "minute.parquet")
    daily = pd.read_parquet(OUT / "daily.parquet")
    d = build_frame(daily, m)                       # clean days only; gives Y_trend_up + half
    clean_dates = set(d.date)

    m = m[m.is_clean & m.date.isin(clean_dates)].sort_values(["date", "minute_index"])
    piv_c = m.pivot_table(index="date", columns="minute_index", values="close")
    piv_h = m.pivot_table(index="date", columns="minute_index", values="high")
    piv_v = m.pivot_table(index="date", columns="minute_index", values="vwap_rth")
    piv_lodmin = m.pivot_table(index="date", columns="minute_index", values="lod_minute_sofar")
    run_hod = m.pivot_table(index="date", columns="minute_index", values="run_hod")

    dates = [dt for dt in piv_c.index if CHECK_T in piv_c.columns]
    # ---- firing condition at 12:00
    low_set_pre10 = piv_lodmin.loc[dates, CHECK_T] < TEN_AM      # LOD set before 10:00 & still LOD
    above_vwap = piv_c.loc[dates, CHECK_T] > piv_v.loc[dates, CHECK_T]
    fires = (low_set_pre10 & above_vwap).reindex(dates).fillna(False)
    fire_dates = [dt for dt in dates if bool(fires.loc[dt])]

    n_days = len(dates)
    n_fire = len(fire_dates)
    dd = d.set_index("date")
    trend_base = dd.Y_trend_up.mean() * 100
    trend_fire = dd.loc[fire_dates, "Y_trend_up"].mean() * 100

    # ---- trade economics: buy 12:00 close, target = standing HOD, stop = trailing VWAP, flat 15:57
    rows = []
    for dt in fire_dates:
        entry = float(piv_c.loc[dt, CHECK_T])
        target = float(run_hod.loc[dt, CHECK_T])                # standing HOD at entry
        c = piv_c.loc[dt]; h = piv_h.loc[dt]; v = piv_v.loc[dt]
        exit_px, reason = None, None
        for t in range(CHECK_T + 1, FLAT_T + 1):
            hit_target = h.get(t, np.nan) >= target
            below_vwap = c.get(t, np.nan) < v.get(t, np.nan)    # trailing session VWAP stop
            if hit_target and below_vwap:                       # same-bar: pessimistic -> stop
                exit_px, reason = float(v.get(t)), "stop"; break
            if below_vwap:
                exit_px, reason = float(v.get(t)), "stop"; break
            if hit_target:
                exit_px, reason = target, "target"; break
        if exit_px is None:
            exit_px, reason = float(c.get(FLAT_T, c.dropna().iloc[-1])), "flat"
        net_bps = ((exit_px - TICK) / (entry + TICK) - 1) * 1e4
        rows.append(dict(date=dt, half=dd.loc[dt, "half"], entry=round(entry, 2),
                         target=round(target, 2), exit=round(exit_px, 2), reason=reason,
                         net_bps=round(net_bps, 1), trend_up=bool(dd.loc[dt, "Y_trend_up"])))
    tr = pd.DataFrame(rows)
    h1 = tr[tr.half == "H1"].net_bps; h2 = tr[tr.half == "H2"].net_bps

    summary = pd.DataFrame([dict(
        n_days=n_days, n_fires=n_fire, fires_per_month=round(n_fire / n_days * 21, 1),
        trend_up_fire_pct=round(trend_fire, 1), trend_up_base_pct=round(trend_base, 1),
        med_bps=round(tr.net_bps.median(), 1), mean_bps=round(tr.net_bps.mean(), 1),
        hit_pct=round((tr.net_bps > 0).mean() * 100, 1),
        med_H1=round(h1.median(), 1), med_H2=round(h2.median(), 1),
        same_sign=bool(np.sign(h1.median()) == np.sign(h2.median())),
        target_hit_pct=round((tr.reason == "target").mean() * 100, 1),
        stop_pct=round((tr.reason == "stop").mean() * 100, 1))])

    if write:
        TBL.mkdir(parents=True, exist_ok=True)
        tr.to_csv(TBL / "X_noon_check_trades.csv", index=False)
        summary.to_csv(TBL / "X_noon_check_summary.csv", index=False)
    return summary, tr


if __name__ == "__main__":
    from tabulate import tabulate as tb
    summary, tr = run()
    print("=== Noon-check (desk-branch Trade 2) — QQQ 2025-26, in-sample ===")
    print(tb(summary.T.reset_index().rename(columns={"index": "metric", 0: "value"}),
             headers="keys", showindex=False))
    print(f"\nFiring anchor (§8): expected 87/247 fires, 41% trend-up vs 17% base.")
    print("\n=== trade ledger tail ===")
    print(tb(tr.tail(8), headers="keys", showindex=False))
