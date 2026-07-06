"""
oos_playbooks.py — OOS validation of the two playbooks on 2018-2024 QQQ/SPY/IWM (frozen specs).

    python oos_playbooks.py <data_dir>

Per symbol-year CSV (Phase-1 format, extended hours, unadjusted):
  P1  OR30 break->pullback system (analysis R, system_backtest.py, spec UNCHANGED):
      first close beyond OR30 by 10:30 -> limit @25% OR retrace -> cancel 10:30 ->
      stop far side -> exit 10:59; shorts gated by trailing 66.7pctl drive (30-day warm-up,
      which RESETS each year file — shorts trade only from ~mid-Feb of each year).
      $10k, 1% fixed-fractional risk, 4x cap, 1 tick/side.
  P2  Noon-check long (desk branch, HANDOFF_RESEARCH.md §8, spec UNCHANGED):
      12:00 ET: LOD set before 10:00 AND still LOD AND close > session VWAP -> buy 12:00 close,
      target = standing HOD, stop = trailing session VWAP (close < vwap), flat 15:57;
      same-bar target+stop resolved pessimistically (stop). Net of 1 tick/side.

In-sample anchors (QQQ 2025-26): P1 +11.0%/yr, DD -3.8%, 62% win, avg_R 0.19, 61 trades;
P2 fires 87/247 (35%), trend-up 41% vs 17% base, med +5.1 bps, 75% hit.

Day hygiene: RTH bar count != 390 or file-boundary day -> excluded (same as oos_validate.py).
Outputs -> tables/OOSPB_or30.csv, tables/OOSPB_noon.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from runners import build_frame
from system_backtest import build_trades, simulate, stats

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TICK = 0.01
CHECK_T, TEN_AM, FLAT_T = 150, 30, 387


# ---------------------------------------------------------------- ingest one file
def load_file(csv_path: Path):
    raw = ingest.load_raw(csv_path)
    rth = ingest.filter_rth(raw)
    counts = rth.groupby("date").size()
    dates = sorted(counts.index)
    bad = set(counts[counts != ingest.N_MIN].index) | {dates[0], dates[-1]}
    flags = pd.DataFrame({"date": dates})
    flags["day_flag"] = np.where(flags.date.isin(bad), "excluded_auto", "full")
    flags["is_clean"] = ~flags.date.isin(bad)
    rth = rth.merge(flags, on="date", how="left")
    daily = ingest.derive_daily(rth).merge(flags, on="date", how="left")
    minute = ingest.derive_minute(rth, daily[["date", "pdh", "pdl", "pdc", "prior_is_full"]])
    return minute, daily


# ---------------------------------------------------------------- P1 OR30
def run_or30(minute, daily, label):
    trades = build_trades(minute)
    if not len(trades):
        return dict(config=label, n_trades=0)
    led = simulate(trades, 0.01)
    st = stats(led, label, n_days=int(daily.is_clean.sum()))
    dd = daily[daily.is_clean].sort_values("date")
    st["bh_ret_pct"] = round((dd.rth_close.iloc[-1] / dd.rth_close.iloc[0] - 1) * 100, 1)
    st["n_days"] = int(daily.is_clean.sum())
    return st


# ---------------------------------------------------------------- P2 noon-check
def run_noon(minute, daily, label):
    d = build_frame(daily, minute)
    dd = d.set_index("date")
    m = minute[minute.is_clean & minute.date.isin(set(d.date))].sort_values(["date", "minute_index"])
    piv_c = m.pivot_table(index="date", columns="minute_index", values="close")
    piv_h = m.pivot_table(index="date", columns="minute_index", values="high")
    piv_v = m.pivot_table(index="date", columns="minute_index", values="vwap_rth")
    piv_lm = m.pivot_table(index="date", columns="minute_index", values="lod_minute_sofar")
    piv_rh = m.pivot_table(index="date", columns="minute_index", values="run_hod")

    fires = (piv_lm[CHECK_T] < TEN_AM) & (piv_c[CHECK_T] > piv_v[CHECK_T])
    fire_dates = list(fires[fires].index)
    n_days = len(piv_c)

    rows = []
    for dt in fire_dates:
        entry = float(piv_c.loc[dt, CHECK_T])
        target = float(piv_rh.loc[dt, CHECK_T])
        c, h, v = piv_c.loc[dt], piv_h.loc[dt], piv_v.loc[dt]
        exit_px, reason = None, None
        for t in range(CHECK_T + 1, FLAT_T + 1):
            below = c[t] < v[t]
            if below:                               # same-bar target+stop -> pessimistic stop
                exit_px, reason = float(v[t]), "stop"; break
            if h[t] >= target:
                exit_px, reason = target, "target"; break
        if exit_px is None:
            exit_px, reason = float(c[FLAT_T]), "flat"
        rows.append(dict(date=dt, half=dd.loc[dt, "half"],
                         net_bps=((exit_px - TICK) / (entry + TICK) - 1) * 1e4,
                         reason=reason, trend_up=bool(dd.loc[dt, "Y_trend_up"])))
    tr = pd.DataFrame(rows)
    if not len(tr):
        return dict(config=label, n_days=n_days, n_fires=0)
    h1 = tr[tr.half == "H1"].net_bps; h2 = tr[tr.half == "H2"].net_bps
    return dict(config=label, n_days=n_days, n_fires=len(tr),
                fire_rate_pct=round(len(tr) / n_days * 100, 1),
                trend_up_fire_pct=round(tr.trend_up.mean() * 100, 1),
                trend_up_base_pct=round(dd.Y_trend_up.mean() * 100, 1),
                med_bps=round(tr.net_bps.median(), 1),
                mean_bps=round(tr.net_bps.mean(), 1),
                hit_pct=round((tr.net_bps > 0).mean() * 100, 1),
                med_H1=round(h1.median(), 1) if len(h1) >= 5 else np.nan,
                med_H2=round(h2.median(), 1) if len(h2) >= 5 else np.nan,
                target_pct=round((tr.reason == "target").mean() * 100, 1),
                stop_pct=round((tr.reason == "stop").mean() * 100, 1))


# ---------------------------------------------------------------- run all
def run(data_dir: Path):
    or_rows, noon_rows = [], []
    for p in sorted(data_dir.glob("*.csv")):
        label = p.stem.replace("_1min", "")
        minute, daily = load_file(p)
        print(f"[{label}] {int(daily.is_clean.sum())} clean days")
        or_rows.append(run_or30(minute, daily, label))
        noon_rows.append(run_noon(minute, daily, label))
    or_tab = pd.DataFrame(or_rows)
    noon_tab = pd.DataFrame(noon_rows)
    TBL.mkdir(parents=True, exist_ok=True)
    or_tab.to_csv(TBL / "OOSPB_or30.csv", index=False)
    noon_tab.to_csv(TBL / "OOSPB_noon.csv", index=False)
    from tabulate import tabulate as tb
    print("\n=== P1 OR30 system, $10k @1% risk (frozen spec) ===")
    print(tb(or_tab, headers="keys", showindex=False))
    print("\n=== P2 noon-check (frozen spec) ===")
    print(tb(noon_tab, headers="keys", showindex=False))
    return or_tab, noon_tab


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run(Path(sys.argv[1] if len(sys.argv) > 1 else "../oos_data"))
