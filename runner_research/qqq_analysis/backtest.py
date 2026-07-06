"""
backtest.py — Analysis K: does the structural clock survive trading costs?

Tests the core playbook (opening-drive continuation into the 10:00-11:00 turn window) as
simple TIME-BASED rules with zero parameters fitted to outcomes — entries/exits at fixed
clock times, direction known at entry (no look-ahead).

Strategies (per day, one trade, close-to-close on 1-min bars):
  S1  drive15 : dir = sign(09:45 close - open); enter 09:45, exit 11:00
  S2  drive30 : dir = sign(10:00 close - open); enter 10:00, exit 11:00
  S3  drive30_early_exit : same entry, exit 10:30
  S4  fade_at_11 : at 11:00 enter OPPOSITE the morning direction, exit at close
      (J4 predicts ~zero — included as an honest control)
  S5  hold_open_to_close : baseline drift

Filters: all days vs |drive| top-tercile days (magnitude known at entry).
Costs: QQQ is penny-spread; assume ROUND-TRIP cost = 2 ticks ($0.02) ≈ 0.4 bps + report gross too.
Metrics: n, hit rate, mean/median bps, t-stat, total %, H1/H2 split.
Outputs -> output/tables/K_backtest.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, N_MIN

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
COST_BPS = 0.4          # round-trip: 2 ticks on ~$550 underlying


def _frames():
    m, d = load()
    piv = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
           .reindex(columns=np.arange(N_MIN)).dropna())
    op = m[m.is_clean].groupby("date")["open"].first().reindex(piv.index)
    return piv, op


def _stats(pnl_bps: pd.Series, label: str, subset: str):
    n = len(pnl_bps)
    if n < 10:
        return None
    mean, med, sd = pnl_bps.mean(), pnl_bps.median(), pnl_bps.std()
    t = mean / (sd / np.sqrt(n)) if sd > 0 else np.nan
    half = n // 2
    return {"strategy": label, "subset": subset, "n_trades": n,
            "hit_rate_pct": round((pnl_bps > 0).mean() * 100, 1),
            "mean_bps": round(mean, 2), "median_bps": round(med, 2),
            "sd_bps": round(sd, 1), "t_stat": round(t, 2),
            "total_pct": round(pnl_bps.sum() / 1e4 * 100, 2),
            "mean_H1": round(pnl_bps.iloc[:half].mean(), 2),
            "mean_H2": round(pnl_bps.iloc[half:].mean(), 2)}


def run(write=True):
    piv, op = _frames()
    drive15 = piv[14] / op - 1
    drive30 = piv[29] / op - 1

    legs = {
        "S1_drive15_0945_to_1100": (np.sign(drive15), piv[89] / piv[14] - 1, drive15),
        "S2_drive30_1000_to_1100": (np.sign(drive30), piv[89] / piv[29] - 1, drive30),
        "S3_drive30_1000_to_1030": (np.sign(drive30), piv[59] / piv[29] - 1, drive30),
        "S4_fade_1100_to_close": (-np.sign(piv[89] / op - 1), piv[389] / piv[89] - 1,
                                  piv[89] / op - 1),
        "S5_hold_open_to_close": (pd.Series(1.0, index=piv.index), piv[389] / op - 1, drive30),
    }
    rows = []
    for name, (dirn, fwd, drive) in legs.items():
        gross = dirn * fwd * 1e4
        net = gross - COST_BPS
        rows.append(_stats(net, name, "all days (net)"))
        rows.append(_stats(gross, name, "all days (gross)"))
        big = drive.abs() > drive.abs().quantile(2 / 3)
        rows.append(_stats(net[big], name, "big-drive tercile (net)"))
    tab = pd.DataFrame([r for r in rows if r])
    if write:
        tab.to_csv(TBL / "K_backtest.csv", index=False)
        print("[backtest] wrote K_backtest.csv")
    return tab


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    t = run()
    print(t.to_string(index=False))
