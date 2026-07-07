"""
upgrade_lab.py — Upgrade the early-low-hold playbook across 6 aspects, QQQ. DEV->VAL discipline.

Baseline = the FINAL playbook: fire at 11:00 (low<10:00 holds, >VWAP, session low>PM low; skip
big-body-yesterday & FOMC); enter 11:00 close; stop = 1-min close < VWAP; flat 15:57; 1 tick/side.

Each upgrade is a pre-registered variant, tuned ONLY on DEV 2018-21, then a single VAL 2022-26
look. Same firing days throughout (we change how we manage the trade, not which days).

  ENTRY     E1 pullback-to-VWAP (buy first VWAP touch in 11:00-11:30 else 11:00 close)
  EXIT      X1 flat 14:30   X2 flat 15:00   (leg tops ~14:30 finding) vs baseline 15:57
  TRAIL     T1 breakeven after +DEV-median-MFE   T2 chandelier (high - k*ATR, k from DEV)
  GIVEBACK  G1 exit on giving back 33% of peak profit   G2 giveback 50%   (the "P20"-style lock)
  PROFIT    P1 fixed target at DEV-P80 of MFE (expected to hurt, tested for completeness)
  PM-HINT   H1 size 1.5x when gap>0 & PM-strength (both), 1x else (report size-weighted mean)

Scored in net bps/trade, win%, pos-years. A variant is adopted only if it beats baseline on DEV
AND holds its sign/rank on VAL.  Output -> tables/UPG_dev.csv / UPG_val.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from oos_playbooks import load_file
from premarket import premarket_daily
from skip_battery import FOMC

TICK = 0.01
E = 90                 # 11:00 entry index
FLAT = 387             # 15:57
DEV = [f"../qqq_full/QQQ_1min_{y}.csv" for y in (2018, 2019, 2020, 2021)]
VAL = [f"../qqq_full/QQQ_1min_{y}.csv" for y in (2022, 2023, 2024, 2025, 2026)]
TBL = Path(__file__).resolve().parent / "output" / "tables"


def firing_paths(f: str):
    """FINAL-playbook firing days -> per-day minute arrays from entry (11:00) to close."""
    raw = ingest.load_raw(Path(f)); minute, daily = load_file(Path(f))
    m = minute[minute.is_clean]
    ok = m.groupby("date")["minute_index"].size() == 390
    m = m[m.date.isin(ok[ok].index)].sort_values(["date", "minute_index"])
    piv = {c: m.pivot_table(index="date", columns="minute_index", values=c)
           for c in ("close", "low", "high", "vwap_rth", "atr", "lod_minute_sofar")}
    pmd = premarket_daily(raw).set_index("date")
    dd = daily[daily.is_clean].sort_values("date").reset_index(drop=True)
    dd["body"] = (dd.rth_close - dd.rth_open) / dd.rth_open * 100; ab = dd.body.abs()
    bb = dict(zip(dd.date, (ab >= ab.rolling(20, min_periods=10).quantile(.8).shift(1))
                  .shift(1).fillna(False).astype(bool)))
    gapmap = dict(zip(dd.date, (dd.rth_open / dd.pdc - 1) > 0))
    out = []
    for dt in piv["close"].index:
        if dt not in pmd.index or pmd.loc[dt, "pm_bars"] < 60:
            continue
        c = piv["close"].loc[dt]; lo = piv["low"].loc[dt]; vw = piv["vwap_rth"].loc[dt]
        low_sofar = float(lo[:E].min()); pm_l = float(pmd.loc[dt, "pm_low"])
        # FINAL fire + filters
        if not (int(piv["lod_minute_sofar"].loc[dt, E]) < 30 and c[E] > vw[E]):
            continue
        if low_sofar <= pm_l or bb.get(dt, False) or dt in FOMC:
            continue
        seg = slice(E, FLAT + 1)
        out.append(dict(date=dt, year=Path(f).stem[-4:],
                        c=c[seg].to_numpy(), lo=lo[seg].to_numpy(),
                        hi=piv["high"].loc[dt][seg].to_numpy(), vw=vw[seg].to_numpy(),
                        atr=piv["atr"].loc[dt][seg].to_numpy(), gap_up=bool(gapmap.get(dt, False))))
    return out


def net(entry, exit_px, side_ticks=1):
    return ((exit_px - TICK) / (entry + TICK) - 1) * 1e4


def sim(day, mode="base", **kw):
    c, lo, hi, vw, atr = day["c"], day["lo"], day["hi"], day["vw"], day["atr"]
    n = len(c)
    # entry
    e_ix = 0
    if mode == "E1_vwap_pull":
        for t in range(0, min(30, n)):                 # first VWAP touch within 30 min of 11:00
            if lo[t] <= vw[t]:
                e_ix = t; break
    entry = c[e_ix]
    hard = {"X1_1430": 210, "X2_1500": 240}.get(mode, n - 1)   # index within seg (E=0 -> 15:57=297)
    hard = min(hard, n - 1)
    peak = entry; be_armed = False
    trig = kw.get("trig", 0.0); k = kw.get("k", 0.0); gb = kw.get("gb", 0.0); pt = kw.get("pt", 0.0)
    for t in range(e_ix + 1, hard + 1):
        peak = max(peak, c[t])
        # baseline VWAP-close stop (always active unless chandelier replaces it)
        if mode != "T2_chandelier" and c[t] < vw[t]:
            return net(entry, c[t])
        if mode == "T2_chandelier":
            stop = hi[:t + 1].max() - k * atr[t]
            if c[t] <= stop:
                return net(entry, c[t])
        if mode == "T1_breakeven":
            if hi[t] >= entry * (1 + trig):
                be_armed = True
            if be_armed and c[t] < entry:
                return net(entry, c[t])
        if mode in ("G1_giveback33", "G2_giveback50") and peak > entry:
            if c[t] <= peak - gb * (peak - entry):
                return net(entry, c[t])
        if mode == "P1_target" and hi[t] >= entry * (1 + pt):
            return net(entry, entry * (1 + pt))
    return net(entry, c[hard])


def score(days, mode, label, **kw):
    rows = [dict(year=d["year"], gap_up=d["gap_up"], bps=sim(d, mode, **kw)) for d in days]
    df = pd.DataFrame(rows)
    if mode == "H1_pmhint":                            # size-weighted (1.5x when gap_up)
        w = np.where(df.gap_up, 1.5, 1.0)
        m = np.average(df.bps, weights=w)
    else:
        m = df.bps.mean()
    yrs = df.groupby("year").bps.mean()
    return dict(variant=label, n=len(df), mean_bps=round(m, 2),
                win_pct=round((df.bps > 0).mean() * 100, 1),
                pos_years=f"{int((yrs>0).sum())}/{yrs.size}")


def run(files, label, cuts):
    days = [d for f in files for d in firing_paths(f)]
    variants = [
        ("base", "BASELINE"),
        ("E1_vwap_pull", "ENTRY pullback-to-VWAP"),
        ("X1_1430", "EXIT flat 14:30"),
        ("X2_1500", "EXIT flat 15:00"),
        ("T1_breakeven", "TRAIL breakeven@+MFE", dict(trig=cuts["mfe_med"])),
        ("T2_chandelier", "TRAIL chandelier(kATR)", dict(k=cuts["k"])),
        ("G1_giveback33", "GIVEBACK 33% of peak", dict(gb=1/3)),
        ("G2_giveback50", "GIVEBACK 50% of peak", dict(gb=0.5)),
        ("P1_target", "PROFIT target @P80 MFE", dict(pt=cuts["mfe_p80"])),
        ("H1_pmhint", "PM-HINT 1.5x gap-up"),
    ]
    rows = [score(days, v[0], v[1], **(v[2] if len(v) > 2 else {})) for v in variants]
    out = pd.DataFrame(rows)
    from tabulate import tabulate as tb
    print(f"\n=== {label} (n={len(days)}) ===")
    print(tb(out, headers="keys", showindex=False))
    return out, days


if __name__ == "__main__":
    TBL.mkdir(parents=True, exist_ok=True)
    # DEV-calibrated cutoffs for the trailing/target variants
    devdays = [d for f in DEV for d in firing_paths(f)]
    mfe = np.array([(np.maximum.accumulate(d["hi"]).max() / d["c"][0] - 1) for d in devdays])
    cuts = dict(mfe_med=float(np.median(mfe[mfe > 0])), mfe_p80=float(np.quantile(mfe, 0.8)),
                k=2.0)                                  # chandelier k=2 ATR (standard)
    print(f"DEV cutoffs: breakeven trigger +{cuts['mfe_med']*100:.2f}% (median MFE), "
          f"target +{cuts['mfe_p80']*100:.2f}% (P80 MFE), chandelier k=2*ATR")
    dev, _ = run(DEV, "DEV 2018-2021", cuts); dev.to_csv(TBL / "UPG_dev.csv", index=False)
    val, _ = run(VAL, "VAL 2022-2026 (frozen cuts)", cuts); val.to_csv(TBL / "UPG_val.csv", index=False)
