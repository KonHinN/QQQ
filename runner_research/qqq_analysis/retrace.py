"""
retrace.py — Analysis N: pullback scaled as % retracement into the OR (0-100%).

Scale: for an up-break, retracement% = (OR_high - price) / (OR_high - OR_low) * 100
  0%   = at the broken extreme (the OR level)
  100% = full traverse to the opposite side of the range
  >100% = break FAILED through the other side (we also track this)

Two studies:
  N(a) LIMIT LADDER (tradable, no look-ahead) — after the first break, rest a limit at rung r%
       (price known at break time). Fill = first bar whose extreme touches the limit; entry at
       the limit price; exit 10:59 close; net 0.4 bps. Per rung: fill rate, expectancy, hit rate,
       H1/H2, MAE, and P(day trended | filled) — the fill-quality/price tradeoff curve.
  N(b) GEOMETRY (descriptive) — distribution of MAX retracement reached after the break,
       split by trended vs failed days, plus P(trend | max retrace bucket) with hindsight caveat.

Outputs -> output/tables/N_*.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, _clk, N_MIN
from or_break import _days, _break_event, COST_BPS, EXIT_IX, TREND_ATR

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
RUNGS = [0, 25, 38, 50, 62, 75, 100]          # % retracement into the OR


def collect(m, w):
    rows = []
    for date, g in _days(m):
        ev = _break_event(g, w)
        if ev is None:
            continue
        atr = g.atr.median()
        s, t0 = ev["side"], ev["t"]
        orh, orl = ev["orh"], ev["orl"]
        orr = orh - orl
        if orr <= 0 or not np.isfinite(atr) or atr <= 0:
            continue
        lvl = orh if s == 1 else orl
        c = g.close.values; lo = g.low.values; hi = g.high.values
        exit_px = c[EXIT_IX]
        ext_atr = (exit_px - lvl) * s / atr
        trended = ext_atr >= TREND_ATR
        # max retracement % reached after the break bar (0 = at level, 100 = full traverse)
        seg_lo = lo[t0 + 1:EXIT_IX + 1]; seg_hi = hi[t0 + 1:EXIT_IX + 1]
        adverse = (lvl - seg_lo) if s == 1 else (seg_hi - lvl)          # $ back inside the range
        max_ret_pct = float(adverse.max() / orr * 100) if len(adverse) else np.nan
        rec = dict(date=date, or_w=w, side=s, t_break=t0, or_range=orr,
                   or_range_atr=round(orr / atr, 2), exit_px=exit_px,
                   ext_atr=round(ext_atr, 3), trended=bool(trended),
                   max_ret_pct=round(max_ret_pct, 1))
        # limit ladder: rung r% => limit price known at t0
        for r in RUNGS:
            limit = lvl - s * (r / 100) * orr
            fill_t = None
            for t in range(t0 + 1, EXIT_IX):                            # fill must occur before exit
                touched = (lo[t] <= limit) if s == 1 else (hi[t] >= limit)
                if touched:
                    fill_t = t
                    break
            if fill_t is not None:
                pnl = ((exit_px - limit) * s / limit) * 1e4 - COST_BPS
                seg = lo[fill_t:EXIT_IX + 1] if s == 1 else hi[fill_t:EXIT_IX + 1]
                mae = ((limit - seg.min()) if s == 1 else (seg.max() - limit)) / atr
                rec[f"r{r}_fill_t"] = fill_t
                rec[f"r{r}_pnl"] = round(float(pnl), 2)
                rec[f"r{r}_mae_atr"] = round(float(mae), 2)
        rows.append(rec)
    return pd.DataFrame(rows)


def ladder_table(df, w):
    out = []
    for r in RUNGS:
        col = f"r{r}_pnl"
        if col not in df:
            continue
        x = df[col].dropna()
        n = len(x)
        if n < 10:
            continue
        filled = df[df[col].notna()]
        t = x.mean() / (x.std() / np.sqrt(n)) if x.std() > 0 else np.nan
        half = n // 2
        out.append(dict(
            or_window=w, retrace_pct=r, fill_rate_pct=round(n / len(df) * 100, 1),
            n_trades=n, hit_pct=round((x > 0).mean() * 100, 1),
            mean_bps=round(x.mean(), 2), med_bps=round(x.median(), 2),
            t_stat=round(t, 2),
            mean_H1=round(x.iloc[:half].mean(), 2), mean_H2=round(x.iloc[half:].mean(), 2),
            mae_med_atr=round(filled[f"r{r}_mae_atr"].median(), 2),
            p_trend_given_fill_pct=round(filled.trended.mean() * 100, 1),
            fill_med_clock=_clk(int(filled[f"r{r}_fill_t"].median())),
        ))
    return pd.DataFrame(out)


def geometry_table(df, w):
    rows = []
    for lbl, sub in [("trended", df[df.trended]), ("failed", df[~df.trended])]:
        x = sub.max_ret_pct.dropna()
        rows.append(dict(or_window=w, outcome=lbl, n_days=len(x),
                         max_ret_med_pct=round(x.median(), 1),
                         q25=round(x.quantile(.25), 1), q75=round(x.quantile(.75), 1),
                         full_traverse_pct=round((x >= 100).mean() * 100, 1)))
    # descriptive (hindsight): P(trend | max retracement bucket)
    buckets = [(0, 25), (25, 50), (50, 75), (75, 100), (100, 1e9)]
    cond = []
    for a, b in buckets:
        sub = df[(df.max_ret_pct >= a) & (df.max_ret_pct < b)]
        if len(sub) >= 8:
            cond.append(dict(or_window=w, bucket=(f">{a}%" if b > 200 else f"{a}-{int(b)}%"),
                             n_days=len(sub), p_trend_pct=round(sub.trended.mean() * 100, 1),
                             ext_med_atr=round(sub.ext_atr.median(), 2)))
    return pd.DataFrame(rows), pd.DataFrame(cond)


def run(write=True):
    m, d = load()
    res = {}
    ladders, geos, conds = [], [], []
    for w in (15, 30):
        df = collect(m, w)
        res[f"N_days_or{w}"] = df
        ladders.append(ladder_table(df, w))
        gtab, ctab = geometry_table(df, w)
        geos.append(gtab); conds.append(ctab)
    res["N_limit_ladder"] = pd.concat(ladders, ignore_index=True)
    res["N_retrace_geometry"] = pd.concat(geos, ignore_index=True)
    res["N_trend_by_depth"] = pd.concat(conds, ignore_index=True)
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[retrace] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 240)
    r = run()
    print("\n=== N(a) limit ladder (entry at r% retracement into the OR, exit 10:59, net) ===")
    print(r["N_limit_ladder"].to_string(index=False))
    print("\n=== N(b) max-retracement geometry ===")
    print(r["N_retrace_geometry"].to_string(index=False))
    print("\n=== N(b) P(trend | max retracement bucket) — descriptive, hindsight ===")
    print(r["N_trend_by_depth"].to_string(index=False))
