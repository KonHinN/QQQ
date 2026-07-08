"""
grid_test.py — Does a volatility-gated dynamic grid work on NASDAQ with more hours?

Faithful-in-spirit port of the VolatilityGridTrading idea (3 protective layers):
  L1 Volatility regime gating   — freeze NEW adds when realized vol is in its high regime
  L2 Rebound confirmation       — only add on a dip AFTER a 1-bar up-tick (no falling knives)
  L3 Dynamic stop + anti-cluster— ATR-scaled grid spacing; cap inventory (anti-cluster);
                                   hard stop if inventory MTM loss exceeds a limit (grid-killer guard)

Grid mechanic: target long units = clip(round((anchor - price)/spacing), 0, Nmax); anchor = EMA;
spacing = g*ATR. Accumulate as price falls below anchor, distribute as it rises = mean-reversion.
Two variants: SYMMETRIC (also shorts above anchor) and LONG-ONLY (drift-aligned, the only one
with a prayer on a +18%/yr index). Continuous extended-hours QQQ (=NASDAQ, more hours) 2018-2026,
resampled to 15-min bars (a realistic grid cadence). Costs 1 bp round-trip. Benchmark: buy&hold.

Output -> printed verdict + tables/GRID_stats.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import ingest

TBL = Path(__file__).resolve().parent / "output" / "tables"
FILES = [f"../qqq_full/QQQ_1min_{y}.csv" for y in range(2018, 2027)]
COST = 1e-4        # round-trip fraction per unit traded


def continuous_15m():
    parts = []
    for f in FILES:
        raw = ingest.load_raw(Path(f))                 # extended hours 04:00-19:59
        raw = raw.set_index("et").sort_index()
        c = raw["close"].resample("15min").last().dropna()
        parts.append(c)
    s = pd.concat(parts)
    s = s[~s.index.duplicated()].sort_index()
    return s


def grid(px: pd.Series, long_only: bool, Nmax=8, g=1.0, ema=96, atr_n=96,
         vol_hi_q=0.8, stop_units_loss=0.15):
    p = px.values
    ret = np.diff(np.log(p), prepend=np.log(p[0]))
    anchor = pd.Series(p).ewm(span=ema).mean().values
    atr = pd.Series(np.abs(ret)).ewm(span=atr_n).mean().values * p    # $ vol proxy
    realized = pd.Series(np.abs(ret)).rolling(ema).mean().values
    vhi = np.nanquantile(realized, vol_hi_q)
    spacing = np.maximum(g * atr, p * 1e-4)

    units = 0.0; avg = 0.0; cash = 0.0; traded = 0.0; eq = []
    for i in range(len(p)):
        # L1 vol gate: high vol -> no NEW adds (allow reductions)
        gate_add = not (realized[i] >= vhi)
        # L2 rebound confirm: only ADD if this bar ticked up vs last
        rebound = ret[i] > 0
        tgt = round((anchor[i] - p[i]) / spacing[i])
        if long_only:
            tgt = np.clip(tgt, 0, Nmax)
        else:
            tgt = np.clip(tgt, -Nmax, Nmax)
        want = tgt
        if want > units and not (gate_add and rebound):   # adding blocked by L1/L2
            want = units
        # L3 hard stop: inventory MTM loss beyond limit -> flatten
        if units != 0:
            mtm = (p[i] - avg) * units / max(abs(avg * units), 1e-9)
            if mtm <= -stop_units_loss:
                want = 0
        d = want - units
        if d != 0:
            traded += abs(d) * p[i]
            cash -= d * p[i] - abs(d) * p[i] * COST          # buy costs, sell adds
            if (units >= 0) == (d > 0) or units == 0:
                avg = (avg * abs(units) + p[i] * abs(d)) / max(abs(units) + abs(d), 1e-9)
            units = want
        eq.append(cash + units * p[i])
    eq = np.array(eq) + 100000.0                              # start bank so it's a $ curve...
    # normalize to a return series on notional = Nmax units of price (the capital at risk)
    cap = Nmax * p[0]
    curve = 100000.0 + (np.array(eq) - eq[0]) / cap * 100000.0
    peak = np.maximum.accumulate(curve)
    dd = (curve / peak - 1).min() * 100
    n_trades = int(traded / p.mean())
    return dict(total_ret_pct=round((curve[-1] / 100000 - 1) * 100, 1),
                max_dd_pct=round(dd, 1), approx_trades=n_trades,
                end=round(curve[-1]))


def run():
    px = continuous_15m()
    yrs = (px.index[-1] - px.index[0]).days / 365.25
    rows = []
    for lo, nm in ((False, "SYMMETRIC grid"), (True, "LONG-ONLY grid")):
        r = grid(px, lo)
        r["config"] = nm
        r["cagr_pct"] = round(((1 + r["total_ret_pct"] / 100) ** (1 / yrs) - 1) * 100, 1)
        rows.append(r)
    bh = (px.iloc[-1] / px.iloc[0] - 1) * 100
    rows.append(dict(config="QQQ buy&hold", total_ret_pct=round(bh, 1),
                     cagr_pct=round(((px.iloc[-1] / px.iloc[0]) ** (1 / yrs) - 1) * 100, 1),
                     max_dd_pct=round((px / px.cummax() - 1).min() * 100, 1),
                     approx_trades=1, end=round(100000 * px.iloc[-1] / px.iloc[0])))
    df = pd.DataFrame(rows)[["config", "total_ret_pct", "cagr_pct", "max_dd_pct", "approx_trades", "end"]]
    TBL.mkdir(parents=True, exist_ok=True)
    df.to_csv(TBL / "GRID_stats.csv", index=False)
    from tabulate import tabulate as tb
    print(f"Continuous extended-hours QQQ (=NASDAQ, more hours), {len(px)} 15-min bars, {yrs:.1f}y")
    print(tb(df, headers="keys", showindex=False))
    return df


if __name__ == "__main__":
    run()
